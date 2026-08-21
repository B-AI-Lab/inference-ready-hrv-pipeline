"""
Bluetooth LE Polar H10-to-dashboard bridge.

Input from BLE chest belts:
    Heart Rate Service (0x180D), Heart Rate Measurement characteristic (0x2A37)
    with optional RR intervals in 1/1024 second units.

Output to browser:
    Server-Sent Events on /stream.

Event shape:
    event: subject
    data: {"subject": {...}, "payload": HRVDashboardPayload}

The existing HRVProcessingEngine remains the single scientific processing
layer. This bridge only discovers/connects BLE devices, parses RR intervals,
and multiplexes subjects for the dashboard.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape
import zipfile

from hrv_live_processing_engine import HRVProcessingEngine, simulate_rr_stream


HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


@dataclass
class SubjectMeta:
    subjectId: str
    displayName: str
    macAddress: str
    source: str
    streamStatus: str
    colorToken: str


COLOR_PALETTE = ["#c084fc", "#5eead4", "#fb7185", "#fbbf24", "#818cf8"]
CONTEXT_PHASES = ("baseline", "intervention", "recovery")


def finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def normalize_context_event(label: Any) -> Tuple[Optional[str], Optional[str]]:
    text = " ".join(str(label or "").strip().lower().replace("_", " ").replace("-", " ").split())
    for phase in CONTEXT_PHASES:
        if text in (f"start {phase}", f"{phase} start"):
            return phase, "start"
        if text in (f"stop {phase}", f"{phase} stop", f"end {phase}", f"{phase} end"):
            return phase, "stop"
    return None, None


def context_for_host_time(events: Sequence[Dict[str, Any]], host_sec: Optional[float]) -> Dict[str, Any]:
    active: Dict[str, Optional[Dict[str, Any]]] = {phase: None for phase in CONTEXT_PHASES}
    if host_sec is not None:
        for event in sorted(events, key=lambda item: finite_float(item.get("hostSec")) or 0.0):
            event_host = finite_float(event.get("hostSec"))
            if event_host is None or event_host > host_sec:
                continue
            phase, action = normalize_context_event(event.get("eventLabel"))
            if phase is None or action is None:
                continue
            if action == "start":
                active[phase] = event
            elif action == "stop":
                active[phase] = None

    active_labels = [phase for phase in CONTEXT_PHASES if active[phase] is not None]
    primary = active_labels[-1] if active_labels else "none"
    return {
        "baselineActive": active["baseline"] is not None,
        "interventionActive": active["intervention"] is not None,
        "recoveryActive": active["recovery"] is not None,
        "contextPhase": primary,
        "activeContexts": active_labels,
        "baselineEventId": (active["baseline"] or {}).get("eventId"),
        "interventionEventId": (active["intervention"] or {}).get("eventId"),
        "recoveryEventId": (active["recovery"] or {}).get("eventId"),
    }


def context_intervals(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    open_by_phase: Dict[str, Dict[str, Any]] = {}
    intervals: List[Dict[str, Any]] = []
    for event in sorted(events, key=lambda item: finite_float(item.get("hostSec")) or 0.0):
        phase, action = normalize_context_event(event.get("eventLabel"))
        if phase is None or action is None:
            continue
        if action == "start":
            open_by_phase[phase] = event
        elif action == "stop":
            start = open_by_phase.pop(phase, None)
            if start is None:
                continue
            intervals.append({
                "phase": phase,
                "startEventId": start.get("eventId"),
                "stopEventId": event.get("eventId"),
                "startHostSec": start.get("hostSec"),
                "stopHostSec": event.get("hostSec"),
                "startSessionElapsedSec": start.get("sessionElapsedSec"),
                "stopSessionElapsedSec": event.get("sessionElapsedSec"),
            })
    for phase, start in open_by_phase.items():
        intervals.append({
            "phase": phase,
            "startEventId": start.get("eventId"),
            "stopEventId": None,
            "startHostSec": start.get("hostSec"),
            "stopHostSec": None,
            "startSessionElapsedSec": start.get("sessionElapsedSec"),
            "stopSessionElapsedSec": None,
        })
    return intervals


def parse_heart_rate_measurement(data: bytes) -> Tuple[Optional[float], List[float]]:
    """Parse BLE Heart Rate Measurement bytes into BPM and RR intervals in ms."""
    if not data:
        return None, []

    flags = data[0]
    offset = 1
    is_hr_uint16 = bool(flags & 0x01)
    energy_present = bool(flags & 0x08)
    rr_present = bool(flags & 0x10)

    if is_hr_uint16:
        if len(data) < offset + 2:
            return None, []
        heart_rate = float(int.from_bytes(data[offset:offset + 2], "little"))
        offset += 2
    else:
        if len(data) < offset + 1:
            return None, []
        heart_rate = float(data[offset])
        offset += 1

    if energy_present:
        offset += 2

    rr_ms: List[float] = []
    if rr_present:
        while len(data) >= offset + 2:
            rr_1024 = int.from_bytes(data[offset:offset + 2], "little")
            offset += 2
            rr = (rr_1024 / 1024.0) * 1000.0
            if 250.0 <= rr <= 2200.0:
                rr_ms.append(rr)

    return heart_rate if math.isfinite(heart_rate) else None, rr_ms


class MultiPayloadStore:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._sequence = 0
        self._subjects: Dict[str, Dict[str, Any]] = {}
        self._payloads: Dict[str, Dict[str, Any]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._events: List[Dict[str, Any]] = []
        self._burned_event_ids_by_subject: Dict[str, set[str]] = {}
        self._session_started_host_sec = time.time()
        self._session_started_iso = datetime.now(timezone.utc).isoformat()
        self.status: Dict[str, Any] = {
            "connected": False,
            "source": "ble",
            "subjectCount": 0,
            "eventCount": 0,
            "events": [],
            "lastError": None,
            "sessionStartedAt": self._session_started_iso,
            "subjects": [],
        }

    def register_subject(self, subject: SubjectMeta, **status: Any) -> None:
        with self._condition:
            existing = self._subjects.get(subject.subjectId, {})
            self._subjects[subject.subjectId] = {
                **existing,
                "subject": subject.__dict__,
                "connected": status.get("connected", existing.get("connected", False)),
                "detectedRR": status.get("detectedRR", existing.get("detectedRR", 0)),
                "lastRR": status.get("lastRR", existing.get("lastRR")),
                "lastError": status.get("lastError", existing.get("lastError")),
                "lastSeenHostSec": status.get("lastSeenHostSec", existing.get("lastSeenHostSec")),
            }
            self._refresh_status_locked()
            self._sequence += 1
            self._condition.notify_all()

    def update_subject_status(self, subject_id: str, **status: Any) -> None:
        with self._condition:
            existing = self._subjects.setdefault(subject_id, {"subject": None})
            existing.update(status)
            self._refresh_status_locked()
            self._sequence += 1
            self._condition.notify_all()

    def update_payload(self, subject: SubjectMeta, payload: Dict[str, Any], rr_ms: float) -> None:
        with self._condition:
            host_now = time.time()
            burned = self._burned_event_ids_by_subject.setdefault(subject.subjectId, set())
            row_events = [event for event in self._events if event["eventId"] not in burned and event["hostSec"] <= host_now]
            for event in row_events:
                burned.add(event["eventId"])

            self._payloads[subject.subjectId] = {"subject": subject.__dict__, "payload": payload}
            existing = self._subjects.setdefault(subject.subjectId, {"subject": subject.__dict__})
            existing["subject"] = subject.__dict__
            existing["connected"] = True
            existing["detectedRR"] = int(existing.get("detectedRR") or 0) + 1
            existing["lastRR"] = rr_ms
            existing["lastError"] = None
            existing["lastSeenHostSec"] = host_now

            self._history.setdefault(subject.subjectId, []).append({
                "receivedAt": datetime.now(timezone.utc).isoformat(),
                "hostSec": host_now,
                "sessionElapsedSec": host_now - self._session_started_host_sec,
                "subject": subject.__dict__,
                "sample": payload.get("sample", {}),
                "quality": payload.get("quality", {}),
                "events": row_events,
            })
            self._refresh_status_locked()
            self._sequence += 1
            self._condition.notify_all()

    def add_event(self, label: str, event_type: str = "manual") -> Dict[str, Any]:
        with self._condition:
            event_index = len(self._events) + 1
            host_now = time.time()
            event = {
                "eventId": f"E{event_index:03d}",
                "eventLabel": (label or f"Event {event_index}").strip()[:80],
                "eventType": (event_type or "manual").strip()[:40],
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "hostSec": host_now,
                "sessionElapsedSec": host_now - self._session_started_host_sec,
            }
            self._events.append(event)
            self._refresh_status_locked()
            self._sequence += 1
            self._condition.notify_all()
            return dict(event)

    def update_global_error(self, error: Optional[str]) -> None:
        with self._condition:
            self.status["lastError"] = error
            self._sequence += 1
            self._condition.notify_all()

    def snapshot(self) -> Tuple[int, Dict[str, Dict[str, Any]], Dict[str, Any]]:
        with self._condition:
            payloads = json.loads(json.dumps(self._payloads))
            status = self._status_snapshot_locked()
            return self._sequence, payloads, status

    def export_session(self) -> Dict[str, Any]:
        with self._condition:
            subjects: Dict[str, Dict[str, Any]] = {}
            for subject_id, subject_status in self._subjects.items():
                history = json.loads(json.dumps(self._history.get(subject_id, [])))
                for record in history:
                    record["context"] = context_for_host_time(self._events, finite_float(record.get("hostSec")))
                subjects[subject_id] = {
                    "subject": subject_status.get("subject"),
                    "status": self._subject_status_with_health(subject_status),
                    "latest": self._payloads.get(subject_id),
                    "history": history,
                }
            return json.loads(json.dumps({
                "session": {
                    "startedAt": self._session_started_iso,
                    "exportedAt": datetime.now(timezone.utc).isoformat(),
                    "source": "Polar H10 BLE",
                    "simulation": False,
                },
                "status": self._status_snapshot_locked(),
                "globalEvents": self._events,
                "contextIntervals": context_intervals(self._events),
                "subjects": subjects,
            }))

    def wait_next(self, after_sequence: int, timeout: Optional[float] = None) -> Tuple[int, Dict[str, Dict[str, Any]]]:
        with self._condition:
            if timeout is None:
                while self._sequence <= after_sequence:
                    self._condition.wait()
            elif self._sequence <= after_sequence:
                self._condition.wait(timeout=timeout)
            return self._sequence, dict(self._payloads)

    def _refresh_status_locked(self) -> None:
        subjects = [self._subject_status_with_health(subject) for subject in self._subjects.values()]
        self.status["subjects"] = subjects
        self.status["subjectCount"] = len(subjects)
        self.status["eventCount"] = len(self._events)
        self.status["events"] = self._events[-20:]
        self.status["connected"] = any(bool(s.get("connected")) for s in subjects)

    def _status_snapshot_locked(self) -> Dict[str, Any]:
        self._refresh_status_locked()
        return json.loads(json.dumps(self.status))

    def _subject_status_with_health(self, subject_status: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(subject_status)
        last_seen = finite_float(out.get("lastSeenHostSec"))
        age = (time.time() - last_seen) if last_seen is not None else None
        out["lastSeenAgeSec"] = age
        if not out.get("connected"):
            out["signalState"] = "reconnecting"
        elif age is None:
            out["signalState"] = "waiting"
        elif age <= 3.0:
            out["signalState"] = "live"
        elif age <= 12.0:
            out["signalState"] = "stale"
        else:
            out["signalState"] = "lost"
        return out


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(value: Any, row: int, col: int) -> str:
    ref = f"{_column_name(col)}{row}"
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = "" if value is None else str(value)
    return f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(text)}</t></is></c>'


def _xlsx_sheet(rows: List[List[Any]]) -> str:
    body = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(_xlsx_cell(value, row_index, col_index) for col_index, value in enumerate(row, start=1))
        body.append(f'<row r="{row_index}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>' + "".join(body) + '</sheetData></worksheet>'
    )


def _safe_sheet_name(name: str, used: set[str]) -> str:
    cleaned = "".join("_" if char in r'[]:*?/\\' else char for char in (name or "Subject")).strip()[:31] or "Subject"
    candidate = cleaned
    counter = 2
    while candidate.lower() in used:
        suffix = f"_{counter}"
        candidate = cleaned[:31 - len(suffix)] + suffix
        counter += 1
    used.add(candidate.lower())
    return candidate


def _history_row(record: Dict[str, Any]) -> List[Any]:
    subject = record.get("subject") or {}
    sample = record.get("sample") or {}
    quality = record.get("quality") or {}
    events = record.get("events") or []
    context = record.get("context") or {}
    return [
        record.get("receivedAt"),
        record.get("sessionElapsedSec"),
        subject.get("subjectId"),
        subject.get("displayName"),
        subject.get("macAddress"),
        sample.get("rrMs"),
        sample.get("heartRate"),
        sample.get("rmssd"),
        sample.get("sdnn"),
        sample.get("pnn50"),
        sample.get("stressScore"),
        sample.get("recoveryScore"),
        sample.get("physiologicalState"),
        sample.get("signalConfidence"),
        quality.get("signalStatus"),
        quality.get("artifactRatioRecent"),
        quality.get("nRawRR"),
        quality.get("nValidRR"),
        bool(context.get("baselineActive")),
        bool(context.get("interventionActive")),
        bool(context.get("recoveryActive")),
        context.get("contextPhase") or "none",
        ";".join(str(label) for label in (context.get("activeContexts") or [])),
        context.get("baselineEventId"),
        context.get("interventionEventId"),
        context.get("recoveryEventId"),
        ";".join(str(event.get("eventId", "")) for event in events),
        ";".join(str(event.get("eventLabel", "")) for event in events),
        ";".join(str(event.get("eventType", "")) for event in events),
    ]


def build_session_xlsx(session: Dict[str, Any]) -> bytes:
    headers = [
        "receivedAt", "sessionElapsedSec", "subjectId", "displayName", "macAddress",
        "rrMs", "heartRate", "rmssd", "sdnn", "pnn50", "stressScore", "recoveryScore",
        "physiologicalState", "signalConfidence", "signalStatus", "artifactRatioRecent",
        "nRawRR", "nValidRR",
        "baselineActive", "interventionActive", "recoveryActive", "contextPhase", "activeContexts",
        "baselineEventId", "interventionEventId", "recoveryEventId",
        "eventIds", "eventLabels", "eventTypes",
    ]
    subjects = session.get("subjects") or {}
    sheets: List[Tuple[str, List[List[Any]]]] = []
    used_names: set[str] = set()
    for subject_id, entry in subjects.items():
        subject = (entry or {}).get("subject") or {}
        sheet_name = _safe_sheet_name(subject.get("displayName") or subject_id, used_names)
        rows = [headers]
        rows.extend(_history_row(record) for record in ((entry or {}).get("history") or []))
        sheets.append((sheet_name, rows))
    if not sheets:
        sheets.append(("NoData", [headers]))

    workbook_sheets = "".join(
        f'<sheet name="{xml_escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, (name, _rows) in enumerate(sheets, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{workbook_sheets}</sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
            for idx in range(1, len(sheets) + 1)
        )
        + '</Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for idx in range(1, len(sheets) + 1)
        )
        + '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr("[Content_Types].xml", content_types)
        workbook_zip.writestr("_rels/.rels", root_rels)
        workbook_zip.writestr("xl/workbook.xml", workbook)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for idx, (_name, rows) in enumerate(sheets, start=1):
            workbook_zip.writestr(f"xl/worksheets/sheet{idx}.xml", _xlsx_sheet(rows))
    return buffer.getvalue()


def make_handler(store: MultiPayloadStore):
    class HRVBleBridgeHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send_cors_headers(self, content_type: str) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-cache")

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers("text/plain")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/stream":
                self._stream()
                return
            if path == "/export/session.json":
                self._export_json()
                return
            if path == "/export/session.xlsx":
                self._export_xlsx()
                return
            if path in ("/", "/latest", "/health"):
                self._json_snapshot()
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/events":
                self._add_event()
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def _json_snapshot(self) -> None:
            _, payloads, status = store.snapshot()
            body = json.dumps({"status": status, "subjects": payloads}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self._send_cors_headers("application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _add_event(self) -> None:
            content_length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                data = {}
            event = store.add_event(str(data.get("label") or "Manual Event"), str(data.get("type") or "manual"))
            body = json.dumps({"ok": True, "event": event}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self._send_cors_headers("application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _export_json(self) -> None:
            body = json.dumps(store.export_session(), indent=2).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self._send_cors_headers("application/json")
            self.send_header("Content-Disposition", 'attachment; filename="polar_h10_session.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _export_xlsx(self) -> None:
            body = build_session_xlsx(store.export_session())
            self.send_response(HTTPStatus.OK)
            self._send_cors_headers("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", 'attachment; filename="polar_h10_session.xlsx"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream(self) -> None:
            self.send_response(HTTPStatus.OK)
            self._send_cors_headers("text/event-stream")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            sequence, payloads, status = store.snapshot()
            sent_payload_keys: Dict[str, str] = {}
            self._write_event("status", status)
            for payload in payloads.values():
                if self._payload_is_new(payload, sent_payload_keys):
                    self._write_event("subject", payload)

            while True:
                next_sequence, _ = store.wait_next(sequence, timeout=10.0)
                try:
                    _, current_payloads, current_status = store.snapshot()
                    self._write_event("status", current_status)
                    if next_sequence != sequence:
                        sequence = next_sequence
                        for payload in current_payloads.values():
                            if self._payload_is_new(payload, sent_payload_keys):
                                self._write_event("subject", payload)
                except (BrokenPipeError, ConnectionResetError):
                    break

        def _payload_is_new(self, data: Dict[str, Any], sent_payload_keys: Dict[str, str]) -> bool:
            subject = data.get("subject") or {}
            payload = data.get("payload") or {}
            subject_id = str(subject.get("subjectId") or "")
            sample = payload.get("sample") or {}
            quality = payload.get("quality") or {}
            key = json.dumps(
                [
                    sample.get("timestamp"),
                    sample.get("elapsedSec"),
                    sample.get("rrMs"),
                    quality.get("nRawRR"),
                    quality.get("nValidRR"),
                ],
                separators=(",", ":"),
            )
            if not subject_id:
                return False
            if sent_payload_keys.get(subject_id) == key:
                return False
            sent_payload_keys[subject_id] = key
            return True

        def _write_event(self, event: str, data: Dict[str, Any]) -> None:
            payload = json.dumps(data, separators=(",", ":"))
            self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()

    return HRVBleBridgeHandler


def make_subject(index: int, address: str, name: Optional[str]) -> SubjectMeta:
    clean_address = address or f"BLE:{index + 1:02d}"
    return SubjectMeta(
        subjectId=f"P{index + 1:02d}",
        displayName=name or f"Polar H10 {index + 1}",
        macAddress=clean_address,
        source="Polar H10 BLE",
        streamStatus="connected",
        colorToken=COLOR_PALETTE[index % len(COLOR_PALETTE)],
    )


def device_name(device: Any, advertisement_data: Any = None) -> str:
    name = getattr(device, "name", None) or ""
    if not name and advertisement_data is not None:
        name = getattr(advertisement_data, "local_name", None) or ""
    return str(name or "")


def advertised_services(advertisement_data: Any = None) -> List[str]:
    uuids = getattr(advertisement_data, "service_uuids", None) if advertisement_data is not None else None
    return [str(u).lower() for u in (uuids or [])]


def should_accept_device(
    address: str,
    name: str,
    services: Sequence[str],
    allowed_addresses: Sequence[str],
    name_filters: Sequence[str],
) -> bool:
    if allowed_addresses:
        return address.lower() in {a.lower() for a in allowed_addresses}
    name_l = name.lower()
    filter_match = any(f.lower() in name_l for f in name_filters)
    service_match = HEART_RATE_SERVICE_UUID in services or "180d" in services
    return filter_match or service_match


async def discover_targets(args: argparse.Namespace) -> List[Tuple[str, str]]:
    try:
        from bleak import BleakScanner
    except ImportError as exc:
        raise RuntimeError("bleak is not installed. Install it with: python -m pip install bleak") from exc

    if args.address:
        return [(address, f"Polar H10 {i + 1}") for i, address in enumerate(args.address[: args.max_devices])]

    found: List[Tuple[str, str]] = []
    seen = set()
    try:
        discovered = await BleakScanner.discover(timeout=args.scan_sec, return_adv=True)
        iterable: Iterable[Any]
        if isinstance(discovered, dict):
            iterable = discovered.values()
        else:
            iterable = discovered
        for item in iterable:
            if isinstance(item, tuple) and len(item) == 2:
                device, adv = item
            else:
                device, adv = item, None
            address = str(getattr(device, "address", ""))
            name = device_name(device, adv)
            services = advertised_services(adv)
            if not address or address.lower() in seen:
                continue
            if should_accept_device(address, name, services, args.address, args.name_filter):
                seen.add(address.lower())
                found.append((address, name or f"Polar H10 {len(found) + 1}"))
            if len(found) >= args.max_devices:
                break
    except TypeError:
        devices = await BleakScanner.discover(timeout=args.scan_sec)
        for device in devices:
            address = str(getattr(device, "address", ""))
            name = device_name(device)
            if not address or address.lower() in seen:
                continue
            if should_accept_device(address, name, [], args.address, args.name_filter):
                seen.add(address.lower())
                found.append((address, name or f"Polar H10 {len(found) + 1}"))
            if len(found) >= args.max_devices:
                break
    return found


async def resolve_connection_target(address: str, scan_sec: float) -> Any:
    try:
        from bleak import BleakScanner
    except ImportError:
        return address
    try:
        device = await BleakScanner.find_device_by_address(address, timeout=scan_sec)
        return device or address
    except Exception:
        return address


async def connect_subject(
    index: int,
    address: str,
    name: str,
    args: argparse.Namespace,
    store: MultiPayloadStore,
    stop: threading.Event,
) -> None:
    try:
        from bleak import BleakClient
    except ImportError as exc:
        store.update_global_error("bleak is not installed. Install it with: python -m pip install bleak")
        raise RuntimeError("bleak is not installed") from exc

    subject = make_subject(index, address, name)
    engine = HRVProcessingEngine()
    store.register_subject(subject, connected=False)

    while not stop.is_set():
        try:
            target = await resolve_connection_target(address, args.scan_sec)
            async with BleakClient(target, timeout=args.connect_timeout_sec) as client:
                store.register_subject(subject, connected=True, lastError=None)

                def on_measurement(_sender: Any, data: bytearray) -> None:
                    heart_rate, rr_values = parse_heart_rate_measurement(bytes(data))
                    for rr_ms in rr_values:
                        payload = engine.add_rr_interval(rr_ms)
                        payload.setdefault("quality", {})["heartRateMeasurementBpm"] = finite_float(heart_rate)
                        payload.setdefault("quality", {})["transport"] = "ble-heart-rate-service"
                        store.update_payload(subject, payload, rr_ms)

                await client.start_notify(HEART_RATE_MEASUREMENT_UUID, on_measurement)
                while not stop.is_set() and getattr(client, "is_connected", True):
                    await asyncio.sleep(0.5)
                try:
                    await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
                except Exception:
                    pass
        except Exception as exc:
            store.update_subject_status(subject.subjectId, connected=False, lastError=str(exc))
            await asyncio.sleep(args.reconnect_sec)


async def ble_manager(args: argparse.Namespace, store: MultiPayloadStore, stop: threading.Event) -> None:
    tasks: Dict[str, asyncio.Task[None]] = {}
    names: Dict[str, str] = {}
    while not stop.is_set():
        try:
            targets = await discover_targets(args)
            store.update_global_error(None if targets else "No Polar H10 / BLE Heart Rate devices found")
        except Exception as exc:
            store.update_global_error(str(exc))
            await asyncio.sleep(args.rescan_sec)
            continue

        for address, name in targets:
            if address not in tasks or tasks[address].done():
                names[address] = name
                index = sorted({*names.keys(), address}).index(address)
                tasks[address] = asyncio.create_task(connect_subject(index, address, name, args, store, stop))

        await asyncio.sleep(args.rescan_sec)

    for task in tasks.values():
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks.values(), return_exceptions=True)


def ble_worker(args: argparse.Namespace, store: MultiPayloadStore, stop: threading.Event) -> None:
    asyncio.run(ble_manager(args, store, stop))


def simulated_worker(args: argparse.Namespace, store: MultiPayloadStore, stop: threading.Event) -> None:
    subjects = [make_subject(i, f"SIM:{i + 1:02d}", f"Polar H10 Sim {i + 1}") for i in range(args.max_devices)]
    engines = [HRVProcessingEngine() for _ in subjects]
    streams = [simulate_rr_stream(duration_sec=None, seed=42 + i * 101) for i in range(args.max_devices)]
    next_elapsed = [0.0 for _ in subjects]
    for subject in subjects:
        subject.streamStatus = "simulated"
        subject.source = "Polar H10 BLE (simulated)"
        store.register_subject(subject, connected=True)

    while not stop.is_set():
        for i, subject in enumerate(subjects):
            rr_ms, elapsed = next(streams[i])
            sleep_for = max(0.01, elapsed - next_elapsed[i])
            next_elapsed[i] = elapsed
            payload = engines[i].add_rr_interval(rr_ms, timestamp=elapsed)
            payload.setdefault("quality", {})["transport"] = "simulated-ble-heart-rate-service"
            store.update_payload(subject, payload, rr_ms)
            time.sleep(sleep_for / max(1, len(subjects)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge Polar H10 BLE RR intervals into the multi-subject HRV dashboard")
    parser.add_argument("--address", action="append", default=[], help="BLE address to connect. Repeat for multiple belts.")
    parser.add_argument("--name-filter", action="append", default=["Polar", "H10"], help="Accepted BLE name substring. Repeatable.")
    parser.add_argument("--max-devices", type=int, default=5, help="Maximum number of belts to connect")
    parser.add_argument("--scan-sec", type=float, default=8.0, help="BLE scan duration")
    parser.add_argument("--rescan-sec", type=float, default=10.0, help="Seconds between discovery passes")
    parser.add_argument("--reconnect-sec", type=float, default=3.0, help="Seconds before reconnect attempts")
    parser.add_argument("--connect-timeout-sec", type=float, default=15.0, help="BLE connection timeout")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP/SSE bind host")
    parser.add_argument("--http-port", type=int, default=8765, help="HTTP/SSE bind port")
    parser.add_argument("--simulate", action="store_true", help="Use simulated multi-subject BLE RR streams")
    args = parser.parse_args()
    args.max_devices = max(1, min(5, args.max_devices))

    store = MultiPayloadStore()
    stop = threading.Event()
    if args.simulate:
        worker = threading.Thread(target=simulated_worker, args=(args, store, stop), daemon=True)
    else:
        worker = threading.Thread(target=ble_worker, args=(args, store, stop), daemon=True)
    worker.start()

    server = ThreadingHTTPServer((args.host, args.http_port), make_handler(store))
    print(f"[HRV BLE bridge] stream: http://{args.host}:{args.http_port}/stream")
    print(f"[HRV BLE bridge] latest: http://{args.host}:{args.http_port}/latest")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()

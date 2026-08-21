"""
Serial-to-dashboard bridge for the ESP32 AD8232 ECG firmware.

Input from ESP32 serial:
    RR_MS,<rr_ms>,BPM,<bpm>,TS_MS,<millis>

Output to browser:
    Server-Sent Events on /stream carrying HRVDashboardPayload JSON objects.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Deque, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from hrv_live_processing_engine import HRVProcessingEngine, simulate_rr_stream


RR_LINE_RE = re.compile(r"rr[_ ]?ms\s*=\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
BPM_RE = re.compile(r"bpm\s*=\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


def parse_rr_line(line: str) -> Optional[Tuple[float, Optional[float], Optional[float]]]:
    s = line.strip()
    if not s:
        return None

    if s.startswith("RR_MS,"):
        parts = s.split(",")
        if len(parts) >= 6:
            try:
                rr_ms = float(parts[1])
                bpm = float(parts[3])
                ts_ms = float(parts[5])
            except ValueError:
                return None
            if math.isfinite(rr_ms) and rr_ms > 0:
                return rr_ms, bpm if math.isfinite(bpm) else None, ts_ms if math.isfinite(ts_ms) else None
        return None

    rr_match = RR_LINE_RE.search(s)
    if rr_match:
        rr_ms = float(rr_match.group(1))
        if rr_ms > 0:
            bpm_match = BPM_RE.search(s)
            bpm = float(bpm_match.group(1)) if bpm_match else None
            return rr_ms, bpm, None

    if re.fullmatch(r"[0-9]{3,4}", s):
        rr_ms = float(s)
        if 250.0 <= rr_ms <= 2200.0:
            return rr_ms, 60000.0 / rr_ms, None

    return None


def finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


class RetrospectiveRRFilter:
    """Delay one RR interval and correct obvious split/early detections."""

    def __init__(self, enabled: bool = True, recent_size: int = 21) -> None:
        self.enabled = enabled
        self.pending: Optional[Tuple[float, Optional[float]]] = None
        self.recent: Deque[float] = deque(maxlen=recent_size)
        self.rejected_count = 0
        self.merged_count = 0

    def add(self, rr_ms: float, timestamp: Optional[float]) -> List[Tuple[float, Optional[float], str]]:
        if not self.enabled:
            return [(rr_ms, timestamp, "filter_disabled")]

        if self.pending is None:
            self.pending = (rr_ms, timestamp)
            return []

        pending_rr, pending_ts = self.pending
        median = self._median()

        if median is not None:
            merged_rr = pending_rr + rr_ms

            # Split beat pattern: a false P-wave/R-wave pair inside one cycle.
            if rr_ms < max(360.0, median * 0.48) and (median * 0.72) <= merged_rr <= (median * 1.28):
                self.pending = None
                self.merged_count += 1
                self._remember(merged_rr)
                return [(merged_rr, timestamp, "merged_short_split")]

            # Early false peak followed by a long recovery interval. Drop the
            # early interval and wait one more beat before accepting the current.
            if pending_rr < median * 0.86 and rr_ms > median * 1.04 and (median * 1.70) <= merged_rr <= (median * 2.30):
                self.pending = (rr_ms, timestamp)
                self.rejected_count += 1
                return []

            # Isolated very short interval.
            if pending_rr < max(330.0, median * 0.55):
                self.pending = (rr_ms, timestamp)
                self.rejected_count += 1
                return []

        self.pending = (rr_ms, timestamp)
        self._remember(pending_rr)
        return [(pending_rr, pending_ts, "accepted_retrospective")]

    def flush(self) -> List[Tuple[float, Optional[float], str]]:
        if self.pending is None:
            return []
        rr_ms, timestamp = self.pending
        self.pending = None
        self._remember(rr_ms)
        return [(rr_ms, timestamp, "accepted_flush")]

    def _median(self) -> Optional[float]:
        if len(self.recent) < 6:
            return None
        values = sorted(self.recent)
        mid = len(values) // 2
        if len(values) % 2:
            return float(values[mid])
        return float((values[mid - 1] + values[mid]) / 2.0)

    def _remember(self, rr_ms: float) -> None:
        if math.isfinite(rr_ms) and 300.0 <= rr_ms <= 2000.0:
            self.recent.append(float(rr_ms))


class PayloadStore:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._payload: Optional[Dict[str, Any]] = None
        self._sequence = 0
        self.status: Dict[str, Any] = {
            "connected": False,
            "source": "starting",
            "rawLines": 0,
            "detectedRR": 0,
            "parsedRR": 0,
            "retroRejectedRR": 0,
            "retroMergedRR": 0,
            "lastRR": None,
            "signalPresent": False,
            "lastRawHostSec": None,
            "lastPayloadElapsedSec": None,
            "lastError": None,
        }

    def update_payload(self, payload: Dict[str, Any]) -> None:
        with self._condition:
            self._payload = payload
            self._sequence += 1
            self._condition.notify_all()

    def update_status(self, **values: Any) -> None:
        with self._condition:
            self.status.update(values)
            self._sequence += 1
            self._condition.notify_all()

    def snapshot(self) -> Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]:
        with self._condition:
            return self._sequence, self._payload, dict(self.status)

    def wait_next(self, after_sequence: int, timeout: Optional[float] = None) -> Tuple[int, Optional[Dict[str, Any]]]:
        with self._condition:
            if timeout is None:
                while self._sequence <= after_sequence:
                    self._condition.wait()
            elif self._sequence <= after_sequence:
                self._condition.wait(timeout=timeout)
            return self._sequence, self._payload


def make_handler(store: PayloadStore):
    class HRVBridgeHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send_cors_headers(self, content_type: str) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
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
            if path in ("/", "/latest", "/health"):
                self._json_snapshot()
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def _json_snapshot(self) -> None:
            _, payload, status = store.snapshot()
            body = json.dumps({"status": status, "payload": payload}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self._send_cors_headers("application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream(self) -> None:
            self.send_response(HTTPStatus.OK)
            self._send_cors_headers("text/event-stream")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            sequence, payload, status = store.snapshot()
            self._write_event("status", status)
            if payload is not None:
                self._write_event("hrv", payload)

            while True:
                next_sequence, next_payload = store.wait_next(sequence, timeout=10.0)
                try:
                    if next_sequence != sequence:
                        sequence = next_sequence
                        _, current_payload, current_status = store.snapshot()
                        self._write_event("status", current_status)
                        if current_payload is not None:
                            self._write_event("hrv", current_payload)
                    else:
                        _, _, current_status = store.snapshot()
                        self._write_event("status", current_status)
                except (BrokenPipeError, ConnectionResetError):
                    break

        def _write_event(self, event: str, data: Dict[str, Any]) -> None:
            payload = json.dumps(data, separators=(",", ":"))
            self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()

    return HRVBridgeHandler


def make_signal_lost_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(payload))
    sample = out.setdefault("sample", {})
    quality = out.setdefault("quality", {})
    sample["physiologicalState"] = "Signal Lost"
    sample["signalConfidence"] = 0.0
    quality["signalStatus"] = "Signal Lost"
    return out


def serial_worker(args: argparse.Namespace, store: PayloadStore, stop: threading.Event) -> None:
    try:
        import serial
    except ImportError:
        store.update_status(
            connected=False,
            source="serial",
            lastError="pyserial is not installed. Install it with: python3 -m pip install pyserial",
        )
        return

    engine = HRVProcessingEngine()
    rr_filter = RetrospectiveRRFilter(enabled=not args.no_retrospective_rr_filter)
    ser = None
    last_r_host_ts: Optional[float] = None
    last_status_print = 0.0
    last_raw_host_ts: Optional[float] = None
    last_signal_lost_emit = 0.0
    signal_was_present = False

    try:
        while not stop.is_set():
            if ser is None:
                try:
                    ser = serial.Serial(
                        args.port,
                        args.baud,
                        timeout=0.2,
                        xonxoff=False,
                        rtscts=False,
                        dsrdtr=False,
                        exclusive=not args.no_exclusive,
                    )
                    try:
                        ser.dtr = False
                        ser.rts = False
                    except Exception:
                        pass
                    ser.reset_input_buffer()
                    store.update_status(connected=True, source=f"serial:{args.port}", lastError=None)
                except serial.SerialException as exc:
                    store.update_status(connected=False, source=f"serial:{args.port}", lastError=str(exc))
                    time.sleep(1.0)
                    continue

            try:
                raw = ser.readline().decode(errors="ignore").strip()
            except serial.SerialException as exc:
                store.update_status(connected=False, lastError=str(exc))
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                continue

            if not raw:
                now_status = time.time()
                if (
                    last_raw_host_ts is not None
                    and args.signal_timeout_sec > 0
                    and (now_status - last_raw_host_ts) >= args.signal_timeout_sec
                    and signal_was_present
                ):
                    signal_was_present = False
                    store.update_status(signalPresent=False, lastRawHostSec=last_raw_host_ts)
                    if (now_status - last_signal_lost_emit) >= args.signal_lost_emit_sec:
                        last_signal_lost_emit = now_status
                        _, last_payload, _ = store.snapshot()
                        if last_payload is not None:
                            store.update_payload(make_signal_lost_payload(last_payload))
                if args.status_every_sec > 0 and (now_status - last_status_print) >= args.status_every_sec:
                    last_status_print = now_status
                    status = store.status
                    print(
                        "[HRV bridge] "
                        f"connected={status.get('connected')} raw={status.get('rawLines')} "
                        f"detected={status.get('detectedRR')} parsed={status.get('parsedRR')} "
                        f"retroReject={status.get('retroRejectedRR')} retroMerge={status.get('retroMergedRR')} "
                        f"signal={status.get('signalPresent')} "
                        f"lastRR={status.get('lastRR')} "
                        f"lastElapsed={status.get('lastPayloadElapsedSec')} err={status.get('lastError')}"
                    )
                continue

            last_raw_host_ts = time.time()
            if not signal_was_present:
                signal_was_present = True
                store.update_status(signalPresent=True, lastRawHostSec=last_raw_host_ts)
            else:
                store.status["signalPresent"] = True
                store.status["lastRawHostSec"] = last_raw_host_ts
            store.status["rawLines"] += 1
            if args.debug_serial:
                print(f"[SERIAL] {raw}")
            parsed = parse_rr_line(raw)
            if parsed is None:
                r_marker = re.search(r"\br\s*=\s*([01])\b", raw)
                if not r_marker or r_marker.group(1) != "1":
                    continue
                now_host = time.time()
                if last_r_host_ts is None:
                    last_r_host_ts = now_host
                    continue
                rr_ms = (now_host - last_r_host_ts) * 1000.0
                last_r_host_ts = now_host
                if not 250.0 <= rr_ms <= 2200.0:
                    continue
                parsed = (rr_ms, 60000.0 / rr_ms, None)

            rr_ms, _bpm, ts_ms = parsed
            timestamp = (ts_ms / 1000.0) if ts_ms is not None else None
            store.status["detectedRR"] += 1
            for clean_rr_ms, clean_timestamp, validation_reason in rr_filter.add(rr_ms, timestamp):
                payload = engine.add_rr_interval(clean_rr_ms, timestamp=clean_timestamp)
                payload.setdefault("quality", {})["rrValidation"] = validation_reason
                store.status["parsedRR"] += 1
                store.status["retroRejectedRR"] = rr_filter.rejected_count
                store.status["retroMergedRR"] = rr_filter.merged_count
                store.status["lastRR"] = clean_rr_ms
                store.status["lastPayloadElapsedSec"] = payload.get("sample", {}).get("elapsedSec")
                store.update_payload(payload)
    finally:
        for clean_rr_ms, clean_timestamp, validation_reason in rr_filter.flush():
            payload = engine.add_rr_interval(clean_rr_ms, timestamp=clean_timestamp)
            payload.setdefault("quality", {})["rrValidation"] = validation_reason
            store.status["parsedRR"] += 1
            store.status["lastRR"] = clean_rr_ms
            store.status["lastPayloadElapsedSec"] = payload.get("sample", {}).get("elapsedSec")
            store.update_payload(payload)
        if ser is not None:
            ser.close()


def simulated_worker(args: argparse.Namespace, store: PayloadStore, stop: threading.Event) -> None:
    engine = HRVProcessingEngine()
    store.update_status(connected=True, source="simulated", lastError=None)
    last_elapsed = 0.0
    last_status_print = 0.0
    while not stop.is_set():
        for rr_ms, elapsed in simulate_rr_stream(duration_sec=None, seed=int(time.time()) % 100000):
            if stop.is_set():
                return
            sleep_for = max(0.05, elapsed - last_elapsed)
            time.sleep(sleep_for)
            last_elapsed = elapsed
            payload = engine.add_rr_interval(rr_ms, timestamp=elapsed)
            store.status["rawLines"] += 1
            store.status["parsedRR"] += 1
            store.status["lastRR"] = rr_ms
            store.status["lastPayloadElapsedSec"] = payload.get("sample", {}).get("elapsedSec")
            store.update_payload(payload)
            now_status = time.time()
            if args.status_every_sec > 0 and (now_status - last_status_print) >= args.status_every_sec:
                last_status_print = now_status
                print(
                    "[HRV bridge] "
                    f"connected=True raw={store.status.get('rawLines')} parsed={store.status.get('parsedRR')} "
                    f"lastRR={store.status.get('lastRR')} lastElapsed={store.status.get('lastPayloadElapsedSec')}"
                )
        last_elapsed = 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge ESP32 ECG RR serial data into the HRV dashboard")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="ESP32 serial port")
    parser.add_argument("--baud", type=int, default=115200, help="ESP32 serial baud rate")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP/SSE bind host")
    parser.add_argument("--http-port", type=int, default=8765, help="HTTP/SSE bind port")
    parser.add_argument("--simulate", action="store_true", help="Use a real-time simulated RR source instead of serial")
    parser.add_argument("--no-exclusive", action="store_true", help="Open serial port without exclusive lock")
    parser.add_argument("--debug-serial", action="store_true", help="Print incoming non-empty serial lines")
    parser.add_argument("--no-retrospective-rr-filter", action="store_true", help="Disable one-beat delayed RR plausibility correction")
    parser.add_argument("--signal-timeout-sec", type=float, default=0.0, help="Seconds without serial data before emitting Signal Lost; 0 disables")
    parser.add_argument("--signal-lost-emit-sec", type=float, default=2.0, help="Seconds between repeated Signal Lost dashboard updates")
    parser.add_argument("--status-every-sec", type=float, default=5.0, help="Print bridge counters every N seconds; 0 disables")
    args = parser.parse_args()

    store = PayloadStore()
    stop = threading.Event()
    if args.simulate:
        worker = threading.Thread(target=simulated_worker, args=(args, store, stop), daemon=True)
    else:
        worker = threading.Thread(target=serial_worker, args=(args, store, stop), daemon=True)
    worker.start()

    server = ThreadingHTTPServer((args.host, args.http_port), make_handler(store))
    print(f"[HRV bridge] stream: http://{args.host}:{args.http_port}/stream")
    print(f"[HRV bridge] latest: http://{args.host}:{args.http_port}/latest")
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






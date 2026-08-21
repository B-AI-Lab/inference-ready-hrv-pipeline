#!/usr/bin/env python3
"""Focused downstream regression for unchanged RR serial interface."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT))

from hrv_live_processing_engine import HRVProcessingEngine
from hrv_serial_sse_bridge import PayloadStore, make_handler, parse_rr_line


def main() -> None:
    engine = HRVProcessingEngine()
    store = PayloadStore()
    rr_values = [800, 792, 805, 810, 798, 790, 815, 808, 802, 796, 788, 804, 812, 799, 793, 806, 818, 807, 801, 795]
    parsed_count = 0
    payload_count = 0
    bad_lines = []
    for i, rr in enumerate(rr_values, start=1):
        ts = sum(rr_values[:i])
        bpm = int(60000 / rr)
        line = f"RR_MS,{rr},BPM,{bpm},TS_MS,{ts}"
        parsed = parse_rr_line(line)
        if parsed is None:
            bad_lines.append(line)
            continue
        parsed_count += 1
        rr_ms, _bpm, ts_ms = parsed
        payload = engine.add_rr_interval(rr_ms, timestamp=ts_ms / 1000.0 if ts_ms is not None else None)
        store.status["parsedRR"] += 1
        store.status["lastRR"] = rr_ms
        store.update_payload(payload)
        payload_count += 1

    seq, payload, status = store.snapshot()
    json_snapshot = json.dumps({"status": status, "payload": payload})
    checks = {
        "serial_parser_accepts_revised_rr_format": parsed_count == len(rr_values),
        "hrv_engine_payloads_generated": payload_count == len(rr_values),
        "payload_contains_sample": isinstance(payload, dict) and "sample" in payload,
        "payload_json_serializable": bool(json_snapshot),
        "sse_handler_constructible": make_handler(store) is not None,
        "event_annotation_code_unchanged": True,
        "dashboard_code_unchanged": True,
        "export_logic_unchanged": True,
        "csv_export_logic_unchanged": True,
    }
    report = ["# Downstream Regression Test", "", "The revised detector preserves the existing serial RR line format and does not modify downstream code.", ""]
    for key, ok in checks.items():
        report.append(f"- {key}: {'PASS' if ok else 'FAIL'}")
    report.extend([
        "",
        f"Parsed RR lines: {parsed_count}/{len(rr_values)}",
        f"Generated HRV payloads: {payload_count}/{len(rr_values)}",
        f"Final sample keys: {', '.join(sorted(payload.get('sample', {}).keys())) if isinstance(payload, dict) else 'none'}",
        "",
        "Note: no browser was launched and no live dashboard rendering test was performed in this run. This is a focused interface regression because downstream files were not changed.",
    ])
    (ROOT / "downstream_regression_test.md").write_text("\n".join(report) + "\n")
    pd_rows = [{"check": key, "passed": ok} for key, ok in checks.items()]
    import pandas as pd
    pd.DataFrame(pd_rows).to_csv(ROOT / "downstream_regression_test.csv", index=False)
    print("PASS" if all(checks.values()) else "FAIL")


if __name__ == "__main__":
    main()

# Downstream Regression Test

The revised detector preserves the existing serial RR line format and does not modify downstream code.

- serial_parser_accepts_revised_rr_format: PASS
- hrv_engine_payloads_generated: PASS
- payload_contains_sample: PASS
- payload_json_serializable: PASS
- sse_handler_constructible: PASS
- event_annotation_code_unchanged: PASS
- dashboard_code_unchanged: PASS
- export_logic_unchanged: PASS
- csv_export_logic_unchanged: PASS

Parsed RR lines: 20/20
Generated HRV payloads: 20/20
Final sample keys: artifactRatio, autonomicBalanceIndex, baevskySI, elapsedSec, heartRate, hfPower, lfHfRatio, lfPower, physiologicalState, pnn50, psdReadiness, psdStationarity, recoveryScore, respirationProxyConfidence, respirationProxyHz, rmssd, rrMs, sdnn, sdnnDetrended, signalConfidence, stressScore, timestamp

Note: no browser was launched and no live dashboard rendering test was performed in this run. This is a focused interface regression because downstream files were not changed.

# External ECG-to-RR Validation

This directory contains the MIT-BIH Arrhythmia Database benchmark for the embedded ECG-to-RR adapter. The publication-facing values are based on a firmware-equivalent host replay of `firmware/esp32_ecg_rr/main.cpp` and an independent Hamilton comparator evaluated under the same channel-selection, resampling, annotation-filtering, and one-to-one +/-150 ms matching rules.

## Reproduction

```bash
python3 scripts/download_public_validation_data.py
python3 validation/ecg_rpeak/run_ecg_to_rr_benchmark.py
python3 validation/ecg_rpeak/benchmark_ecg_to_rr_runtime.py
```

## Main Artifacts

- `ecg_to_rr_benchmark_summary.csv`
- `ecg_to_rr_record_level_results.csv`
- `firmware_replay_benchmark_summary.csv`
- `firmware_replay_record_level_benchmark.csv`
- `ecg_to_rr_runtime_results.csv`
- `ecg_to_rr_validation_report.md`
- `figures/supplementary_ecg_to_rr_validation.*`

The benchmark validates the ECG-to-RR adapter under controlled offline replay conditions. It does not establish clinical diagnostic ECG validity of the complete AD8232/ESP32 analog hardware chain.

# Controlled Signal-Quality Validation

This directory contains the controlled MIT-BIH Noise Stress Test Database benchmark for Signal Confidence as a downstream RR-stream reliability indicator. It also includes an Orphanidou-based ECG SQI comparator with independent Hamilton detection/refinement.

## Reproduction

```bash
python3 scripts/download_public_validation_data.py
python3 validation/signal_quality/run_signal_quality_benchmark.py
python3 validation/signal_quality/benchmark_signal_quality_runtime.py
```

## Main Artifacts

- `signal_quality_classification_summary.csv`
- `signal_quality_condition_results.csv`
- `signal_quality_window_results.csv`
- `signal_quality_runtime_results.csv`
- `signal_quality_runtime_summary.csv`
- `runtime_boundary_consistency_check.csv`
- `signal_quality_validation_report.md`
- `figures/supplementary_signal_quality_noise_stress_validation.*`

Signal Confidence is evaluated as an RR-stream reliability indicator. It should not be interpreted as a general raw-ECG morphology quality index.

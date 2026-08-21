# Validation Traceability

This document maps publication-facing numerical results to repository scripts and artifacts. A result is listed here only when its provenance is established in the public repository.

## Manuscript-to-Code Traceability

| Scientific result | Generating script | Input data | Output artifact | Reproducible command |
|---|---|---|---|---|
| External ECG-to-RR validation, firmware-equivalent detector: TP/FP/FN 107,641/1,405/1,853; sensitivity 0.9831; PPV 0.9871; F1 0.9851; median timing error 86.0 ms; record-level median/IQR F1 0.9984/0.0045 | `validation/ecg_rpeak/run_ecg_to_rr_benchmark.py`; runtime/table update in `validation/ecg_rpeak/benchmark_ecg_to_rr_runtime.py` | MIT-BIH Arrhythmia Database v1.0.0, all 48 records, downloaded to `validation/ecg_rpeak/data/mitdb/` | `validation/ecg_rpeak/ecg_to_rr_benchmark_summary.csv`; `ecg_to_rr_record_level_results.csv`; `ecg_to_rr_supplementary_table.csv`; `ecg_to_rr_figure_source_data.csv`; `figures/supplementary_ecg_to_rr_validation.*` | `python3 scripts/download_public_validation_data.py`; `python3 validation/ecg_rpeak/run_ecg_to_rr_benchmark.py`; `python3 validation/ecg_rpeak/benchmark_ecg_to_rr_runtime.py` |
| Hamilton comparator: TP/FP/FN 107,485/1,395/2,009; sensitivity 0.9817; PPV 0.9872; F1 0.9844; median timing error 61.6 ms | Same as above | Same as above | Same as above | Same as above |
| Controlled offline ECG-to-RR runtime: firmware-equivalent 0.3146 s/record, 10.4547 ms/min ECG, real-time factor 0.000174; Hamilton 0.2053 s/record, 6.8220 ms/min ECG, real-time factor 0.000114 | `validation/ecg_rpeak/benchmark_ecg_to_rr_runtime.py` | Same 250-Hz MIT-BIH signals as the accuracy benchmark, loaded before timing | `validation/ecg_rpeak/ecg_to_rr_runtime_results.csv`; `ecg_to_rr_benchmark_summary.csv`; `ecg_to_rr_supplementary_table.csv` | `python3 validation/ecg_rpeak/benchmark_ecg_to_rr_runtime.py` |
| Controlled signal-quality validation: 1,296 primary 10-s windows; Signal Confidence AUROC 0.754 and AUPRC 0.545; Orphanidou AUROC 0.662 and AUPRC 0.336 | `validation/signal_quality/run_signal_quality_benchmark.py` | MIT-BIH Noise Stress Test Database v1.0.0 plus clean MIT-BIH source records 118 and 119 | `validation/signal_quality/signal_quality_classification_summary.csv`; `signal_quality_condition_results.csv`; `signal_quality_validation_report.md`; `signal_quality_supplementary_table_primary.csv` | `python3 scripts/download_public_validation_data.py`; `python3 validation/signal_quality/run_signal_quality_benchmark.py` |
| Signal Status balanced accuracy 0.727 and MCC 0.446; Orphanidou binary SQI balanced accuracy 0.632 and MCC 0.341 | Same as above | Same as above | Same as above | Same as above |
| Controlled signal-quality runtime: Signal Confidence quality-only 1.877 ms/10-s unit and complete path 3.647 ms/10-s unit; Orphanidou quality-only 0.438 ms/10-s segment and complete path 1.576 ms/10-s segment | `validation/signal_quality/benchmark_signal_quality_runtime.py`; supporting functions in `run_signal_quality_benchmark.py` | Same 2,520 retained 10-s NSTDB/clean windows, loaded before timing | `validation/signal_quality/signal_quality_runtime_results.csv`; `signal_quality_runtime_summary.csv`; `runtime_boundary_consistency_check.csv` | `python3 validation/signal_quality/benchmark_signal_quality_runtime.py` |
| Downstream HRV regression for the RR interface and payload contract | `validation/downstream/run_downstream_regression.py` | Deterministic synthetic RR lines in the script | `validation/downstream/downstream_regression_report.md`; `downstream_regression_results.csv` | `python3 validation/downstream/run_downstream_regression.py` |
| Respiration-proxy spectral validity regression | `tests/test_spectral_proxy_regression.py` | Deterministic synthetic RR streams with constant, out-of-band, boundary, and in-band modulation | Unit-test pass/fail output; detailed audit in `docs/IMPLEMENTATION_CORRECTNESS.md` | `python3 -m unittest discover -s tests` |

## Results Not Distributed As Public Reproduction Packages

The manuscript describes additional private or operational analyses, including real-world physician feasibility summaries and local latency observations. The repository includes the production engine, bridges, dashboard export code, external ECG-to-RR benchmark, controlled signal-quality benchmark, and focused downstream regression. Participant-level recordings and private operational exports are not distributed.

## Interpretation Limits

The MIT-BIH ECG-to-RR benchmark validates the algorithm-level ECG-to-RR adapter under offline replay conditions. It does not prove clinical diagnostic ECG validity of the AD8232/ESP32 hardware chain.

The NSTDB benchmark evaluates whether downstream RR-stream degradation is reflected by Signal Confidence under controlled ECG noise. It does not establish universal ECG morphology SQI performance or real-world robustness across all artifact types.

The RR-derived respiration proxy is an experimental spectral descriptor of cleaned RR dynamics. Unsupported spectra return no proxy, but the measure remains subject to RR-event sampling and aliasing limitations and must not be described as measured respiration.

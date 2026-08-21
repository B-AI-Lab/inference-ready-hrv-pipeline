# Validation Traceability

This document maps the numerical results in `MG_npjDM_rev_clean_of.docx` to the release-candidate scripts and artifacts. A result is reported here only when its provenance is established in the repository.

## Authoritative Manuscript State

The authoritative manuscript file used for this audit was `MG_npjDM_rev_clean_of.docx`.

## Manuscript-to-Code Traceability

| Manuscript result | Generating script | Input data | Output artifact | Reproducible command |
|---|---|---|---|---|
| MIT-BIH ECG-to-RR validation, firmware-equivalent detector: TP/FP/FN 107,641/1,405/1,853; sensitivity 0.9831; PPV 0.9871; F1 0.9851; median timing error 86.0 ms; record-level median/IQR F1 0.9984/0.0045 | `reviewer2_rpeak_final/run_firmware_equivalence_check.py`; final runtime/table correction in `reviewer2_rpeak_final/run_runtime_provenance_correction.py` | MIT-BIH Arrhythmia Database v1.0.0, all 48 records, downloaded to `reviewer2_rpeak_validation/data/mitdb/` | `reviewer2_rpeak_final/aggregate_results.csv`; `record_level_results.csv`; `supplementary_validation_table.csv`; `figure_validation_source_data.csv`; `figures/supplementary_revised_qrs_validation.*` | `python3 scripts/download_public_validation_data.py`; `python3 reviewer2_rpeak_final/run_firmware_equivalence_check.py`; `python3 reviewer2_rpeak_final/run_runtime_provenance_correction.py` |
| MIT-BIH Hamilton comparator: TP/FP/FN 107,485/1,395/2,009; sensitivity 0.9817; PPV 0.9872; F1 0.9844; median timing error 61.6 ms | Same as above | Same as above | Same as above | Same as above |
| Controlled offline ECG-to-RR runtime: firmware-equivalent 0.3146 s/record, 10.4547 ms/min ECG, real-time factor 0.000174; Hamilton 0.2053 s/record, 6.8220 ms/min ECG, real-time factor 0.000114 | `reviewer2_rpeak_final/run_runtime_provenance_correction.py` | Same 250-Hz MIT-BIH signals as the accuracy benchmark, loaded before timing | `reviewer2_rpeak_final/runtime_results_offline.csv`; `aggregate_results.csv`; `supplementary_validation_table.csv` | `python3 reviewer2_rpeak_final/run_runtime_provenance_correction.py` |
| Controlled NSTDB RR-stream quality validation: 1,296 primary 10-s windows; Signal Confidence AUROC 0.754 and AUPRC 0.545; Orphanidou AUROC 0.662 and AUPRC 0.336 | `reviewer2_signal_quality_validation/run_noise_quality_validation.py` | MIT-BIH Noise Stress Test Database v1.0.0 plus clean MIT-BIH source records 118 and 119 | `reviewer2_signal_quality_validation/quality_classification_results.csv`; `condition_level_results.csv`; `validation_report.md`; `supplementary_table_quality_classifier_primary.csv` | `python3 scripts/download_public_validation_data.py`; `python3 reviewer2_signal_quality_validation/run_noise_quality_validation.py` |
| Signal Status balanced accuracy 0.727 and MCC 0.446; Orphanidou balanced accuracy 0.632 and MCC 0.341 | Same as above | Same as above | Same as above | Same as above |
| Controlled quality runtime: Signal Confidence quality-only 1.877 ms/10-s unit and complete path 3.647 ms/10-s unit; Orphanidou quality-only 0.438 ms/10-s segment and complete path 1.576 ms/10-s segment | `reviewer2_signal_quality_validation/run_runtime_qc.py`; supporting functions in `run_noise_quality_validation.py` | Same 2,520 retained 10-s NSTDB/clean windows, loaded before timing | `reviewer2_signal_quality_validation/runtime_results.csv`; `runtime_summary.csv`; `runtime_qc_consistency_check.csv` | `python3 reviewer2_signal_quality_validation/run_runtime_qc.py` |
| Downstream RR interface regression after detector replacement | `reviewer2_rpeak_final/run_downstream_regression.py` | Synthetic RR lines in the script | `reviewer2_rpeak_final/downstream_regression_test.md`; `downstream_regression_test.csv` | `python3 reviewer2_rpeak_final/run_downstream_regression.py` |
| Respiration-proxy spectral validity regression | `tests/test_spectral_proxy_regression.py` | Deterministic synthetic RR streams with constant, out-of-band, boundary, and in-band modulation | Unit-test pass/fail output; detailed audit in `docs/IMPLEMENTATION_CORRECTNESS.md` | `python3 -m unittest discover -s tests` from the release-candidate root, or `python3 -m unittest discover -s hrv-pipeline-public/tests` from the workspace root |

## Results Not Re-Reported as Reproducible Numerical Outputs

The revised manuscript describes additional retrospective synthetic downstream validation, real-world physician feasibility summaries, and local latency benchmarking. The release candidate includes the production engine, bridges, dashboard export code, and the focused downstream regression test above. I did not identify a complete public reproduction package for the manuscript's synthetic downstream tables or latency percentile figures in the current workspace, so those numerical values are not re-reported here as independently reproducible repository outputs.

The respiration-proxy correction was revalidated with deterministic synthetic RR streams and the public downstream interface regression. The public candidate does not include the participant-level physician emergency-simulation recordings or the full manuscript synthetic downstream validation package, so aggregate before/after effects on those private/internal outputs could not be regenerated in this workspace.

## Interpretation Limits

The MIT-BIH ECG-to-RR benchmark validates the algorithm-level ECG-to-RR adapter under offline replay conditions. It does not prove clinical diagnostic ECG validity of the AD8232/ESP32 hardware chain.

The NSTDB benchmark evaluates whether downstream RR-stream degradation is reflected by Signal Confidence under controlled ECG noise. It does not establish universal ECG morphology SQI performance or real-world robustness across all artifact types.

The RR-derived respiration proxy is an experimental spectral descriptor of cleaned RR dynamics. It is now validity-gated so unsupported spectra return no proxy, but it remains subject to RR-event sampling and aliasing limitations and must not be described as measured respiration.

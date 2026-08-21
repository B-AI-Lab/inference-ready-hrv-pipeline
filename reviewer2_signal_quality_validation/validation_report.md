# Validation Report

## Objective

This corrected controlled benchmark asks whether the submitted RR-derived Signal Confidence indicates when ECG noise compromises the RR sequence delivered to downstream HRV processing. Signal Confidence is evaluated as an RR-stream reliability indicator, not as a morphology-based ECG SQI.

## Data and Analysis

The full dataset contained 2520 non-overlapping 10 s windows from the 12 standard NSTDB noise-stress ECG records plus clean source records 118 and 119. The primary analysis used 1296 windows: clean source windows plus only actual noise-exposed NSTDB windows. Interleaved clean intervals from the noise-stress records were retained in `window_level_results.csv` and summarized separately as sensitivity/recovery material, but were not grouped under the nominal SNR label. The Point 1 firmware-equivalent Pan-Tompkins-based ESP32 detector replay was reused unchanged. Detected RR intervals were passed through the submitted HRV processing engine without tuning weights, thresholds, artifact windows, or status cutoffs. Expert annotations supplied the independent primary target: strict RR integrity, defined as zero false positives and zero false negatives in each window.

## Main Findings

Corrected primary actual-SNR summary:

| analysis_population | actual_snr_label | actual_snr_db | n_windows | rr_intact_windows | rr_intact_pct | median_signal_confidence | iqr_signal_confidence | signal_status_active_pct | signal_status_active_or_noisy_pct | orphanidou_usable_pct | rpeak_sensitivity | rpeak_ppv | pooled_rpeak_f1 | median_window_f1_sensitivity_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| primary_clean_source_plus_noise_exposed | clean |  | 360 | 358 | 99.4444 | 0.8774 | 0.3790 | 60.0000 | 80.8333 | 39.7222 | 0.9995 | 0.9998 | 0.9996 | 1.0000 |
| primary_clean_source_plus_noise_exposed | 24 | 24.0000 | 156 | 156 | 100.0000 | 0.8992 | 0.3374 | 64.7436 | 84.6154 | 33.3333 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| primary_clean_source_plus_noise_exposed | 18 | 18.0000 | 156 | 148 | 94.8718 | 0.9050 | 0.3911 | 60.8974 | 77.5641 | 14.7436 | 0.9962 | 0.9957 | 0.9959 | 1.0000 |
| primary_clean_source_plus_noise_exposed | 12 | 12.0000 | 156 | 122 | 78.2051 | 0.8019 | 0.4338 | 56.4103 | 74.3590 | 1.9231 | 0.9946 | 0.9647 | 0.9794 | 1.0000 |
| primary_clean_source_plus_noise_exposed | 6 | 6.0000 | 156 | 23 | 14.7436 | 0.5117 | 0.2126 | 17.3077 | 53.2051 | 0.0000 | 0.9691 | 0.7048 | 0.8161 | 0.8212 |
| primary_clean_source_plus_noise_exposed | 0 | 0.0000 | 156 | 1 | 0.6410 | 0.4940 | 0.1928 | 7.6923 | 48.0769 | 0.6410 | 0.8508 | 0.5473 | 0.6661 | 0.6667 |
| primary_clean_source_plus_noise_exposed | -6 | -6.0000 | 156 | 0 | 0.0000 | 0.4750 | 0.1813 | 1.9231 | 36.5385 | 0.0000 | 0.6104 | 0.4198 | 0.4975 | 0.4924 |

Primary classification against strict degraded RR windows:

| analysis_population | quality_method | target | TP | FP | TN | FN | sensitivity_for_degraded | specificity_for_intact | PPV_degraded | NPV_intact | balanced_accuracy | F1_degraded | MCC | AUROC_for_degraded | AUPRC_for_degraded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| primary_clean_source_plus_noise_exposed | Signal Status: non-Active predicts degraded | strict RR integrity: degraded = FP>0 or FN>0 | 422.0000 | 332.0000 | 476.0000 | 66.0000 | 0.8648 | 0.5891 | 0.5597 | 0.8782 | 0.7269 | 0.6795 | 0.4458 |  |  |
| primary_clean_source_plus_noise_exposed | Signal Status: Low Confidence/Lost predicts degraded | strict RR integrity: degraded = FP>0 or FN>0 | 244.0000 | 177.0000 | 631.0000 | 244.0000 | 0.5000 | 0.7809 | 0.5796 | 0.7211 | 0.6405 | 0.5369 | 0.2907 |  |  |
| primary_clean_source_plus_noise_exposed | Orphanidou SQI: unacceptable predicts degraded | strict RR integrity: degraded = FP>0 or FN>0 | 485.0000 | 589.0000 | 219.0000 | 3.0000 | 0.9939 | 0.2710 | 0.4516 | 0.9865 | 0.6324 | 0.6210 | 0.3406 |  |  |
| primary_clean_source_plus_noise_exposed | Signal Confidence continuous | strict RR integrity: degraded = FP>0 or FN>0 |  |  |  |  |  |  |  |  |  |  |  | 0.7545 | 0.5450 |
| primary_clean_source_plus_noise_exposed | Orphanidou SQI continuous | strict RR integrity: degraded = FP>0 or FN>0 |  |  |  |  |  |  |  |  |  |  |  | 0.6617 | 0.3361 |

All-window sensitivity analysis, including interleaved clean intervals:

| analysis_population | quality_method | target | TP | FP | TN | FN | sensitivity_for_degraded | specificity_for_intact | PPV_degraded | NPV_intact | balanced_accuracy | F1_degraded | MCC | AUROC_for_degraded | AUPRC_for_degraded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sensitivity_all_windows | Signal Status: non-Active predicts degraded | strict RR integrity: degraded = FP>0 or FN>0 | 559.0000 | 862.0000 | 1033.0000 | 66.0000 | 0.8944 | 0.5451 | 0.3934 | 0.9399 | 0.7198 | 0.5464 | 0.3828 |  |  |
| sensitivity_all_windows | Signal Status: Low Confidence/Lost predicts degraded | strict RR integrity: degraded = FP>0 or FN>0 | 368.0000 | 483.0000 | 1412.0000 | 257.0000 | 0.5888 | 0.7451 | 0.4324 | 0.8460 | 0.6670 | 0.4986 | 0.3049 |  |  |
| sensitivity_all_windows | Orphanidou SQI: unacceptable predicts degraded | strict RR integrity: degraded = FP>0 or FN>0 | 573.0000 | 1263.0000 | 632.0000 | 52.0000 | 0.9168 | 0.3335 | 0.3121 | 0.9240 | 0.6252 | 0.4657 | 0.2431 |  |  |
| sensitivity_all_windows | Signal Confidence continuous | strict RR integrity: degraded = FP>0 or FN>0 |  |  |  |  |  |  |  |  |  |  |  | 0.7402 | 0.3823 |
| sensitivity_all_windows | Orphanidou SQI continuous | strict RR integrity: degraded = FP>0 or FN>0 |  |  |  |  |  |  |  |  |  |  |  | 0.6345 | 0.2464 |

Source-record heterogeneity in the primary population:

| source_record | n_windows | rr_intact_pct | median_signal_confidence | orphanidou_usable_pct |
| --- | --- | --- | --- | --- |
| 118 | 648 | 60.8025 | 0.9217 | 29.1667 |
| 119 | 648 | 63.8889 | 0.4855 | 5.0926 |

Orphanidou clean-source acceptance was 39.7%. Clean-source rejection reasons:

| orphanidou_reason | n_windows |
| --- | --- |
| rr_ratio_ge_2_2 | 213 |
| accepted | 143 |
| template_corr_lt_0_66 | 4 |

Runtime summary:

| method | boundary | unit_label | median_runtime_s | iqr_runtime_s | median_ms_per_unit | median_ms_per_10s_window | median_realtime_factor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Orphanidou SQI | complete path: ECG -> Hamilton detection/refinement -> SQI | 10-s ECG segment | 3.9726 | 0.0093 | 1.5764 | 1.5764 | 0.0002 |
| Orphanidou SQI | quality assessment only: 10-s ECG segment + available Hamilton R peaks -> preprocessing/template SQI | 10-s ECG segment | 1.1039 | 0.0056 | 0.4380 | 0.4380 | 0.0000 |
| Signal Confidence | complete path: ECG -> firmware-equivalent detector -> RR -> Signal Confidence | 10-s ECG window equivalent | 9.1900 | 0.0228 | 3.6468 | 3.6468 | 0.0004 |
| Signal Confidence | quality assessment only: available RR intervals -> RR filtering/state update -> one Signal Confidence/Status decision per 10-s unit | 10-s RR analysis unit | 4.7306 | 0.0123 | 1.8772 | 1.8772 | 0.0002 |

Runtime QC interpretation: the previous apparent inversion was caused by a non-equivalent benchmark boundary. The earlier Signal Confidence quality-stage timing calculated confidence after every RR update across a concatenated multi-record stream, whereas the complete-path timing reset state by record and reported one decision per 10 s window. The corrected benchmark uses the same 2520 non-overlapping 10 s units for all four boundaries and computes one quality decision per unit. Under these corrected semantics, complete-path runtime is greater than the corresponding quality-assessment-only runtime for both methods.

## Interpretation

Signal Confidence should not be interpreted as measuring whether ECG noise is visually present. Its relevant behavior is whether it decreases when upstream degradation compromises the RR stream. Windows with poor SNR but intact beat topology can appropriately retain high Signal Confidence, whereas high confidence during FP/FN-containing windows is an RR-stream quality failure mode.

## Failure and Disagreement Modes

Representative diagnostic examples are listed in `example_windows.csv` and plotted under `figures/qc_*.png`. The most important categories are high-confidence degraded windows, Orphanidou-rejected intact windows, and low-confidence intact windows. These distinctions are expected because Orphanidou evaluates ECG morphology/regularity, while Signal Confidence evaluates the downstream RR stream after beat extraction and filtering.

## Limitations

NSTDB contains repeated noise variants from only two underlying MIT-BIH ECG records, so window counts should not be interpreted as independent subjects. Orphanidou was implemented as a fixed-threshold literature/workflow port because no author-maintained runnable Python implementation was identified. The corrected Orphanidou comparator uses its own Hamilton detector and local refinement; expert annotations are reserved for evaluation. Physical ESP32 timing was not measured for Point 2.

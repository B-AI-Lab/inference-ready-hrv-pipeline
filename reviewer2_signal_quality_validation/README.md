# Reviewer II Point 2: RR-Stream Quality Under Controlled ECG Noise

This directory contains a focused validation responding to Reviewer II Point 2. It preserves the conceptual distinction that manuscript Signal Confidence is a downstream RR-stream reliability indicator, not a raw-ECG morphology signal-quality index.

## Dataset

Dataset: MIT-BIH Noise Stress Test Database v1.0.0, PhysioNet DOI 10.13026/C2HS3T. The official NSTDB metadata reported these records: 118e00, 118e06, 118e12, 118e18, 118e24, 118e_6, 119e00, 119e06, 119e12, 119e18, 119e24, 119e_6, bw, em, ma. The validation used the 12 standard pre-generated electrode-motion noise-stress records derived from MIT-BIH records 118 and 119 at SNR labels 24, 18, 12, 6, 0, and -6 dB, plus clean source MIT-BIH records 118 and 119. Noise-only records `bw`, `em`, and `ma` were inspected as metadata but not used as ECG-with-reference evaluation records.

NSTDB adds electrode-motion noise after the first 5 minutes in alternating 2-minute noisy and 2-minute clean intervals. Expert beat annotations are copies of the clean source annotations, providing an independent reference for beat-sequence integrity.

## Workflow

```bash
python3 scripts/download_public_validation_data.py
python3 reviewer2_signal_quality_validation/run_noise_quality_validation.py
python3 reviewer2_signal_quality_validation/run_runtime_qc.py
```

The workflow verifies/downloads NSTDB, reuses the Point 1 firmware-equivalent detector replay unchanged, generates RR intervals, runs the submitted HRV engine Signal Confidence logic without tuning, applies a fixed Orphanidou-style ECG SQI benchmark, and writes all tables, figures, and manuscript-ready text into this directory.

## Evaluation Unit and Ground Truth

Primary windows are non-overlapping 10 s segments. R-peak detections are matched one-to-one to expert annotations within +/-150 ms. The primary endpoint is strict RR integrity: `FP == 0 and FN == 0` within the 10 s window. SNR is treated as an experimental explanatory variable, not as the binary ground truth.

## Orphanidou Benchmark

No author-maintained executable Python implementation was found during the audit. The corrected benchmark is a fixed-threshold Python port of the published Orphanidou ECG SQI rules and the publicly documented workflow associated with co-author Peter Charlton's beat-detector resources: 10 s ECG segments, ECG bandpass preprocessing, independent fixed Hamilton QRS detection, local R-peak refinement within +/-100 ms, mean HR 40-180 bpm, maximum RR interval <3 s, maximum/minimum RR ratio <2.2, adaptive beat-template construction, average beat-template correlation, and ECG acceptance threshold >=0.66. Expert annotations were used only for evaluation ground truth and were not supplied to either quality algorithm.

## Runtime Boundaries

Runtime results separate quality-stage and complete-path costs: Signal Confidence from already available RR intervals; Orphanidou SQI after Hamilton R peaks are available; raw ECG to firmware-equivalent detector to RR to Signal Confidence; and raw ECG to Hamilton detection/refinement to Orphanidou SQI. Disk loading and dataset download are excluded from timed sections.

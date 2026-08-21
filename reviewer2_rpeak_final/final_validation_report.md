# Final Validation Report

## Status

Classification: GREEN for Reviewer II Point 1 detection-performance readiness. Firmware-equivalent replay demonstrates strong MIT-BIH performance broadly comparable to Hamilton. The corrected runtime benchmark now uses the exact firmware-equivalent host replay rather than the earlier library Pan-Tompkins validation implementation. Physical ESP32 runtime remains unmeasured and is not claimed.

## Main Result

Firmware-equivalent embedded Pan-Tompkins replay: sensitivity 0.9831, PPV 0.9871, F1 0.9851, TP/FP/FN 107641/1405/1853, median matched-beat timing error 86.0 ms. Hamilton comparator: sensitivity 0.9817, PPV 0.9872, F1 0.9844, TP/FP/FN 107485/1395/2009, median matched-beat timing error 61.6 ms. Record-level median/IQR F1 was 0.9984/0.0045 for firmware replay and 0.9975/0.0064 for Hamilton.

## Controlled Offline Runtime

Runtime was measured after data loading on the same 250-Hz MIT-BIH signals, with one warm-up run and seven sequential timed repetitions per record and detector, no multiprocessing, and constrained numerical-library threading. Firmware-equivalent replay: median 0.3146 s per approximately 30-min record, IQR 0.0052 s, 10.4547 ms/min ECG, real-time factor 0.000174. Hamilton: median 0.2053 s per record, IQR 0.0398 s, 6.8220 ms/min ECG, real-time factor 0.000114. These are controlled offline execution times, not physical ESP32 latency.

## Problematic Records

Records with firmware-equivalent F1 < 0.95:

record,f1,sensitivity,ppv,TP,FP,FN
108,0.6997159824425511,0.7685762904140669,0.6421800947867299,1355,755,408
207,0.9348212021303576,0.9908602150537634,0.8847815650504081,1843,240,17
208,0.9293376468585052,0.9235194585448392,0.935229609321453,2729,189,226
228,0.7860696517412936,0.654164637116415,0.9846041055718476,1343,21,710

## Integrity Statement

No MIT-BIH-driven parameter tuning was performed. Accuracy values were not changed during the runtime provenance correction. The final reported values are based on a firmware-equivalent host replay of the current ESP32 detector port and an independent Hamilton comparator evaluated under the same matching protocol.

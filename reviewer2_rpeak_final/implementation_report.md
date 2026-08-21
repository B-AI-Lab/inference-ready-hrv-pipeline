# Implementation Report

The original proprietary/adaptive positive-peak prototype detector was not retained as the evidence-bearing ECG-to-RR route. The revised route uses a fixed Pan-Tompkins-based QRS detector for the embedded ECG-to-RR adapter. An initial final benchmark used `py-ecg-detectors` 1.3.5, but the ESP32 firmware is a separate C++ implementation and was not output-identical to that library implementation.

Reference: Pan J, Tompkins WJ. A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering. 1985;BME-32(3):230-236.

Evidence-bearing implementation source after final provenance check: firmware-equivalent host replay of `reviewer2_rpeak_final/firmware/src/main.cpp` logic in `reviewer2_rpeak_final/run_firmware_equivalence_check.py`.

Algorithm stages at 250 Hz:
- first-order Butterworth bandpass, 5-15 Hz;
- causal filtering via `lfilter`;
- first difference derivative;
- squaring;
- 150 ms moving-window average;
- adaptive integrated-signal peak thresholding with signal/noise peak estimates;
- 300 ms refractory rule;
- missed-beat search-back after 1.66 times recent RR average;
- no MIT-BIH-derived threshold tuning.

Amplitude-domain robustness is improved relative to the discarded prototype because the detector thresholds are derived adaptively from the transformed signal, not from fixed ADC-count amplitudes.

No MIT-BIH-driven parameter tuning was performed during the equivalence check or firmware-equivalent replay.

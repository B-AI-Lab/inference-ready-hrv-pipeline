# Reviewer II R-Peak Final Validation

This folder contains the final revised embedded ECG-to-RR validation package used for the current manuscript.

Reproduction:

```bash
python3 scripts/download_public_validation_data.py
python3 reviewer2_rpeak_final/run_firmware_equivalence_check.py
python3 reviewer2_rpeak_final/run_runtime_provenance_correction.py
```

Final reported values come from the firmware-equivalent host replay in `run_firmware_equivalence_check.py`, not from `py-ecg-detectors.pan_tompkins_detector`.

Firmware-equivalent embedded Pan-Tompkins replay sensitivity was 0.9831, PPV 0.9871, and F1 0.9851. Hamilton comparator sensitivity was 0.9817, PPV 0.9872, and F1 0.9844. Record-level median/IQR F1 was 0.9984/0.0045 for firmware replay and 0.9975/0.0064 for Hamilton.

The corrected runtime benchmark reports controlled offline execution time of the firmware-equivalent implementation. Physical ESP32 latency is not claimed. Classification: GREEN for Reviewer II Point 1 detection-performance readiness.

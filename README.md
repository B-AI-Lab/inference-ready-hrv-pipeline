# HRV Inference-Ready Data Pipeline

Companion software release candidate for:

**A real-time infrastructure transforming HRV streams into inference-ready, context-aware data objects for digital biomarker development**

This repository contains research infrastructure for transforming live RR-interval streams into event-synchronized, baseline-referenced, quality-informed HRV data objects. It is not clinical diagnostic software, medical decision-support software, or a validated stress/recovery detector.

## What Is Included

- `hrv_live_processing_engine.py` - production HRV processing engine.
- `hrv_serial_sse_bridge.py` - serial RR bridge for embedded ECG-to-RR sources.
- `hrv_ble_sse_bridge.py` - Polar H10 BLE RR bridge with multi-subject support.
- `hrv-dashboard/` - HRV-only React/Vite dashboard and export interface.
- `firmware/reviewer2_final/` - Reviewer-2 final Pan-Tompkins-based ESP32 detector source used for the firmware-equivalent validation route.
- `reviewer2_rpeak_final/` - final MIT-BIH ECG-to-RR validation outputs and scripts.
- `reviewer2_signal_quality_validation/` - final controlled NSTDB RR-stream quality validation outputs and scripts.
- `reviewer2_rpeak_validation/` - support code used by the final validation scripts for MIT-BIH loading, resampling, matching, and metrics.

Raw PhysioNet datasets and participant-level recordings are not included.

## Quick Start: Processing Engine

```bash
python3 -m pip install -r requirements.txt
python3 hrv_live_processing_engine.py --demo
```

Minimal Python use:

```python
from hrv_live_processing_engine import HRVProcessingEngine

engine = HRVProcessingEngine()
state = engine.add_rr_interval(812.0)
print(state["sample"]["heartRate"])
print(state["sample"]["signalConfidence"])
```

## Live Bridges

Serial RR stream from an embedded ECG-to-RR source:

```bash
python3 hrv_serial_sse_bridge.py --port /dev/ttyUSB0 --baud 115200
```

Hardware-free serial bridge test:

```bash
python3 hrv_serial_sse_bridge.py --simulate
```

Polar H10 BLE RR stream:

```bash
python3 hrv_ble_sse_bridge.py --max-devices 5
```

Hardware-free multi-subject BLE bridge test:

```bash
python3 hrv_ble_sse_bridge.py --simulate --max-devices 3
```

The bridges expose local Server-Sent Events at `http://127.0.0.1:8765/stream` and a JSON snapshot at `http://127.0.0.1:8765/latest`.

## Dashboard

```bash
cd hrv-dashboard
npm install
npm run dev
```

The public dashboard copy contains the HRV monitoring and event-annotation workflow only. Experimental EEG and hemodynamic dashboard modules from the development workspace were excluded because they are outside the manuscript validation path.

## Reviewer-2 Validation Reproduction

Install validation dependencies:

```bash
python3 -m pip install -r requirements-validation.txt
```

Download public validation data into the paths expected by the scripts:

```bash
python3 scripts/download_public_validation_data.py
```

Final ECG-to-RR validation:

```bash
python3 reviewer2_rpeak_final/run_firmware_equivalence_check.py
python3 reviewer2_rpeak_final/run_runtime_provenance_correction.py
```

Controlled RR-stream quality validation:

```bash
python3 reviewer2_signal_quality_validation/run_noise_quality_validation.py
python3 reviewer2_signal_quality_validation/run_runtime_qc.py
```

See [docs/VALIDATION.md](docs/VALIDATION.md) for the manuscript-to-code traceability table.

## Scientific Boundaries

The MIT-BIH Arrhythmia Database validation supports the ECG-to-RR adapter under controlled offline replay conditions. It does not establish clinical diagnostic ECG validity of the complete AD8232/ESP32 hardware chain.

Signal Confidence is a downstream RR-stream reliability indicator. It is not a general ECG morphology signal-quality index.

The Autonomic Balance Index, Autonomic Load Index, Recovery Score, and physiological state labels are experimental engineering readouts for research and prototyping. They are not clinically normed measures.

The respiration output is an RR-derived respiration proxy based on supported spectral structure in cleaned RR intervals. Unsupported spectra, numerical near-zero PSD residuals, and boundary-leakage cases return no proxy. This output is not direct measurement of airflow, thoracic movement, or ventilation, and it is not a clinically validated respiratory measure.

## Copyright and License

Copyright (c) 2026 Morris Gellisch. The original HRV pipeline and its accompanying software implementation remain copyrighted by the author. The software is released under the MIT License, which permits reuse, modification, and redistribution under the conditions specified in the LICENSE file. Third-party libraries, dependencies, PhysioNet data, and other externally sourced material remain subject to their respective licenses.

## Project Leadership and Contributions

**Dr. Morris Gellisch**\
Lead Developer, Corresponding Author, Repository Owner and Maintainer\
Ruhr University Bochum\
`morris.gellisch@ruhr-uni-bochum.de`

**Boris Burr**\
Technical Advisor, Software Methodology and Validation Contributor

The repository accompanies the scientific manuscript:

**"A real-time infrastructure transforming HRV streams into inference-ready, context-aware data objects for digital biomarker development."**

All manuscript co-authors are included in the recommended scientific citation in recognition of their contributions to the associated research and publication. Software/repository responsibility, scientific citation, maintainer status, software-development role, and copyright ownership are documented as distinct concepts. Please refer to `CITATION.cff` for the complete author list.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Validation Traceability](docs/VALIDATION.md)
- [Firmware Validation Parity](docs/FIRMWARE_VALIDATION_PARITY.md)
- [Implementation Correctness](docs/IMPLEMENTATION_CORRECTNESS.md)
- [Data and Privacy](docs/DATA.md)
- [Public Release Exclusions](docs/PUBLIC_RELEASE_EXCLUSIONS.md)

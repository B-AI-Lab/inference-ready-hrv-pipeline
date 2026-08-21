# HRV Inference-Ready Data Pipeline

Companion software for the manuscript:

**A real-time infrastructure transforming HRV streams into inference-ready, context-aware data objects for digital biomarker development**

This repository contains research infrastructure for transforming live RR-interval streams into event-synchronized, baseline-referenced, quality-informed HRV data objects. It is not clinical diagnostic software, medical decision-support software, or a validated stress/recovery detector.

## Overview

The pipeline is acquisition-agnostic after RR intervals are available. It accepts normalized RR streams from supported sources, applies artifact handling and HRV feature extraction, attaches event/context metadata, and emits inference-ready JSON/SSE payloads for dashboards or downstream research workflows.

## Key Capabilities

- Live RR-stream processing with time-domain, frequency-domain, and quality metadata.
- Serial bridge for embedded ECG-to-RR sources.
- BLE bridge for Polar H10 RR streams with multi-subject support.
- React/Vite dashboard for HRV monitoring, event annotation, and export.
- External ECG-to-RR validation against the MIT-BIH Arrhythmia Database.
- Controlled signal-quality validation using the MIT-BIH Noise Stress Test Database.
- Downstream regression tests for the public RR interface and HRV payload contract.

## Architecture

The repository separates acquisition adapters from downstream HRV processing:

1. ECG or BLE acquisition produces RR intervals.
2. `hrv_live_processing_engine.py` normalizes, filters, and summarizes the RR stream.
3. Signal Confidence and Signal Status describe RR-stream reliability.
4. Event annotation and baseline comparison create context-aware data objects.
5. Bridge services expose Server-Sent Events and JSON snapshots for the dashboard.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Repository Structure

```text
.
|-- firmware/
|   `-- esp32_ecg_rr/                 # ESP32 ECG-to-RR firmware source
|-- validation/
|   |-- ecg_rpeak/                    # MIT-BIH ECG-to-RR benchmark and runtime artifacts
|   |-- signal_quality/               # NSTDB Signal Confidence and Orphanidou-based comparator benchmark
|   `-- downstream/                   # RR interface and downstream HRV regression checks
|-- hrv-dashboard/                    # React/Vite dashboard
|-- scripts/                          # Public validation-data downloader
|-- tests/                            # Unit and regression tests
|-- docs/                             # Architecture, validation, data, and release documentation
|-- hrv_live_processing_engine.py
|-- hrv_ble_sse_bridge.py
|-- hrv_serial_sse_bridge.py
|-- ble_scan_debug.py
|-- requirements.txt
|-- requirements-live.txt
`-- requirements-validation.txt
```

Raw PhysioNet waveform files and participant-level recordings are not included.

## Installation

Core Python runtime:

```bash
python3 -m pip install -r requirements.txt
```

Live bridge extras:

```bash
python3 -m pip install -r requirements-live.txt
```

Validation dependencies:

```bash
python3 -m pip install -r requirements-validation.txt
```

Dashboard dependencies:

```bash
cd hrv-dashboard
npm install
```

## Running The Pipeline

Processing-engine demo:

```bash
python3 hrv_live_processing_engine.py --demo
```

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

Dashboard:

```bash
cd hrv-dashboard
npm run dev
```

The bridges expose local Server-Sent Events at `http://127.0.0.1:8765/stream` and a JSON snapshot at `http://127.0.0.1:8765/latest`.

## Validation

The public repository organizes validation by scientific function rather than manuscript-review history.

1. **External ECG-to-RR validation**: firmware-equivalent Pan-Tompkins replay and Hamilton comparator on all 48 MIT-BIH Arrhythmia Database records.
2. **Controlled signal-quality validation**: Signal Confidence and an Orphanidou-based comparator on MIT-BIH Noise Stress Test Database records and clean source records.
3. **Downstream HRV validation**: regression tests confirming that the RR serial interface, HRV engine payload, event annotation hooks, and export-facing contract remain stable.
4. **Operational feasibility and latency context**: documentation separates offline benchmark timings from physical embedded latency and from real-world feasibility recordings, which are not distributed as participant-level data.

See [docs/VALIDATION.md](docs/VALIDATION.md), [docs/FIRMWARE_VALIDATION_PARITY.md](docs/FIRMWARE_VALIDATION_PARITY.md), and [docs/IMPLEMENTATION_CORRECTNESS.md](docs/IMPLEMENTATION_CORRECTNESS.md).

## Reproducing Public Benchmarks

Download public validation data:

```bash
python3 scripts/download_public_validation_data.py
```

External ECG-to-RR benchmark:

```bash
python3 validation/ecg_rpeak/run_ecg_to_rr_benchmark.py
python3 validation/ecg_rpeak/benchmark_ecg_to_rr_runtime.py
```

Controlled signal-quality benchmark:

```bash
python3 validation/signal_quality/run_signal_quality_benchmark.py
python3 validation/signal_quality/benchmark_signal_quality_runtime.py
```

Downstream regression:

```bash
python3 validation/downstream/run_downstream_regression.py
```

Core test suite:

```bash
python3 -m unittest discover -s tests
```

## Data Availability

Public validation scripts download the MIT-BIH Arrhythmia Database and MIT-BIH Noise Stress Test Database from PhysioNet into ignored local `validation/*/data/` directories. These raw public waveform files are not vendored in the repository.

Individual-level physiological recordings from emergency-simulation sessions are not included. Generated live BLE exports may include subject IDs, display names, BLE MAC addresses, timestamps, and free-text event labels; treat them as potentially identifiable operational records.

## Scientific Scope And Limitations

The MIT-BIH Arrhythmia Database benchmark supports the ECG-to-RR adapter under controlled offline replay conditions. It does not establish clinical diagnostic ECG validity of the complete AD8232/ESP32 hardware chain.

Signal Confidence is a downstream RR-stream reliability indicator. It is not a general ECG morphology signal-quality index.

The Autonomic Balance Index, Autonomic Load Index, Recovery Score, and physiological state labels are experimental engineering readouts for research and prototyping. They are not clinically normed measures.

The respiration output is an RR-derived respiration proxy based on supported spectral structure in cleaned RR intervals. Unsupported spectra, numerical near-zero PSD residuals, and boundary-leakage cases return no proxy. This output is not direct measurement of airflow, thoracic movement, or ventilation, and it is not a clinically validated respiratory measure.

## Citation

Please cite the associated manuscript when using this repository. The recommended citation metadata in [CITATION.cff](CITATION.cff) preserves all manuscript co-authors in the current manuscript order.

## Project Leadership And Contributions

**Dr. Morris Gellisch**\
Lead Developer, Corresponding Author, Repository Owner and Maintainer\
Ruhr University Bochum\
`morris.gellisch@ruhr-uni-bochum.de`

**Boris Burr**\
Technical Advisor, Software Methodology and Validation Contributor

All manuscript co-authors are included in the recommended scientific citation in recognition of their contributions to the associated research and publication. Software/repository responsibility, scientific citation, maintainer status, software-development role, and copyright ownership are documented as distinct concepts.

## License

Copyright (c) 2026 Morris Gellisch. The original HRV pipeline and its accompanying software implementation remain copyrighted by the author. The software is released under the MIT License, which permits reuse, modification, and redistribution under the conditions specified in the [LICENSE](LICENSE) file. Third-party libraries, dependencies, PhysioNet data, and other externally sourced material remain subject to their respective licenses.

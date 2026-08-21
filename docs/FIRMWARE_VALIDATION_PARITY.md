# Firmware Validation Parity

The evidence-bearing embedded ECG-to-RR implementation is organized as:

- Firmware source: `firmware/esp32_ecg_rr/main.cpp`
- Host replay: `validation/ecg_rpeak/run_ecg_to_rr_benchmark.py`
- Validation outputs: `validation/ecg_rpeak/ecg_to_rr_benchmark_summary.csv` and `validation/ecg_rpeak/ecg_to_rr_record_level_results.csv`

The older development sketch from the workspace root (`src/main.cpp` with display-coupled adaptive threshold logic) is intentionally not included in this public repository and is not evidence-bearing for the manuscript.

## Component Comparison

| Component | ESP32 firmware | Host validation replay | Equivalent? | Notes |
|---|---|---|---|---|
| Sampling frequency | 250 Hz, `SAMPLE_PERIOD_US = 4000`, `FS_HZ = 250` | `mitval.FS_TARGET = 250`; one replay update per 250-Hz sample | Yes | MIT-BIH ECG is resampled from 360 Hz to 250 Hz before replay. |
| Preprocessing/filter chain | Causal second-order IIR: `0.11216024*x[n] - 0.11216024*x[n-2] + 1.73356294*y[n-1] - 0.77567951*y[n-2]` | Same difference equation in `FirmwarePanTompkinsReplay.update()` | Yes | Host uses Python floats; firmware uses `float`. |
| Derivative stage | First difference of filtered output | Same | Yes | `diff = y - lastFiltered`. |
| Squaring/nonlinear transform | Squared derivative | Same | Yes | `squared = diff * diff`. |
| Moving-window integration | Circular buffer length 38 samples | Same | Yes | 38 samples equals approximately 150 ms at 250 Hz. |
| Initial zeroing | MWI forced to zero for first 75 samples | Same | Yes | `ZERO_SAMPLES = 75`. |
| Peak candidate logic | Local maximum in MWI: previous MWI greater than neighbors | Same | Yes | Same one-sample delayed candidate index. |
| Adaptive thresholds | SPKI/NPKI updates; `thresholdI1 = npki + 0.25*(spki-npki)`; `thresholdI2 = 0.5*thresholdI1` | Same | Yes | Host naming differs only by Python style. |
| Signal/noise peak handling | Candidate over threshold and outside refractory updates SPKI; otherwise NPKI | Same | Yes | Same update weights `0.125/0.875`. |
| Refractory period | 75 samples | Same | Yes | 300 ms at 250 Hz. |
| Search-back | If RR exceeds `rrMissed`, choose recent peak above secondary threshold with minimum 62-sample separation | Same | Yes | Host list reproduces firmware recent peak buffer behavior for replay. |
| Peak localization | Detection timestamp is the MWI peak sample index | Same | Yes | No additional local ECG-amplitude refinement is applied. |
| Timing conversion | `detectedMs = (1000 * qrsIndex) / FS_HZ` using integer division | Same | Yes | Host uses integer floor division before RR filtering. |
| RR calculation | Difference between successive detected timestamps | Same | Yes | First detection initializes state and is not emitted as RR. |
| Physiologic RR limits | Emit only `250 <= rr_ms <= 2200` | Same | Yes | This is the route used for manuscript ECG-to-RR metrics. |
| State reset | One detector instance per record/replay | Same | Yes | Validation resets state between MIT-BIH records. |
| Numerical precision | Firmware `float` | Python float | Equivalent with minor numerical differences possible | No evidence that these minor precision differences alter the reported host-replay validation because the host replay is the evidence-bearing algorithm-level implementation. |

## Empirical Evidence

`validation/ecg_rpeak/run_ecg_to_rr_benchmark.py` implements a line-by-line host replay of `firmware/esp32_ecg_rr/main.cpp`. The MIT-BIH validation and controlled offline runtime benchmark use this host replay, not `py-ecg-detectors.pan_tompkins_detector`.

This means the repository validates a host-side implementation reproducing the deployed firmware detector logic for offline replay. It does not mean that MIT-BIH ECG physically passed through an AD8232/ESP32 device, and it does not validate the complete analog hardware chain.

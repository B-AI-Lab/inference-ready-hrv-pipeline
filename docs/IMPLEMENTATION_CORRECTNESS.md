# Implementation Correctness Audit

Date: 2026-08-21

Scope: independent scientific implementation-correctness audit of the
public repository. This pass did not modify production algorithms,
classification metrics, figures, or manuscript-reported validation results.

## Executive Finding

The standard time-domain HRV calculations, RR timestamp handling, RR
plausibility filtering, composite-index directionality, event assignment, and
baseline-relative export calculations are internally interpretable and matched
independent deterministic checks.

The initial audit found that out-of-band synthetic RR modulation at 0.05 Hz and
0.55 Hz could produce apparently valid in-band `respirationProxyHz`, and that
constant RR could produce tiny numerical PSD power, a finite LF/HF ratio, and an
in-band respiration-proxy value. The production engine was then minimally
corrected with explicit spectral-validity gates. The corrected implementation
returns no LF/HF or respiration proxy for constant RR, returns no proxy for the
audited 0.05-Hz and 0.55-Hz cases, and preserves ordinary in-band behavior for
supported 0.10-0.40 Hz oscillations plus a supported 0.50-Hz boundary case when
the RR-event sampling rate can support it.

Residual scientific caveat: RR intervals are themselves sampled at beat times.
Therefore, high true modulations above the RR-event Nyquist frequency can alias
into lower RR-dynamic frequencies and may be indistinguishable from genuine
lower-frequency RR oscillations using RR intervals alone. The output must remain
described as an experimental RR-derived spectral proxy, not direct respiration
measurement or a fully anti-aliased respiratory-rate estimator.

## Component-Level Correctness Matrix

| Component | Intended mathematical definition | Production code location | Independent test/reference | Observed result | Manuscript agreement | Status |
|---|---|---|---|---|---|---|
| RR timestamp handling | Without source timestamp, elapsed time advances by RR/1000 s; with source timestamp, elapsed time is timestamp minus first timestamp. | `hrv_live_processing_engine.py:528-540` | Injected RR `[800, 900, 1000]` without timestamps and `[100.0, 100.8, 101.7]` with timestamps. | Elapsed values were 0.8, 1.7, 2.7 s and 0.0, 0.8, 1.7 s. | Agrees with manuscript claim of timestamped RR primitive and BLE host-time context. | VERIFIED |
| Physiologic RR plausibility filtering | Accept finite RR within 300-2000 ms before local artifact checks. | `hrv_live_processing_engine.py:479-485` | Boundary injection at 299, 300, 2000, 2001 ms. | Initial 300 and 2000 ms accepted; 299 rejected `below_min`; 2001 rejected `above_max`. With a stable 800 ms recent history, 300 and 2000 can still be rejected as outliers, which is expected because plausibility is necessary but not sufficient. | Agrees with Methods wording if described as plausibility plus artifact filtering. | VERIFIED WITH CAVEAT |
| Local median/MAD artifact detection | Reject RR differing from recent median by more than max(140, min(260, 0.35*median, 6*MAD or 260)). | `hrv_live_processing_engine.py:487-502` | Stable recent RR of 800 ms, test 940 and 1100 ms. | 940 ms accepted; 1100 ms rejected as `median_mad_outlier`. | Agrees with artifact-handling claim. | VERIFIED |
| Successive-difference filtering | Reject adjacent accepted RR jumps outside ratio range 1/(1+0.30) to 1+0.30. | `hrv_live_processing_engine.py:503-508`, `182-243` | RR sequence with isolated 1600 ms among approximately 800 ms intervals. | `clean_nn_mask` rejected only the 1600 ms interval. | Agrees with conservative NN filtering wording. | VERIFIED |
| Heart rate | 60000 / median cleaned RR over the recent heart-rate window when at least 3 RR values exist. | `hrv_live_processing_engine.py:620-631` | Constant 800 ms stream after stabilization. | Heart rate 75.0 bpm. | Agrees. | VERIFIED |
| RMSSD | Square root of mean squared successive RR differences after live successive-difference filtering. | `hrv_live_processing_engine.py:125-140`, `643-645` | Independent calculation on `[800, 810, 790, 820, 780]`. | Production helper and independent value both 27.3861278753 ms. | Agrees. | VERIFIED |
| SDNN | Sample standard deviation of cleaned RR, `ddof=1`. | `hrv_live_processing_engine.py:158-162`, `646` | Independent NumPy sample SD on `[800, 810, 790, 820, 780]`. | Production helper and independent value both 15.8113883008 ms. | Agrees. | VERIFIED |
| pNN50 | Percent of valid successive RR differences greater than 50 ms. | `hrv_live_processing_engine.py:142-155`, `647-648` | Independent count on `[800, 860, 800, 861]`. | Production helper returned 100.0%. | Agrees. | VERIFIED |
| Detrended SDNN | Sample SD after least-squares linear trend removal; falls back to SDNN for fewer than 8 values. | `hrv_live_processing_engine.py:165-172` | Linear RR ramp `800 + 10*i`. | Detrended SDNN 0.0 ms. | Agrees. | VERIFIED |
| Baevsky-related relative index | Relative live index `AMo/(2*Mo*MxDMn)` using 50 ms bins, with Mo and MxDMn in ms. | `hrv_live_processing_engine.py:276-301` | Manual histogram logic on `[800,805,810,815,820,900]`; constant RR boundary. | Returned 0.0005050505 for varying RR; returned `None` when MxDMn = 0. | Agrees if manuscript retains "relative index" wording, not clinical Baevsky SI. | VERIFIED WITH CAVEAT |
| RR interpolation to 4 Hz | Interpolate cleaned irregular RR samples onto evenly spaced 4 Hz grid. | `hrv_live_processing_engine.py:695-698` | Synthetic sinusoidal RR streams with known modulation frequency. | In-band synthetic frequencies resolved to nearby Welch bins. | Agrees with Methods constants. | VERIFIED |
| Detrending | Linear detrending before Welch PSD. | `hrv_live_processing_engine.py:698-699` | Linear-ramp and sinusoidal tests. | Linear trend removed in deterministic time-domain check; spectral pipeline ran after detrending. | Agrees. | VERIFIED |
| Welch PSD | Hamming-window Welch PSD at 4 Hz; `nperseg=min(max(128,n//4),512)`, 50% overlap; no additional Welch detrend. | `hrv_live_processing_engine.py:700-712` | Synthetic sinusoidal RR streams with expected spectral peaks. | Dominant peaks close to expected frequencies inside band, subject to bin resolution. | Agrees. | VERIFIED WITH CAVEAT |
| LF integration 0.04-0.15 Hz | Trapezoidal integration of PSD bins where `f >= 0.04` and `f <= 0.15`. | `hrv_live_processing_engine.py:304-311`, `713` | Synthetic 0.10 Hz and 0.25 Hz RR modulation. | 0.10 Hz produced dominant LF power; 0.25 Hz produced near-zero LF power. | Agrees. | VERIFIED |
| HF integration 0.15-0.40 Hz | Trapezoidal integration of PSD bins where `f >= 0.15` and `f <= 0.40`. | `hrv_live_processing_engine.py:304-311`, `714` | Synthetic 0.25 Hz and 0.40 Hz RR modulation. | 0.25 and 0.40 Hz produced dominant HF power. Boundary 0.15 contributed to both LF and HF because both bands use inclusive endpoints. | Manuscript bands are correct, but inclusive overlap at 0.15 Hz should be understood. | VERIFIED WITH CAVEAT |
| LF/HF calculation | `lf/hf` only when HF is positive and the detrended RR spectrum has at least 1 ms variability. | `hrv_live_processing_engine.py` frequency analyzer | Synthetic LF/HF cases and constant RR before/after the validity guard. | Constant RR now returns `None` for LF, HF, and LF/HF; ordinary in-band LF/HF behavior is preserved when spectral variability is supported. | Manuscript should still avoid overinterpreting LF/HF. | VERIFIED WITH CAVEAT |
| RR-derived respiration proxy 0.06-0.50 Hz | Report dominant supported RR-spectral peak only after negligible-spectrum, diagnostic-band dominance, peak/background, and RR-sampling reliability gates. | `hrv_live_processing_engine.py` respiration analyzer | Synthetic RR modulation at 0, 0.05, 0.06, 0.10, 0.15, 0.25, 0.40, 0.50, 0.55 Hz plus sweep and noisy scenarios. | Constant, 0.05, and 0.55 Hz return no proxy. 0.10-0.40 Hz are recovered. 0.06 Hz is rejected because the 300-s Welch bin is not separable from 0.05-Hz leakage; 0.50 Hz is supported only when RR-event sampling permits it. Higher-frequency alias ambiguity remains inherent to RR-only sampling. | Requires Methods wording for the validity gate and alias limitation. | VERIFIED WITH CAVEAT |
| PSD Readiness | Window fill fraction up to 300 s multiplied by stationarity score. | `hrv_live_processing_engine.py:679-692` | Too-few, 80-beat, and long stable streams. | Readiness rose from approximately 0.0027 to 0.2107 to 1.0 as expected. | Agrees. | VERIFIED |
| Slow-breathing detection/attenuation | For confident respiration proxy, spectral stress weights multiplied by `1 - 0.65*sigmoid((0.15-respHz)*35)`. | `hrv_live_processing_engine.py:345-348`, `782-789` | Same sample with low HF/high LF-HF at 0.10 Hz versus 0.25 Hz. | Stress score 57.51 at 0.10 Hz versus 64.01 at 0.25 Hz. | Agrees with intended attenuation direction. | VERIFIED |
| Artifact Ratio / RR quality | Recent rejected raw RR fraction; RR quality = `1 - artifact_ratio`. | `hrv_live_processing_engine.py:595-602`, `1084-1101` | Stable stream followed by six rejected 2500 ms intervals. | Rejected count increased; confidence dropped; status became `Signal Lost`. | Agrees. | VERIFIED |
| Beat density | Recent valid beat count divided by expected beats from mean RR and 60 s analysis window, clipped to 0-1. | `hrv_live_processing_engine.py:1086-1091` | Early 12-beat stream and mature 80-beat stable stream. | Early confidence stayed lower due incomplete 60 s density; mature stream reached 1.0. | Agrees if described as 60 s density, not instantaneous density. | VERIFIED WITH CAVEAT |
| Freshness | 1.0 within 3 s since last valid RR, linearly decays to 0 at 10 s. | `hrv_live_processing_engine.py:1092-1100` | Valid stream followed by invalid RR at later timestamps. | Status became `Signal Lost` when seconds since last valid exceeded 5 s. | Agrees. | VERIFIED |
| Signal Confidence | `0.5*RR quality + 0.3*beat density + 0.2*freshness`, clipped 0-1. | `hrv_live_processing_engine.py:1084-1101` | Stable mature stream and rejected/stale stream. | Mature stable stream: 1.0 Active. Rejected/stale stream: confidence 0.364-0.650 but status Signal Lost due stale rule. | Agrees with controlled Signal Confidence validation as a rule-based RR-stream reliability measure. | VERIFIED |
| Signal Status | Signal Lost if confidence <0.35 or stale >5 s; Active >=0.75; Noisy >=0.50; else Low Confidence. | `hrv_live_processing_engine.py:1103-1111` | Confidence/status boundary tests. | Status matched thresholds. | Agrees. | VERIFIED |
| Baseline initialization | Add baseline features while elapsed <=300 s and recent artifact ratio <=0.12 with at least 20 recent records; initialized after >=120 s and at least 2 baseline stats. | `hrv_live_processing_engine.py:995-1009` | Stable synthetic stream. | Baseline initialized after criteria were met. MAD=0 baselines can prevent robust-z outputs unless std >0 exists. | Agrees with initialization concept. | VERIFIED WITH CAVEAT |
| Robust baseline z-scores | Median/MAD z using 1.4826*MAD; fallback to sample SD; return `None` if both dispersion estimates are zero. | `hrv_live_processing_engine.py:314-331`, `413-417` | Manual baseline stats with nonzero MAD and zero-dispersion boundary. | Z-scores matched robust formula; unsupported zero-dispersion z returned `None`. | Agrees. | VERIFIED |
| Autonomic Balance Index | `100*sigmoid(clamp(z(ln LF/HF), -3, 3))`. | `hrv_live_processing_engine.py:1011-1014` | Ratios 0.5, 1.0, 2.0 against baseline ratio 1.0. | ABI 8.81, 50.00, 91.19. | Agrees with directionality; should not be framed as direct sympathovagal truth. | VERIFIED |
| Autonomic Load Index / Stress Score | Weighted robust-z composite: HR 0.35, inverse RMSSD 0.25, inverse HF 0.15, ln LF/HF 0.10, Baevsky relative index 0.15; spectral components attenuated by PSD readiness and slow-breathing factor; logistic scaling to 0-100; EMA smoothing alpha 0.25 in live sequence. | `hrv_live_processing_engine.py:334-368`, `751-797` | One-component-at-a-time monotonicity tests with fixed baseline. | Base 50.00; HR up 67.08; RMSSD up 41.61; RMSSD down 58.39; HF up 44.17; HF down 58.56; LF/HF up 55.73; LF/HF down 44.27; Baevsky up 55.07. | Agrees with intended directionality if manuscript uses experimental composite wording. | VERIFIED |
| Recovery Score | Without active event: high score for lower stress with optional RMSSD rebound capped at baseline. With event: weighted completion, speed, stability, optional RMSSD rebound. | `hrv_live_processing_engine.py:897-935` | Stress and RMSSD monotonicity tests with/without artificial event. | No event: stress 35/55/75 produced recovery 96.25/81.25/66.25. Event current stress 75/60/45 produced recovery 43.0/67.0/85.0. | Agrees with intended directionality; experimental only. | VERIFIED |
| Event/phase assignment | Backend BLE export context uses event labels and host times; dashboard annotation uses active event phase or `none`. | `hrv_ble_sse_bridge.py:67-138`, `224-249`, dashboard `phaseLabeler.ts`. | Inspection plus deterministic event-label parsing. | Baseline/intervention/recovery flags and active context are assigned by host timestamp order. | Agrees with manuscript context-preserving claim. | VERIFIED |
| Baseline-relative segment calculations | Baseline means/SD; windows get absolute/percent deltas, z-scores, and corridor flags; segments summarize phase windows. | Dashboard `baselineCalculator.ts`, `baselineComparator.ts`, `segmentSummarizer.ts`. | Independent arithmetic formulas for mean, sample SD, z, percent delta, mean summaries. | Formulas are transparent and correct for available numeric fields; unsupported baseline SD=0 returns null z. | Agrees. | VERIFIED |

## Respiratory-Proxy Synthetic Frequency Test

Synthetic RR intervals were generated as:

`RR_ms(t) = 1000 + 60*sin(2*pi*f*t)`

Each stream was replayed for approximately 330 s through the production
interpolation, linear detrending, Welch PSD, LF/HF integration, and respiration
search pipeline. The expected values below are the known injected modulation
frequencies; the production code produced the observed values.

### Initial failing behavior

The initial audit reproduced the failure before the validity guard: constant RR
could emit an in-band proxy from numerical PSD residue, 0.05 Hz could be snapped
to approximately 0.067 Hz, and 0.55 Hz could alias to approximately 0.455 Hz.

### Corrected behavior

| Injected frequency (Hz) | Expected proxy validity | Corrected proxy (Hz) | Error when accepted (Hz) | LF power | HF power | LF/HF | PSD ready | Slow-breathing effect | Interpretation |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| 0.00 | No | None | n/a | None | None | None | 1.000 | No | Correctly suppressed zero-variability spectrum. |
| 0.05 | No | None | n/a | 1502.6806 | 0.1468 | 10233.1372 | 0.623 | No | Correctly avoids snapping leakage to lower boundary. |
| 0.06 | Ambiguous at current resolution | None | n/a | 1747.6195 | 0.3302 | 5291.8747 | 0.971 | No | Conservatively rejected because the broad 300-s Welch peak is not separable from the 0.05-Hz leakage case. |
| 0.10 | Yes | 0.093645 | 0.006355 | 1683.5537 | 0.9681 | 1739.0848 | 0.966 | Yes | Accepted, bin-limited recovery error. |
| 0.15 | Yes | 0.147157 | 0.002843 | 612.2836 | 205.2244 | 2.9835 | 0.998 | Yes | Accepted near LF/HF boundary. |
| 0.25 | Yes | 0.254181 | 0.004181 | 0.1039 | 1175.8822 | 0.000088 | 0.999 | No | Accepted HF-dominant oscillation. |
| 0.40 | Yes | 0.400000 | 0.000000 | 0.000021 | 295.4970 | approximately 0 | 0.999 | No | Accepted upper HF boundary. |
| 0.50, 1000-ms base RR | No, unsupported sampling realization | None | n/a | None | None | None | 1.000 | No | With 1-s beat timing this synthetic lands on zero crossings and has no supported spectral variability. |
| 0.50, 800-ms base RR | Yes, supported upper boundary | 0.494983 | 0.005017 | 0.0134 | 3.1977 | 0.0042 | 0.999 | No | Accepted when RR-event sampling supports the boundary. |
| 0.55 | No | None | n/a | 5.1531 | 0.2286 | 22.5455 | 0.997 | No | Correctly suppresses audited upper out-of-band alias case. |

Unit trace:

- RR input is in milliseconds.
- RR timestamps and elapsed time are in seconds.
- Interpolation uses `interp_fs = 4.0` samples/second.
- Welch frequencies are in Hz.
- LF, HF, and respiration-proxy bands are specified in Hz.
- No Hz-to-breaths/min conversion is applied in the engine.
- No milliseconds-to-seconds conversion error was observed in the frequency axis.

The original problem was not a 60x or 1000x unit error. It was a validity-gating
problem: the implementation picked the strongest bin inside the configured
search band whenever a PSD existed, even if the true modulation was outside the
band or the PSD was effectively zero.

## Additional Post-Fix Probes

Representative realistic perturbations remained accepted when the in-band
oscillation was supported:

| Scenario | Corrected proxy | Interpretation |
|---|---:|---|
| 0.25 Hz with 5 ms beat-to-beat noise | 0.254181 | Accepted |
| 0.25 Hz with 15 ms beat-to-beat noise | 0.254181 | Accepted |
| 0.25 Hz with 10 ms modulation and 3 ms noise | 0.253333 | Accepted |
| 0.10 Hz with baseline RR drift and 5 ms noise | 0.093645 | Accepted |
| 0.55 Hz with 5 ms noise | None | Rejected |
| Short 45-s 0.25 Hz window with noise | 0.250000 | Accepted with low PSD readiness; downstream spectral influence remains attenuated by readiness |
| 0.25 Hz at 800-ms base RR | 0.253333 | Accepted |
| 0.25 Hz at 1200-ms base RR | 0.254181 | Accepted |

Frequency sweep from 0.02 to 0.70 Hz in 0.02-Hz increments showed acceptance
from approximately 0.08 to 0.40 Hz and rejection from 0.42 to 0.58 Hz under the
1000-ms base-RR condition. Frequencies at 0.60 Hz and above can alias into lower
RR-derived frequencies and may be accepted as lower-frequency RR oscillations.
This residual ambiguity cannot be fully resolved from the RR interval stream
alone; avoiding it requires direct respiration measurement, higher-rate source
information, or stronger upper-band conservatism that would also reject some
nominally in-band high-frequency RR oscillations.

## Composite-Index Directionality Tests

Manual robust baselines were constructed with nonzero median/MAD values:

- HR median 60 bpm, MAD 5
- RMSSD median 50 ms, MAD 10
- ln(HF) median ln(1000), MAD 0.2
- ln(LF/HF) median ln(1.0), MAD 0.2
- Baevsky relative index median 0.002, MAD 0.0005

Observed Autonomic Load / Stress Score outputs with one component changed at a
time:

| Input condition | Observed score | Direction |
|---|---:|---|
| Baseline sample | 50.00 | Reference |
| HR increased to 75 bpm | 67.08 | Increased load |
| RMSSD increased to 70 ms | 41.61 | Decreased load |
| RMSSD reduced to 30 ms | 58.39 | Increased load |
| HF increased to 1600 | 44.17 | Decreased load |
| HF reduced to 500 | 58.56 | Increased load |
| LF/HF increased to 2.0 | 55.73 | Increased load |
| LF/HF reduced to 0.5 | 44.27 | Decreased load |
| Baevsky relative index increased to 0.003 | 55.07 | Increased load |

Attenuation behavior:

- Low HF plus high LF/HF at PSD readiness 1.0: 64.01.
- Same sample at PSD readiness 0.0: 53.58.
- Same spectral stress sample with confident 0.10 Hz slow-breathing proxy:
  57.51.
- Same spectral stress sample with confident 0.25 Hz proxy: 64.01.
- Same spectral stress sample with no valid respiration proxy: 64.21.
- The previous false slow-breathing proxy at approximately 0.067 Hz would have
  reduced the same sample to 56.59; after the fix, no valid proxy means no
  respiration-based attenuation.

Autonomic Balance Index tests:

| LF/HF ratio | Robust z of ln(LF/HF) | ABI |
|---:|---:|---:|
| 0.5 | -2.3376 | 8.81 |
| 1.0 | 0.0000 | 50.00 |
| 2.0 | 2.3376 | 91.19 |

Recovery Score tests:

| Condition | Observed Recovery Score | Direction |
|---|---:|---|
| No event, stress 35 | 96.25 | Higher recovery |
| No event, stress 55 | 81.25 | Lower recovery |
| No event, stress 75 | 66.25 | Lower recovery |
| No event, stress 55, RMSSD 25 | 68.75 | Lower RMSSD lowers recovery |
| No event, stress 55, RMSSD 50 | 81.25 | Baseline RMSSD |
| No event, stress 55, RMSSD 80 | 81.25 | RMSSD rebound is capped at baseline contribution |
| Active event, current stress 75 | 43.00 | Lower completion |
| Active event, current stress 60 | 67.00 | More completion |
| Active event, current stress 45 | 85.00 | More completion |

These tests confirm intended monotonicity and missing-component handling for
the composite indices. They do not validate clinical interpretation.

## Failure And Boundary Conditions

| Case | Observed behavior | Status |
|---|---|---|
| Constant RR, 80 beats | HR 75, RMSSD 0, SDNN 0, pNN50 0, signal Active. PSD-derived LF/HF and respiration proxy are now unavailable. | Safe. |
| Long constant RR, 420 beats | PSD readiness can reach 1.0, but negligible detrended RR variability suppresses LF/HF and respiration proxy. | Safe. |
| Too few beats | HR/RMSSD/SDNN/pNN50/LF/HF/respiration all `None`; signal status Noisy/Initializing. | Safe. |
| Zero variance | Time-domain zero-variability metrics are emitted as 0, which is mathematically supported. Baevsky relative index returns `None`; spectral/proxy output is suppressed by the 1-ms detrended RR variability guard. | Safe. |
| MAD = 0 | Artifact detector falls back to minimum jump threshold; robust z falls back to SD if available and otherwise returns `None`. | Safe. |
| HF power = 0 | LF/HF returns `None` if HF is absent/nonpositive or the spectrum is unsupported by the RR-variability guard. | Safe with caveat for very small but nonzero supported HF. |
| No valid PSD peak | Respiration proxy returns `None` when the supported broad-band dominant peak is outside the reliable proxy range or fails peak/background validity. | Safe with alias caveat. |
| Irregular sampling | Uses elapsed RR timestamps and interpolates cleaned RR to 4 Hz. | Verified. |
| Long gaps | Invalid RR at later timestamps produces stale Signal Lost status. | Safe. |
| Stale input | >5 s since last valid RR sets Signal Lost. | Safe. |
| Rejected beats | Rejected intervals increase artifact ratio and lower confidence; status can become Signal Lost. | Safe. |
| Minimum permitted RR | 300 ms accepted initially; can be rejected after stable recent history as an outlier. | Safe with caveat. |
| Maximum permitted RR | 2000 ms accepted initially; can be rejected after stable recent history as an outlier. | Safe with caveat. |
| Reconnect/resynchronization | After at least 10 consecutive rejections, a stable plausible raw RR sequence can be accepted as `accepted_resync`. | Plausible, not empirically device-tested here. |
| Insufficient baseline | Stress/Recovery return `None` until baseline initialized; robust z returns `None` without baseline dispersion. | Safe. |

## Firmware Parity Evidence

How parity was established:

1. The evidence-bearing firmware source is present at
   `firmware/esp32_ecg_rr/main.cpp`.
2. The host replay in `validation/ecg_rpeak/run_ecg_to_rr_benchmark.py`
   mirrors the firmware constants and sequential update logic: IIR filter,
   derivative, squaring, 38-sample moving-window integration, refractory period,
   threshold updates, RR-missed search-back logic, and RR validity gating.
3. The MIT-BIH values reported in the ECG-to-RR validation package are generated
   from the host replay, not from the earlier `py-ecg-detectors` route.

Quantified validation result for the firmware-equivalent host replay:

- 48 MIT-BIH records.
- 109,494 expert beats.
- TP/FP/FN = 107,641 / 1,405 / 1,853.
- Sensitivity 0.9831.
- PPV 0.9871.
- F1 0.9851.
- Median matched-beat timing error 86.0 ms.

Remaining caveat: this audit did not execute a compiled C++ host fixture or a
physical ESP32 on identical ECG input. Therefore, "firmware parity" is best
stated as source-level equivalence between the included firmware and the
firmware-equivalent host replay plus external MIT-BIH validation of that host replay.
It should not be overstated as byte-for-byte runtime output comparison against
an ESP32 device unless such a fixture is added.

## Export-Format Consistency

Actual implemented endpoints and formats:

| Layer | Endpoint/function | File type | Internal organization | One observation per row? | Subject organization |
|---|---|---|---|---|---|
| BLE backend | `/export/session.json` | JSON | Hierarchical session object with global events, context intervals, subjects, histories, latest payloads, status. | Observations are history objects, not rows. | Subjects are keys under `subjects`. |
| BLE backend | `/export/session.xlsx` | XLSX | OpenXML workbook generated by Python standard-library zip/XML code. | Yes, one history observation per worksheet row. | One worksheet per subject/display name. |
| Dashboard event layer | `exportFullSessionJSON()` | JSON | ML-ready object with session metadata, source samples, annotated windows, events, baseline, segments, readouts. | Observations are objects, not rows. | Single dashboard session object. |
| Dashboard event layer | `exportAnnotatedWindowsCSV()` | CSV | Long-format comma-separated rows for annotated HRV windows. | Yes, one annotated HRV window per CSV row. | CSV is not worksheet-based; subject separation depends on the dashboard session context and exported fields. |
| Dashboard multi-subject service | `exportSessionExcel()` | XLSX | Client-side workbook using `xlsx`. | Yes, one history sample per worksheet row. | One worksheet per subject. |
| Dashboard multi-subject service | `exportSubjectJSON()` | JSON | One JSON file per subject. | Observations are history objects. | Separate subject JSON files. |

Technically correct manuscript wording:

"The backend exposes `/export/session.json` as a hierarchical session export and
`/export/session.xlsx` as an Excel workbook with one worksheet per subject and
one stored subject observation per row. The dashboard event-annotation layer
also supports a spreadsheet-compatible long-format CSV export in which each
annotated HRV window is one row. CSV files do not contain worksheets."

The manuscript sentence "The CSV export provides one worksheet per subject" is
incorrect and should be replaced with the distinction above.

## Evidence-Bearing Firmware In Public Release

The public repository contains the evidence-bearing ESP32 ECG-to-RR firmware and its
build context:

- `firmware/esp32_ecg_rr/main.cpp`
- `firmware/esp32_ecg_rr/platformio.ini`
- `validation/ecg_rpeak/run_ecg_to_rr_benchmark.py`
- `validation/ecg_rpeak/firmware_replay_benchmark_summary.csv`
- `validation/ecg_rpeak/firmware_replay_record_level_benchmark.csv`
- `validation/ecg_rpeak/ecg_to_rr_benchmark_summary.csv`
- `validation/ecg_rpeak/ecg_to_rr_record_level_results.csv`

The excluded legacy root `src/main.cpp` is obsolete for this public repository
because the validation evidence is tied to the isolated
Pan-Tompkins firmware source listed above, not to the development root sketch.

## xlsx Dependency

The vulnerable `xlsx` npm dependency is present because
`hrv-dashboard/src/hrvMulti/exportService.ts` imports it to create and write a
client-side multi-subject Excel workbook:

- `XLSX.utils.book_new()`
- `XLSX.utils.json_to_sheet()`
- `XLSX.utils.book_append_sheet()`
- `XLSX.writeFile()`

It is not needed for the Python backend `/export/session.xlsx` endpoint, which
generates OpenXML directly with `zipfile` and XML strings.

Options:

1. Safe update: no maintained fixed version is available for `xlsx` 0.18.5
   according to the prior audit result.
2. Replacement: a maintained Excel writer could replace it, but that is a
   behavior-changing dependency change and should be done in a separate pass
   with export regression tests.
3. Removal: if public release can rely on backend `/export/session.xlsx`,
   backend `/export/session.json`, dashboard JSON, and dashboard CSV exports,
   the unused client-side Excel service and `xlsx` dependency can likely be
   removed without changing manuscript-critical backend behavior. This should
   be verified by dashboard build tests and a search confirming no active UI
   path still imports the client-side Excel export.

No replacement or removal was performed in this audit.

## Minimum Manuscript Wording Update

Current Methods language that says the proxy is the dominant PSD peak within
0.06-0.50 Hz is incomplete after the validity correction. Replace that sentence
with:

"The RR-derived respiration proxy was computed from cleaned RR intervals after
4-Hz interpolation, linear detrending, and Welch spectral estimation. A proxy
frequency was reported only when the detrended RR spectrum showed at least 1 ms
of variability and the dominant supported peak in a 0.02-0.70-Hz diagnostic
range fell within the reliable 0.06-0.50-Hz RR-derived proxy range, subject to
an RR-event-sampling Nyquist safety constraint and a fixed peak-to-background
criterion. Unsupported spectra, ambiguous boundary leakage, and numerical
near-zero spectra were reported as unavailable rather than forced to the nearest
band edge."

Add this limitation sentence near the existing respiratory-proxy caveat:

"Because the estimate is derived from beat-to-beat RR intervals rather than a
direct respiratory sensor, high-frequency respiratory or RR oscillations can
alias into lower RR-derived frequencies; the output should therefore be
interpreted only as an experimental RR-derived spectral proxy."

## Conclusions

1. Repository hygiene: satisfactory from the previous release-preparation pass;
   not re-audited here.
2. Validation reproducibility: the ECG-to-RR and RR-stream
   quality outputs remain traceable to the included scripts and result tables.
3. Firmware equivalence: source-level firmware/replay equivalence is documented
   and the included firmware copies are byte-identical; direct compiled
   C++/ESP32 output parity on identical ECG input remains an unperformed fixture.
4. HRV implementation correctness: standard time-domain HRV metrics, RR
   filtering, baseline z-scores, event assignment, and baseline-relative segment
   calculations are verified or verified with clearly stated caveats.
5. Spectral implementation correctness: interpolation, detrending, Welch PSD,
   LF/HF integration, and PSD readiness follow the stated formulas; negligible
   RR-variability spectra are now suppressed before LF/HF and proxy reporting.
6. Respiration-proxy correctness: verified with caveat. The audited constant,
   0.05-Hz, and 0.55-Hz false estimates are corrected, supported in-band
   oscillations are recovered, and residual high-frequency alias ambiguity is
   documented as inherent to RR-only sampling.
7. Composite-index correctness: directionality, weights, robust z transforms,
   clipping, missing-component handling, spectral-readiness attenuation,
   slow-breathing attenuation, and smoothing are consistent with the intended
   experimental composite definitions.
8. Export-format consistency: implementation is clear, but manuscript wording
   must distinguish JSON, XLSX workbook worksheets, and long-format CSV rows.
9. Public-release readiness: ready after manuscript wording update. The
   manuscript should state the explicit proxy validity gate and avoid any claim
   that the RR-derived proxy is direct or fully anti-aliased respiration
   measurement.

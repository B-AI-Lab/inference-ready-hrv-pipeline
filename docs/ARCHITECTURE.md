# Architecture

The system separates source-specific RR generation from acquisition-agnostic downstream HRV processing.

## Production Pipeline

1. Acquisition source emits RR intervals.
2. A Python bridge normalizes source-specific input into timestamped RR updates.
3. `HRVProcessingEngine` computes rolling HRV metrics, RR-stream quality, baseline-referenced indices, respiration proxy, and JSON-safe state payloads.
4. Server-Sent Events stream the payloads to the dashboard.
5. The dashboard preserves subject identity, event annotations, phase labels, segment summaries, and exportable JSON/CSV structures.

## Canonical HRV/Spectral Definitions

The canonical production definitions live in `HRVConfig` in `hrv_live_processing_engine.py`:

| Quantity | Value |
|---|---:|
| Physiologic RR range | 300-2000 ms |
| PSD window | 300 s |
| Minimum PSD duration | 30 s |
| RR interpolation frequency | 4 Hz |
| LF band | 0.04-0.15 Hz |
| HF band | 0.15-0.40 Hz |
| RR-derived respiration-proxy search band | 0.06-0.50 Hz |
| Respiration-proxy bandwidth | 0.05 Hz |
| Respiration-proxy diagnostic band | 0.02-0.70 Hz |
| Minimum detrended RR variability for PSD reporting | 1.0 ms |
| Respiration-proxy peak/background requirement | 3.0x diagnostic-band median power |
| RR-sampling Nyquist safety fraction | 0.80 |

The respiration output is an RR-derived respiration proxy, not direct respiratory airflow, thoracic movement, or ventilation. The proxy is reported only when the detrended RR spectrum has sufficient nonzero variability and the dominant supported diagnostic-band oscillation falls within the reliable proxy range. The nominal search band is 0.06-0.50 Hz, but the effective upper limit is also constrained by the RR-event sampling rate to reduce alias/boundary artifacts. Boundary bins are treated conservatively: they are not snapped into the valid range when the broad diagnostic peak is outside the supported range.

LF/HF is used only as a frequency-domain engineering descriptor and as one input to experimental baseline-referenced indices. It must not be interpreted as a direct sympathetic marker.

## Slow-Breathing Handling in Autonomic Load

Frequency-dependent components of the experimental Autonomic Load Index are attenuated by PSD readiness and slow-breathing context:

- PSD readiness multiplier: `0.2 + 0.8 * psd_readiness`.
- Slow breathing is considered only when `respirationProxyHz` is available and `respirationProxyConfidence >= 0.50`.
- Slow-breathing likelihood: `sigmoid((0.15 - respirationProxyHz) * 35.0)`.
- Slow-breathing multiplier: `1.0 - 0.65 * slow_likelihood`.
- Frequency-dependent weights are multiplied by both multipliers.

If the respiration proxy is unavailable, no respiration-based attenuation is applied. These parameters are fixed in the production engine.

## Experimental Readouts

Autonomic Balance Index, Autonomic Load Index, Recovery Score, and physiological state labels are experimental engineering readouts intended for research and prototyping. They are not clinically normed measures.

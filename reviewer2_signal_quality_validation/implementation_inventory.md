# Implementation Inventory

## Source of Truth

The frozen RR-stream quality implementation is `hrv_live_processing_engine.py`.

## RR Acceptance and Rejection

- Valid finite RR bounds: 300-2000 ms.
- Recent accepted RR history for artifact decisions: 25 beats.
- Warm-up: local median/MAD rejection is inactive until at least 8 recent accepted RR intervals exist.
- Median/MAD outlier threshold: `max(140 ms, min(artifact_min_jump_ms, median*artifact_relative_jump, artifact_mad_multiplier*MAD))`.
- Frozen constants: artifact MAD multiplier 6.0, minimum jump 260 ms, relative jump 0.35.
- Successive RR quotient filter: reject if adjacent accepted RR ratio exceeds 1.30 or falls below its reciprocal.
- Resynchronization: after at least 10 consecutive rejections, stable plausible raw RR history can re-enter as `accepted_resync`.

## Artifact and RR Quality

- Artifact window duration: 60 s.
- Artifact Ratio: rejected RR records / all raw RR records in the recent artifact window.
- RR quality: `1 - Artifact Ratio`.
- The live engine does not implement a separate named Artifact Level field; this validation leaves `artifact_level` blank.

## Beat Density and Freshness

- Beat-density window: 60 s.
- Beat density: recent accepted RR count divided by expected beats over the 60 s time window, where expected beats are estimated from the recent 30 s mean RR, defaulting to 800 ms if no recent RR exists.
- Freshness: 1.0 when the last accepted RR is <=3 s old, 0.0 when >=10 s old, and linearly interpolated between those limits. If no RR has ever been accepted, freshness is 0.0.

## Signal Confidence and Status

- Signal Confidence: `clamp01(0.5*rr_quality + 0.3*beat_density + 0.2*freshness)`.
- Signal Status: `Signal Lost` if confidence <0.35 or last accepted RR is >5 s old; `Active` if confidence >=0.75; `Noisy` if confidence >=0.50; otherwise `Low Confidence`.
- Signal Confidence was sampled non-mutatingly at each 10 s window end using the submitted formula and current RR buffer state. Detector parameters, quality weights, thresholds, and status cutoffs were not tuned on NSTDB.

import type { HRVSample } from "../lib/types";
import type { AnnotatedHRVWindow, BaselineCorridor, BaselineSummary, PhaseLabel, SessionEvent } from "./types";
import { compareWindowToBaseline } from "./baselineComparator";

function finiteOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function sampleTimestampMs(sample: HRVSample): number {
  if (Number.isFinite(sample.timestamp)) {
    if (sample.timestamp > 1_000_000_000_000) return sample.timestamp;
    if (sample.timestamp > 1_000_000_000) return sample.timestamp * 1000;
  }
  return Date.now();
}

export function assignPhaseLabel(activeEvent: SessionEvent | null): PhaseLabel {
  return activeEvent?.phase ?? "none";
}

// Converts a live HRV sample into a phase-aware ML-ready window record.
export function annotateHRVWindow(
  sample: HRVSample,
  activeEvent: SessionEvent | null,
  previousSample: HRVSample | null,
  baselineSummary: BaselineSummary | null,
  baselineCorridor: BaselineCorridor | null,
  sequence: number,
): AnnotatedHRVWindow {
  const endMs = sampleTimestampMs(sample);
  const elapsedEnd = finiteOrNull(sample.elapsedSec) ?? 0;
  const previousElapsed = previousSample ? finiteOrNull(previousSample.elapsedSec) : null;
  const elapsedStart = previousElapsed !== null && previousElapsed <= elapsedEnd ? previousElapsed : Math.max(0, elapsedEnd - 1);
  const startMs = endMs - Math.max(0, elapsedEnd - elapsedStart) * 1000;
  const phaseLabel = assignPhaseLabel(activeEvent);
  const baseWindow: AnnotatedHRVWindow = {
    window_id: `window_${sequence}_${Math.round(endMs)}`,
    window_start_timestamp_iso: new Date(startMs).toISOString(),
    window_end_timestamp_iso: new Date(endMs).toISOString(),
    window_start_unix_ms: Math.round(startMs),
    window_end_unix_ms: Math.round(endMs),
    elapsed_session_time_start_s: elapsedStart,
    elapsed_session_time_end_s: elapsedEnd,
    phase_label: phaseLabel,
    active_event_id: activeEvent?.event_id ?? null,
    time_since_phase_start_s: activeEvent ? Math.max(0, elapsedEnd - activeEvent.elapsed_session_time_s) : null,
    rmssd_ms: finiteOrNull(sample.rmssd),
    sdnn_ms: finiteOrNull(sample.sdnn),
    pnn50_percent: finiteOrNull(sample.pnn50),
    mean_hr_bpm: finiteOrNull(sample.heartRate),
    signal_reliability_score: finiteOrNull(sample.signalConfidence),
    artifact_rate_percent: finiteOrNull(sample.artifactRatio) !== null ? finiteOrNull(sample.artifactRatio)! * 100 : null,
    psd_readiness_score: finiteOrNull(sample.psdReadiness),
    source_sample: sample,
    rmssd_delta_absolute: null,
    rmssd_delta_percent: null,
    rmssd_z: null,
    hr_delta_absolute: null,
    hr_delta_percent: null,
    hr_z: null,
    sdnn_delta_absolute: null,
    sdnn_delta_percent: null,
    sdnn_z: null,
    pnn50_delta_absolute: null,
    pnn50_delta_percent: null,
    pnn50_z: null,
    outside_baseline_corridor_boolean: null,
    outside_baseline_corridor_metrics: [],
  };

  return baselineSummary ? compareWindowToBaseline(baseWindow, baselineSummary, baselineCorridor) : baseWindow;
}

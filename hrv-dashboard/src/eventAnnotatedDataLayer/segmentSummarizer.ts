import type { AnnotatedHRVWindow, BaselineSummary, PhaseLabel, SegmentSummary, SessionEvent } from "./types";
import { signalInterpretability } from "./baselineCalculator";

function numeric(windows: AnnotatedHRVWindow[], key: keyof AnnotatedHRVWindow): number[] {
  return windows.map((window) => window[key]).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

function sourceNumeric(windows: AnnotatedHRVWindow[], key: keyof AnnotatedHRVWindow["source_sample"]): number[] {
  return windows.map((window) => window.source_sample[key]).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

function mean(items: number[]): number | null {
  return items.length ? items.reduce((sum, item) => sum + item, 0) / items.length : null;
}

function min(items: number[]): number | null {
  return items.length ? Math.min(...items) : null;
}

function max(items: number[]): number | null {
  return items.length ? Math.max(...items) : null;
}

function percentDelta(value: number | null, baseline: number | null): number | null {
  if (value === null || baseline === null || baseline === 0) return null;
  return ((value - baseline) / baseline) * 100;
}

function maxAbsDeviation(summary: Pick<SegmentSummary, "rmssd_delta_percent_vs_baseline" | "hr_delta_percent_vs_baseline" | "sdnn_delta_percent_vs_baseline" | "pnn50_delta_percent_vs_baseline">): [string | null, number | null] {
  const pairs: Array<[string, number | null]> = [
    ["rmssd", summary.rmssd_delta_percent_vs_baseline],
    ["hr", summary.hr_delta_percent_vs_baseline],
    ["sdnn", summary.sdnn_delta_percent_vs_baseline],
    ["pnn50", summary.pnn50_delta_percent_vs_baseline],
  ];
  const valid = pairs.filter((pair): pair is [string, number] => pair[1] !== null && Number.isFinite(pair[1]));
  if (!valid.length) return [null, null];
  return valid.reduce((best, current) => (Math.abs(current[1]) > Math.abs(best[1]) ? current : best));
}

// Creates a completed phase summary only after a stop event has been logged.
export function summarizeSegment(
  phaseLabel: Exclude<PhaseLabel, "none">,
  startEvent: SessionEvent,
  stopEvent: SessionEvent,
  annotatedWindows: AnnotatedHRVWindow[],
  baselineSummary: BaselineSummary | null,
): SegmentSummary {
  const segmentWindows = annotatedWindows.filter(
    (window) =>
      window.phase_label === phaseLabel &&
      window.active_event_id === startEvent.event_id &&
      window.elapsed_session_time_end_s >= startEvent.elapsed_session_time_s &&
      window.elapsed_session_time_end_s <= stopEvent.elapsed_session_time_s,
  );
  const rmssd = numeric(segmentWindows, "rmssd_ms");
  const hr = numeric(segmentWindows, "mean_hr_bpm");
  const sdnn = numeric(segmentWindows, "sdnn_ms");
  const pnn50 = numeric(segmentWindows, "pnn50_percent");
  const lfPower = sourceNumeric(segmentWindows, "lfPower");
  const hfPower = sourceNumeric(segmentWindows, "hfPower");
  const lfHfRatio = sourceNumeric(segmentWindows, "lfHfRatio");
  const autonomicBalance = sourceNumeric(segmentWindows, "autonomicBalanceIndex");
  const respirationProxy = sourceNumeric(segmentWindows, "respirationProxyHz");
  const respirationConfidence = sourceNumeric(segmentWindows, "respirationProxyConfidence");
  const signal = numeric(segmentWindows, "signal_reliability_score");
  const artifact = numeric(segmentWindows, "artifact_rate_percent");
  const duration = Math.max(0, stopEvent.elapsed_session_time_s - startEvent.elapsed_session_time_s);
  const outsideWindows = segmentWindows.filter((window) => window.outside_baseline_corridor_boolean);
  const meanRmssd = mean(rmssd);
  const meanHr = mean(hr);
  const meanSdnn = mean(sdnn);
  const meanPnn50 = mean(pnn50);
  const partial = {
    rmssd_delta_percent_vs_baseline: percentDelta(meanRmssd, baselineSummary?.baseline_rmssd_mean ?? null),
    hr_delta_percent_vs_baseline: percentDelta(meanHr, baselineSummary?.baseline_hr_mean ?? null),
    sdnn_delta_percent_vs_baseline: percentDelta(meanSdnn, baselineSummary?.baseline_sdnn_mean ?? null),
    pnn50_delta_percent_vs_baseline: percentDelta(meanPnn50, baselineSummary?.baseline_pnn50_mean ?? null),
  };
  const [maxMetric, maxValue] = maxAbsDeviation(partial);
  const outsideSeconds = baselineSummary ? outsideWindows.reduce((sum, window) => sum + Math.max(0, window.elapsed_session_time_end_s - window.elapsed_session_time_start_s), 0) : null;
  const signalMean = mean(signal);
  const artifactMean = mean(artifact);

  return {
    segment_id: `${phaseLabel}_${startEvent.timestamp_unix_ms}_${stopEvent.timestamp_unix_ms}`,
    segment_type: phaseLabel,
    phase_label: phaseLabel,
    start_event_id: startEvent.event_id,
    stop_event_id: stopEvent.event_id,
    segment_start_time: startEvent.timestamp_iso,
    segment_end_time: stopEvent.timestamp_iso,
    duration_s: duration,
    number_of_windows_used: segmentWindows.length,
    mean_rmssd: meanRmssd,
    min_rmssd: min(rmssd),
    max_rmssd: max(rmssd),
    mean_hr: meanHr,
    min_hr: min(hr),
    max_hr: max(hr),
    mean_sdnn: meanSdnn,
    mean_pnn50: meanPnn50,
    mean_lf_power: mean(lfPower),
    mean_hf_power: mean(hfPower),
    mean_lf_hf_ratio: mean(lfHfRatio),
    mean_autonomic_balance_index: mean(autonomicBalance),
    mean_respiration_proxy_hz: mean(respirationProxy),
    mean_respiration_proxy_confidence: mean(respirationConfidence),
    mean_signal_reliability: signalMean,
    mean_artifact_rate: artifactMean,
    ...partial,
    time_outside_baseline_corridor_s: outsideSeconds,
    percent_time_outside_baseline_corridor: outsideSeconds !== null && duration > 0 ? (outsideSeconds / duration) * 100 : null,
    max_deviation_metric: maxMetric,
    max_deviation_value: maxValue,
    interpretability_label: signalInterpretability(signalMean, artifactMean),
  };
}

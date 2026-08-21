import type { AnnotatedHRVWindow, BaselineCorridor, BaselineSummary, InterpretabilityLabel, SessionEvent } from "./types";

function values(windows: AnnotatedHRVWindow[], key: keyof AnnotatedHRVWindow): number[] {
  return windows.map((item) => item[key]).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

function mean(items: number[]): number | null {
  if (items.length === 0) return null;
  return items.reduce((sum, item) => sum + item, 0) / items.length;
}

function sd(items: number[]): number | null {
  if (items.length < 2) return null;
  const avg = mean(items);
  if (avg === null) return null;
  return Math.sqrt(items.reduce((sum, item) => sum + (item - avg) ** 2, 0) / (items.length - 1));
}

function corridor(meanValue: number | null, sdValue: number | null): [number | null, number | null] {
  if (meanValue === null || sdValue === null) return [null, null];
  return [meanValue - (2 * sdValue), meanValue + (2 * sdValue)];
}

export function signalInterpretability(signalReliability: number | null, artifactRatePercent: number | null): InterpretabilityLabel {
  const reliability = signalReliability ?? 0;
  const artifact = artifactRatePercent ?? 100;
  if (reliability >= 0.85 && artifact <= 8) return "good";
  if (reliability >= 0.7 && artifact <= 18) return "acceptable";
  if (reliability >= 0.45 && artifact <= 35) return "limited";
  return "not_interpretable";
}

// Summarizes valid baseline windows and labels baseline quality deterministically.
export function computeBaselineSummary(
  windows: AnnotatedHRVWindow[],
  baselineStart: SessionEvent,
  baselineEnd: SessionEvent,
): BaselineSummary {
  const segmentWindows = windows.filter(
    (window) =>
      window.phase_label === "baseline" &&
      window.elapsed_session_time_end_s >= baselineStart.elapsed_session_time_s &&
      window.elapsed_session_time_end_s <= baselineEnd.elapsed_session_time_s,
  );
  const validWindows = segmentWindows.filter((window) => window.rmssd_ms !== null || window.mean_hr_bpm !== null || window.sdnn_ms !== null);
  const rmssd = values(validWindows, "rmssd_ms");
  const sdnn = values(validWindows, "sdnn_ms");
  const pnn50 = values(validWindows, "pnn50_percent");
  const hr = values(validWindows, "mean_hr_bpm");
  const signal = values(validWindows, "signal_reliability_score");
  const artifact = values(validWindows, "artifact_rate_percent");
  const signalMean = mean(signal);
  const artifactMean = mean(artifact);

  return {
    baseline_start_time: baselineStart.timestamp_iso,
    baseline_end_time: baselineEnd.timestamp_iso,
    baseline_duration_s: Math.max(0, baselineEnd.elapsed_session_time_s - baselineStart.elapsed_session_time_s),
    baseline_rmssd_mean: mean(rmssd),
    baseline_rmssd_sd: sd(rmssd),
    baseline_sdnn_mean: mean(sdnn),
    baseline_sdnn_sd: sd(sdnn),
    baseline_pnn50_mean: mean(pnn50),
    baseline_pnn50_sd: sd(pnn50),
    baseline_hr_mean: mean(hr),
    baseline_hr_sd: sd(hr),
    baseline_signal_reliability_mean: signalMean,
    baseline_artifact_rate_mean: artifactMean,
    number_of_windows_used: validWindows.length,
    baseline_stability_label: signalInterpretability(signalMean, artifactMean),
  };
}

// Builds the current configurable baseline corridor as mean +/- 2 SD.
export function computeBaselineCorridor(summary: BaselineSummary): BaselineCorridor {
  const [rmssdLower, rmssdUpper] = corridor(summary.baseline_rmssd_mean, summary.baseline_rmssd_sd);
  const [hrLower, hrUpper] = corridor(summary.baseline_hr_mean, summary.baseline_hr_sd);
  const [sdnnLower, sdnnUpper] = corridor(summary.baseline_sdnn_mean, summary.baseline_sdnn_sd);
  const [pnn50Lower, pnn50Upper] = corridor(summary.baseline_pnn50_mean, summary.baseline_pnn50_sd);
  return {
    rmssd_lower: rmssdLower,
    rmssd_upper: rmssdUpper,
    hr_lower: hrLower,
    hr_upper: hrUpper,
    sdnn_lower: sdnnLower,
    sdnn_upper: sdnnUpper,
    pnn50_lower: pnn50Lower,
    pnn50_upper: pnn50Upper,
  };
}

import type { AnnotatedHRVWindow, BaselineCorridor, BaselineSummary } from "./types";

function delta(value: number | null, baseline: number | null): [number | null, number | null] {
  if (value === null || baseline === null || !Number.isFinite(baseline) || baseline === 0) return [null, null];
  const absolute = value - baseline;
  return [absolute, (absolute / baseline) * 100];
}

function zScore(value: number | null, baseline: number | null, sd: number | null): number | null {
  if (value === null || baseline === null || sd === null || !Number.isFinite(sd) || sd === 0) return null;
  return (value - baseline) / sd;
}

function outside(value: number | null, lower: number | null | undefined, upper: number | null | undefined): boolean {
  if (value === null || lower === null || lower === undefined || upper === null || upper === undefined) return false;
  return value < lower || value > upper;
}

// Adds individual baseline deltas, z-scores, and corridor flags to one window.
export function compareWindowToBaseline(
  window: AnnotatedHRVWindow,
  baselineSummary: BaselineSummary,
  baselineCorridor: BaselineCorridor | null,
): AnnotatedHRVWindow {
  const [rmssdAbs, rmssdPct] = delta(window.rmssd_ms, baselineSummary.baseline_rmssd_mean);
  const [hrAbs, hrPct] = delta(window.mean_hr_bpm, baselineSummary.baseline_hr_mean);
  const [sdnnAbs, sdnnPct] = delta(window.sdnn_ms, baselineSummary.baseline_sdnn_mean);
  const [pnn50Abs, pnn50Pct] = delta(window.pnn50_percent, baselineSummary.baseline_pnn50_mean);
  const outsideMetrics: string[] = [];

  if (baselineCorridor) {
    if (outside(window.rmssd_ms, baselineCorridor.rmssd_lower, baselineCorridor.rmssd_upper)) outsideMetrics.push("rmssd");
    if (outside(window.mean_hr_bpm, baselineCorridor.hr_lower, baselineCorridor.hr_upper)) outsideMetrics.push("hr");
    if (outside(window.sdnn_ms, baselineCorridor.sdnn_lower, baselineCorridor.sdnn_upper)) outsideMetrics.push("sdnn");
    if (outside(window.pnn50_percent, baselineCorridor.pnn50_lower, baselineCorridor.pnn50_upper)) outsideMetrics.push("pnn50");
  }

  return {
    ...window,
    rmssd_delta_absolute: rmssdAbs,
    rmssd_delta_percent: rmssdPct,
    rmssd_z: zScore(window.rmssd_ms, baselineSummary.baseline_rmssd_mean, baselineSummary.baseline_rmssd_sd),
    hr_delta_absolute: hrAbs,
    hr_delta_percent: hrPct,
    hr_z: zScore(window.mean_hr_bpm, baselineSummary.baseline_hr_mean, baselineSummary.baseline_hr_sd),
    sdnn_delta_absolute: sdnnAbs,
    sdnn_delta_percent: sdnnPct,
    sdnn_z: zScore(window.sdnn_ms, baselineSummary.baseline_sdnn_mean, baselineSummary.baseline_sdnn_sd),
    pnn50_delta_absolute: pnn50Abs,
    pnn50_delta_percent: pnn50Pct,
    pnn50_z: zScore(window.pnn50_percent, baselineSummary.baseline_pnn50_mean, baselineSummary.baseline_pnn50_sd),
    outside_baseline_corridor_boolean: baselineCorridor ? outsideMetrics.length > 0 : null,
    outside_baseline_corridor_metrics: outsideMetrics,
  };
}

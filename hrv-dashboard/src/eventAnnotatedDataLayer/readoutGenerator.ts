import type { BaselineSummary, DashboardReadout, PhaseLabel, SegmentSummary } from "./types";

function fmt(value: number | null, decimals = 0, suffix = ""): string {
  return value === null || Number.isNaN(value) ? "n/a" : `${value.toFixed(decimals)}${suffix}`;
}

function signedPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(0)}%`;
}

function phaseName(phase: PhaseLabel): string {
  const names: Record<PhaseLabel, string> = {
    none: "No active phase",
    baseline: "Baseline",
    intervention_1: "Intervention 1",
    intervention_2: "Intervention 2",
    intervention_3: "Intervention 3",
    recovery: "Recovery",
  };
  return names[phase];
}

// Produces deterministic dashboard text from completed baseline and segment summaries.
export function generateDashboardReadout(
  segmentSummary: SegmentSummary | null,
  baselineSummary: BaselineSummary | null,
): DashboardReadout {
  const created = new Date().toISOString();
  if (!segmentSummary && baselineSummary) {
    const minutes = baselineSummary.baseline_duration_s / 60;
    return {
      readout_id: `readout_baseline_${Date.now()}`,
      created_at: created,
      kind: "baseline",
      phase_label: "baseline",
      title: "Baseline saved",
      baseline_summary: baselineSummary,
      segment_summary: null,
      message: `Baseline saved: ${fmt(minutes, 1, " min")} recorded. RMSSD mean ${fmt(baselineSummary.baseline_rmssd_mean, 0, " ms")}, HR mean ${fmt(baselineSummary.baseline_hr_mean, 0, " bpm")}, signal reliability ${baselineSummary.baseline_stability_label}, baseline stability ${baselineSummary.baseline_stability_label}.`,
    };
  }

  if (segmentSummary) {
    const name = phaseName(segmentSummary.phase_label);
    const outside = fmt(segmentSummary.time_outside_baseline_corridor_s, 0, " s");
    const noBaseline = segmentSummary.rmssd_delta_percent_vs_baseline === null && segmentSummary.hr_delta_percent_vs_baseline === null;
    const recoveryHint = segmentSummary.phase_label === "recovery" && segmentSummary.percent_time_outside_baseline_corridor !== null
      ? ", return toward baseline corridor observed"
      : "";
    const message = noBaseline
      ? `${name} stored, but no baseline comparison available. Signal interpretability ${segmentSummary.interpretability_label}.`
      : `${name} vs. baseline: RMSSD ${signedPercent(segmentSummary.rmssd_delta_percent_vs_baseline)}, HR ${signedPercent(segmentSummary.hr_delta_percent_vs_baseline)}, ${outside} outside baseline corridor${recoveryHint}, signal reliability ${segmentSummary.interpretability_label}.`;

    return {
      readout_id: `readout_${segmentSummary.segment_id}_${Date.now()}`,
      created_at: created,
      kind: "segment",
      phase_label: segmentSummary.phase_label,
      title: `${name} completed`,
      baseline_summary: baselineSummary,
      segment_summary: segmentSummary,
      message,
    };
  }

  return {
    readout_id: `readout_empty_${Date.now()}`,
    created_at: created,
    kind: "segment",
    phase_label: "none",
    title: "No completed segment",
    baseline_summary: null,
    segment_summary: null,
    message: "Baseline not yet available. Start and stop a baseline recording before comparing interventions.",
  };
}

export function sendReadoutToDashboard(readout: DashboardReadout, currentReadouts: DashboardReadout[]): DashboardReadout[] {
  return [readout, ...currentReadouts];
}

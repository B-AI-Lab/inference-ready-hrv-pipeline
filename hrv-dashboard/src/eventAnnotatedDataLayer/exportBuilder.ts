import type { AnnotatedHRVWindow, BaselineCorridor, BaselineSummary, DashboardReadout, MLReadyExport, PhaseLabel, SegmentSummary, SessionEvent } from "./types";

function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function segmentInterpretabilityForWindow(window: AnnotatedHRVWindow, segments: SegmentSummary[]): string {
  const segment = segments.find(
    (item) =>
      item.phase_label === window.phase_label &&
      window.window_end_timestamp_iso >= item.segment_start_time &&
      window.window_end_timestamp_iso <= item.segment_end_time,
  );
  return segment?.interpretability_label ?? "";
}

// Builds the full session object used for local JSON export.
export function buildMLReadyExport(params: {
  sessionId: string;
  sessionStartedAt: string;
  activePhase: PhaseLabel;
  annotatedWindows: AnnotatedHRVWindow[];
  events: SessionEvent[];
  baselineSummary: BaselineSummary | null;
  baselineCorridor: BaselineCorridor | null;
  segmentSummaries: SegmentSummary[];
  dashboardReadouts: DashboardReadout[];
}): MLReadyExport {
  return {
    session_metadata: {
      session_id: params.sessionId,
      session_started_at: params.sessionStartedAt,
      active_phase: params.activePhase,
    },
    raw_rr_data_reference_or_data_if_available: null,
    computed_hrv_windows: params.annotatedWindows.map((window) => window.source_sample),
    annotated_hrv_windows: params.annotatedWindows,
    session_events: params.events,
    baseline_summary: params.baselineSummary,
    baseline_corridor: params.baselineCorridor,
    segment_summaries: params.segmentSummaries,
    dashboard_readouts: params.dashboardReadouts,
    export_created_at: new Date().toISOString(),
  };
}

// Builds one-row-per-window CSV for ML pipelines and spreadsheet review.
export function exportAnnotatedWindowsCSV(annotatedWindows: AnnotatedHRVWindow[], segmentSummaries: SegmentSummary[]): string {
  const columns = [
    "timestamp",
    "phase_label",
    "event_id",
    "time_since_phase_start_s",
    "rmssd_ms",
    "mean_hr_bpm",
    "sdnn_ms",
    "pnn50_percent",
    "signal_reliability_score",
    "artifact_rate_percent",
    "rmssd_delta_percent",
    "rmssd_z",
    "hr_delta_percent",
    "hr_z",
    "outside_baseline_corridor_boolean",
    "interpretability_label",
  ];
  const rows = annotatedWindows.map((window) => [
    window.window_end_timestamp_iso,
    window.phase_label,
    window.active_event_id,
    window.time_since_phase_start_s,
    window.rmssd_ms,
    window.mean_hr_bpm,
    window.sdnn_ms,
    window.pnn50_percent,
    window.signal_reliability_score,
    window.artifact_rate_percent,
    window.rmssd_delta_percent,
    window.rmssd_z,
    window.hr_delta_percent,
    window.hr_z,
    window.outside_baseline_corridor_boolean,
    segmentInterpretabilityForWindow(window, segmentSummaries),
  ]);

  return [columns, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
}

export function exportFullSessionJSON(exportObject: MLReadyExport): string {
  return JSON.stringify(exportObject, null, 2);
}

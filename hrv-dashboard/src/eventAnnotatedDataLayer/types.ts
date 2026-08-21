import type { HRVSample } from "../lib/types";

export type PhaseLabel = "none" | "baseline" | "intervention_1" | "intervention_2" | "intervention_3" | "recovery";
export type PhaseAction = "start" | "stop" | "manual";
export type InterpretabilityLabel = "good" | "acceptable" | "limited" | "not_interpretable";

export type SessionEventType =
  | "start_baseline"
  | "stop_save_baseline"
  | "start_intervention_1"
  | "stop_intervention_1"
  | "start_intervention_2"
  | "stop_intervention_2"
  | "start_intervention_3"
  | "stop_intervention_3"
  | "start_recovery"
  | "stop_recovery"
  | "manual_event"
  | "biological_sample_blood"
  | "biological_sample_saliva"
  | "biological_sample_sweat";

export type BiologicalSampleType = "blood" | "saliva" | "sweat";

export interface SessionEvent {
  event_id: string;
  event_type: SessionEventType;
  event_label: string;
  phase: PhaseLabel;
  action: PhaseAction;
  timestamp_iso: string;
  timestamp_unix_ms: number;
  elapsed_session_time_s: number;
  optional_user_note: string | null;
  event_category?: "biological_sample";
  sample_type?: BiologicalSampleType;
  sample_number?: number;
}

export interface AnnotatedHRVWindow {
  window_id: string;
  window_start_timestamp_iso: string;
  window_end_timestamp_iso: string;
  window_start_unix_ms: number;
  window_end_unix_ms: number;
  elapsed_session_time_start_s: number;
  elapsed_session_time_end_s: number;
  phase_label: PhaseLabel;
  active_event_id: string | null;
  time_since_phase_start_s: number | null;
  rmssd_ms: number | null;
  sdnn_ms: number | null;
  pnn50_percent: number | null;
  mean_hr_bpm: number | null;
  signal_reliability_score: number | null;
  artifact_rate_percent: number | null;
  psd_readiness_score: number | null;
  source_sample: HRVSample;
  rmssd_delta_absolute: number | null;
  rmssd_delta_percent: number | null;
  rmssd_z: number | null;
  hr_delta_absolute: number | null;
  hr_delta_percent: number | null;
  hr_z: number | null;
  sdnn_delta_absolute: number | null;
  sdnn_delta_percent: number | null;
  sdnn_z: number | null;
  pnn50_delta_absolute: number | null;
  pnn50_delta_percent: number | null;
  pnn50_z: number | null;
  outside_baseline_corridor_boolean: boolean | null;
  outside_baseline_corridor_metrics: string[];
}

export interface BaselineSummary {
  baseline_start_time: string;
  baseline_end_time: string;
  baseline_duration_s: number;
  baseline_rmssd_mean: number | null;
  baseline_rmssd_sd: number | null;
  baseline_sdnn_mean: number | null;
  baseline_sdnn_sd: number | null;
  baseline_pnn50_mean: number | null;
  baseline_pnn50_sd: number | null;
  baseline_hr_mean: number | null;
  baseline_hr_sd: number | null;
  baseline_signal_reliability_mean: number | null;
  baseline_artifact_rate_mean: number | null;
  number_of_windows_used: number;
  baseline_stability_label: "good" | "acceptable" | "limited" | "not_interpretable";
}

export interface BaselineCorridor {
  rmssd_lower: number | null;
  rmssd_upper: number | null;
  hr_lower: number | null;
  hr_upper: number | null;
  sdnn_lower: number | null;
  sdnn_upper: number | null;
  pnn50_lower: number | null;
  pnn50_upper: number | null;
}

export interface SegmentSummary {
  segment_id: string;
  segment_type: Exclude<PhaseLabel, "none">;
  phase_label: Exclude<PhaseLabel, "none">;
  start_event_id: string;
  stop_event_id: string;
  segment_start_time: string;
  segment_end_time: string;
  duration_s: number;
  number_of_windows_used: number;
  mean_rmssd: number | null;
  min_rmssd: number | null;
  max_rmssd: number | null;
  mean_hr: number | null;
  min_hr: number | null;
  max_hr: number | null;
  mean_sdnn: number | null;
  mean_pnn50: number | null;
  mean_lf_power: number | null;
  mean_hf_power: number | null;
  mean_lf_hf_ratio: number | null;
  mean_autonomic_balance_index: number | null;
  mean_respiration_proxy_hz: number | null;
  mean_respiration_proxy_confidence: number | null;
  mean_signal_reliability: number | null;
  mean_artifact_rate: number | null;
  rmssd_delta_percent_vs_baseline: number | null;
  hr_delta_percent_vs_baseline: number | null;
  sdnn_delta_percent_vs_baseline: number | null;
  pnn50_delta_percent_vs_baseline: number | null;
  time_outside_baseline_corridor_s: number | null;
  percent_time_outside_baseline_corridor: number | null;
  max_deviation_metric: string | null;
  max_deviation_value: number | null;
  interpretability_label: InterpretabilityLabel;
}

export interface DashboardReadout {
  readout_id: string;
  created_at: string;
  kind: "baseline" | "segment";
  phase_label: PhaseLabel;
  title: string;
  message: string;
  segment_summary: SegmentSummary | null;
  baseline_summary: BaselineSummary | null;
}

export interface MLReadyExport {
  session_metadata: {
    session_id: string;
    session_started_at: string;
    active_phase: PhaseLabel;
  };
  raw_rr_data_reference_or_data_if_available: null;
  computed_hrv_windows: HRVSample[];
  annotated_hrv_windows: AnnotatedHRVWindow[];
  session_events: SessionEvent[];
  baseline_summary: BaselineSummary | null;
  baseline_corridor: BaselineCorridor | null;
  segment_summaries: SegmentSummary[];
  dashboard_readouts: DashboardReadout[];
  export_created_at: string;
}

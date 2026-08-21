import type { BiologicalSampleType, PhaseAction, PhaseLabel, SessionEvent, SessionEventType } from "./types";

const EVENT_LABELS: Record<SessionEventType, string> = {
  start_baseline: "Start Baseline",
  stop_save_baseline: "Stop / Save Baseline",
  start_intervention_1: "Start Intervention 1",
  stop_intervention_1: "Stop Intervention 1",
  start_intervention_2: "Start Intervention 2",
  stop_intervention_2: "Stop Intervention 2",
  start_intervention_3: "Start Intervention 3",
  stop_intervention_3: "Stop Intervention 3",
  start_recovery: "Start Recovery",
  stop_recovery: "Stop Recovery",
  manual_event: "Manual Event",
  biological_sample_blood: "Blood sample",
  biological_sample_saliva: "Saliva sample",
  biological_sample_sweat: "Sweat sample",
};

const EVENT_PHASES: Record<SessionEventType, PhaseLabel> = {
  start_baseline: "baseline",
  stop_save_baseline: "baseline",
  start_intervention_1: "intervention_1",
  stop_intervention_1: "intervention_1",
  start_intervention_2: "intervention_2",
  stop_intervention_2: "intervention_2",
  start_intervention_3: "intervention_3",
  stop_intervention_3: "intervention_3",
  start_recovery: "recovery",
  stop_recovery: "recovery",
  manual_event: "none",
  biological_sample_blood: "none",
  biological_sample_saliva: "none",
  biological_sample_sweat: "none",
};

const EVENT_ACTIONS: Record<SessionEventType, PhaseAction> = {
  start_baseline: "start",
  stop_save_baseline: "stop",
  start_intervention_1: "start",
  stop_intervention_1: "stop",
  start_intervention_2: "start",
  stop_intervention_2: "stop",
  start_intervention_3: "start",
  stop_intervention_3: "stop",
  start_recovery: "start",
  stop_recovery: "stop",
  manual_event: "manual",
  biological_sample_blood: "manual",
  biological_sample_saliva: "manual",
  biological_sample_sweat: "manual",
};

const SAMPLE_EVENT_TYPE: Record<BiologicalSampleType, SessionEventType> = {
  blood: "biological_sample_blood",
  saliva: "biological_sample_saliva",
  sweat: "biological_sample_sweat",
};

// Creates deterministic, structured event metadata from dashboard controls.
export function logSessionEvent(
  eventType: SessionEventType,
  elapsedSessionTimeS: number,
  optionalUserNote: string | null = null,
): SessionEvent {
  const now = Date.now();
  return {
    event_id: `${eventType}_${now}`,
    event_type: eventType,
    event_label: EVENT_LABELS[eventType],
    phase: EVENT_PHASES[eventType],
    action: EVENT_ACTIONS[eventType],
    timestamp_iso: new Date(now).toISOString(),
    timestamp_unix_ms: now,
    elapsed_session_time_s: elapsedSessionTimeS,
    optional_user_note: optionalUserNote,
  };
}

// Creates a structured biological sample collection event with machine-readable fields.
export function logBiologicalSampleEvent(
  sampleType: BiologicalSampleType,
  sampleNumber: number,
  elapsedSessionTimeS: number,
): SessionEvent {
  const eventType = SAMPLE_EVENT_TYPE[sampleType];
  const baseLabel = EVENT_LABELS[eventType];
  const now = Date.now();
  return {
    event_id: `${eventType}_${sampleNumber}_${now}`,
    event_type: eventType,
    event_label: `${baseLabel} ${sampleNumber}`,
    phase: EVENT_PHASES[eventType],
    action: EVENT_ACTIONS[eventType],
    timestamp_iso: new Date(now).toISOString(),
    timestamp_unix_ms: now,
    elapsed_session_time_s: elapsedSessionTimeS,
    optional_user_note: null,
    event_category: "biological_sample",
    sample_type: sampleType,
    sample_number: sampleNumber,
  };
}

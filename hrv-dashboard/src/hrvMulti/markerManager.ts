import type { GlobalMarkerEvent, MarkerPhase } from "./types";

const PHASE_LABEL: Record<MarkerPhase, string> = {
  idle: "Idle",
  baseline: "Baseline",
  task: "Task",
  recovery: "Recovery",
};

export function buildPhaseMarker(
  action: "start" | "end",
  phase: Exclude<MarkerPhase, "idle">,
  elapsedSec: number,
  affectedSubjects: string[],
): GlobalMarkerEvent {
  const now = Date.now();
  const label = action === "start" ? `Start ${PHASE_LABEL[phase]}` : `End ${PHASE_LABEL[phase]}`;
  return {
    eventId: `${action === "start" ? "phase_start" : "phase_end"}_${phase}_${now}`,
    timestamp: now,
    elapsedSec,
    eventType: action === "start" ? "phase_start" : "phase_end",
    eventLabel: label,
    phase,
    affectedSubjects,
    createdFrom: "global_marker_control",
    notes: null,
  };
}

export function buildCustomMarker(
  label: string,
  elapsedSec: number,
  affectedSubjects: string[],
  notes: string | null = null,
): GlobalMarkerEvent {
  const now = Date.now();
  return {
    eventId: `custom_marker_${now}`,
    timestamp: now,
    elapsedSec,
    eventType: "custom_marker",
    eventLabel: label || "Marker",
    phase: null,
    affectedSubjects,
    createdFrom: "global_marker_control",
    notes,
  };
}

export function phaseAfterMarker(marker: GlobalMarkerEvent, current: MarkerPhase): MarkerPhase {
  if (marker.eventType === "phase_start" && marker.phase) return marker.phase;
  if (marker.eventType === "phase_end") return "idle";
  return current;
}

import type { HRVSample, RecoveryEvent } from "../lib/types";

export type MarkerPhase = "idle" | "baseline" | "task" | "recovery";
export type StreamStatus = "connected" | "simulated" | "paused" | "disconnected";
export type SessionStatus = "idle" | "running" | "paused" | "stopped";
export type MarkerEventType = "phase_start" | "phase_end" | "custom_marker";

export interface Subject {
  subjectId: string;
  displayName: string;
  active: boolean;
  visible: boolean;
  streamStatus: StreamStatus;
  source: string;
  macAddress: string;
  colorToken: string;
}

export interface MultiSubjectHRVSample extends HRVSample {
  subjectId: string;
  sessionId: string;
  currentPhase: MarkerPhase;
  activeMarkerId: string | null;
  source: string;
}

export interface GlobalMarkerEvent {
  eventId: string;
  timestamp: number;
  elapsedSec: number;
  eventType: MarkerEventType;
  eventLabel: string;
  phase: MarkerPhase | null;
  affectedSubjects: string[];
  createdFrom: "global_marker_control";
  notes?: string | null;
}

export interface SessionMeta {
  sessionId: string;
  startedAt: string;
  status: SessionStatus;
}

export interface SubjectStreamData {
  history: MultiSubjectHRVSample[];
  events: GlobalMarkerEvent[];
  recoveryEvents: RecoveryEvent[];
}

export const DASHBOARD_VERSION = "1.0.0-multisubject";

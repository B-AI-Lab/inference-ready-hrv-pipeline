import * as XLSX from "xlsx";
import { downloadTextFile } from "../lib/fileDownload";
import { DASHBOARD_VERSION } from "./types";
import type { GlobalMarkerEvent, MultiSubjectHRVSample, SessionMeta, Subject } from "./types";

function sanitizeFilenamePart(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, "_");
}

function activeMarkerLabel(sample: MultiSubjectHRVSample, events: GlobalMarkerEvent[]): string {
  if (!sample.activeMarkerId) return "";
  return events.find((event) => event.eventId === sample.activeMarkerId)?.eventLabel ?? "";
}

export function buildSubjectJSON(
  subject: Subject,
  sessionMeta: SessionMeta,
  history: MultiSubjectHRVSample[],
  events: GlobalMarkerEvent[],
) {
  return {
    subject_metadata: {
      subjectId: subject.subjectId,
      displayName: subject.displayName,
      macAddress: subject.macAddress,
      streamStatus: subject.streamStatus,
    },
    session_metadata: {
      sessionId: sessionMeta.sessionId,
      startedAt: sessionMeta.startedAt,
      status: sessionMeta.status,
    },
    device_metadata: {
      source: subject.source,
      macAddress: subject.macAddress,
    },
    hrv_samples: history,
    events,
    export_created_at: new Date().toISOString(),
    dashboard_version: DASHBOARD_VERSION,
  };
}

// One JSON file per subject, named after the (simulated) sensor's BLE MAC address.
export function exportSubjectJSON(
  subject: Subject,
  sessionMeta: SessionMeta,
  history: MultiSubjectHRVSample[],
  events: GlobalMarkerEvent[],
): void {
  const filename = `${sanitizeFilenamePart(subject.macAddress)}.json`;
  downloadTextFile(filename, JSON.stringify(buildSubjectJSON(subject, sessionMeta, history, events), null, 2), "application/json");
}

function sampleRow(subject: Subject, sample: MultiSubjectHRVSample, events: GlobalMarkerEvent[]) {
  return {
    timestamp: sample.timestamp,
    subjectId: sample.subjectId,
    sessionId: sample.sessionId,
    macAddress: subject.macAddress,
    heartRate: sample.heartRate,
    rrIntervalMs: sample.rrMs ?? null,
    RMSSD: sample.rmssd,
    SDNN: sample.sdnn,
    pNN50: sample.pnn50,
    LFHF: sample.lfHfRatio,
    currentPhase: sample.currentPhase,
    activeEventId: sample.activeMarkerId ?? "",
    eventLabelIfAny: activeMarkerLabel(sample, events),
    source: sample.source,
  };
}

function uniqueSheetName(base: string, used: Set<string>): string {
  const trimmedBase = base.replace(/[\\/?*[\]:]/g, "_").slice(0, 31);
  let candidate = trimmedBase;
  let suffix = 1;
  while (used.has(candidate)) {
    candidate = `${trimmedBase.slice(0, 28)}_${suffix++}`;
  }
  used.add(candidate);
  return candidate;
}

// One workbook, one sheet per subject/dataset.
export function buildWorkbook(
  subjects: Subject[],
  dataBySubject: Record<string, { history: MultiSubjectHRVSample[]; events: GlobalMarkerEvent[] }>,
): XLSX.WorkBook {
  const workbook = XLSX.utils.book_new();
  const usedNames = new Set<string>();
  for (const subject of subjects) {
    const data = dataBySubject[subject.subjectId];
    const rows = (data?.history ?? []).map((sample) => sampleRow(subject, sample, data?.events ?? []));
    const sheet = XLSX.utils.json_to_sheet(rows);
    XLSX.utils.book_append_sheet(workbook, sheet, uniqueSheetName(subject.displayName, usedNames));
  }
  return workbook;
}

export function exportSessionExcel(
  subjects: Subject[],
  sessionMeta: SessionMeta,
  dataBySubject: Record<string, { history: MultiSubjectHRVSample[]; events: GlobalMarkerEvent[] }>,
): void {
  const workbook = buildWorkbook(subjects, dataBySubject);
  const sessionLabel = sessionMeta.sessionId.replace(/^session_/, "");
  XLSX.writeFile(workbook, `session_${sessionLabel}_all_subjects.xlsx`);
}

// Per active subject: one JSON file named by MAC address, plus one combined
// multi-sheet Excel workbook (one sheet per subject/dataset).
export function exportAllActiveSubjects(
  subjects: Subject[],
  sessionMeta: SessionMeta,
  dataBySubject: Record<string, { history: MultiSubjectHRVSample[]; events: GlobalMarkerEvent[] }>,
): void {
  const activeSubjects = subjects.filter((s) => s.active);
  for (const subject of activeSubjects) {
    const data = dataBySubject[subject.subjectId];
    exportSubjectJSON(subject, sessionMeta, data?.history ?? [], data?.events ?? []);
  }
  exportSessionExcel(activeSubjects, sessionMeta, dataBySubject);
}

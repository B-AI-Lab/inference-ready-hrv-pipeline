import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { HRVSample } from "../lib/types";
import { computeBaselineCorridor, computeBaselineSummary } from "./baselineCalculator";
import { buildMLReadyExport, exportAnnotatedWindowsCSV, exportFullSessionJSON } from "./exportBuilder";
import { logBiologicalSampleEvent, logSessionEvent } from "./eventLogger";
import { annotateHRVWindow } from "./phaseLabeler";
import { generateDashboardReadout, sendReadoutToDashboard } from "./readoutGenerator";
import { summarizeSegment } from "./segmentSummarizer";
import type {
  AnnotatedHRVWindow,
  BaselineCorridor,
  BaselineSummary,
  BiologicalSampleType,
  DashboardReadout,
  MLReadyExport,
  PhaseLabel,
  SegmentSummary,
  SessionEvent,
  SessionEventType,
} from "./types";

function phaseStartEventType(phase: PhaseLabel): SessionEventType | null {
  if (phase === "baseline") return "start_baseline";
  if (phase === "intervention_1") return "start_intervention_1";
  if (phase === "intervention_2") return "start_intervention_2";
  if (phase === "intervention_3") return "start_intervention_3";
  if (phase === "recovery") return "start_recovery";
  return null;
}

function stopEventTypePhase(eventType: SessionEventType): Exclude<PhaseLabel, "none"> | null {
  if (eventType === "stop_save_baseline") return "baseline";
  if (eventType === "stop_intervention_1") return "intervention_1";
  if (eventType === "stop_intervention_2") return "intervention_2";
  if (eventType === "stop_intervention_3") return "intervention_3";
  if (eventType === "stop_recovery") return "recovery";
  return null;
}

function isStart(eventType: SessionEventType): boolean {
  return eventType.startsWith("start_");
}

export function useEventAnnotatedDataLayer(sample: HRVSample) {
  const [sessionId] = useState(() => `session_${Date.now()}`);
  const [sessionStartedAt] = useState(() => new Date().toISOString());
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [activeEvent, setActiveEvent] = useState<SessionEvent | null>(null);
  const [annotatedWindows, setAnnotatedWindows] = useState<AnnotatedHRVWindow[]>([]);
  const [baselineSummary, setBaselineSummary] = useState<BaselineSummary | null>(null);
  const [baselineCorridor, setBaselineCorridor] = useState<BaselineCorridor | null>(null);
  const [segmentSummaries, setSegmentSummaries] = useState<SegmentSummary[]>([]);
  const [dashboardReadouts, setDashboardReadouts] = useState<DashboardReadout[]>([]);
  const [warning, setWarning] = useState<string | null>(null);
  const previousSampleRef = useRef<HRVSample | null>(null);
  const sequenceRef = useRef(0);
  const activeEventRef = useRef<SessionEvent | null>(null);
  const baselineSummaryRef = useRef<BaselineSummary | null>(null);
  const baselineCorridorRef = useRef<BaselineCorridor | null>(null);
  const annotatedWindowsRef = useRef<AnnotatedHRVWindow[]>([]);

  useEffect(() => {
    activeEventRef.current = activeEvent;
  }, [activeEvent]);

  useEffect(() => {
    baselineSummaryRef.current = baselineSummary;
    baselineCorridorRef.current = baselineCorridor;
  }, [baselineSummary, baselineCorridor]);

  useEffect(() => {
    annotatedWindowsRef.current = annotatedWindows;
  }, [annotatedWindows]);

  useEffect(() => {
    if (!Number.isFinite(sample.elapsedSec)) return;
    const previous = previousSampleRef.current;
    if (previous && previous.elapsedSec === sample.elapsedSec && previous.timestamp === sample.timestamp) return;
    const next = annotateHRVWindow(
      sample,
      activeEventRef.current,
      previous,
      baselineSummaryRef.current,
      baselineCorridorRef.current,
      sequenceRef.current,
    );
    sequenceRef.current += 1;
    previousSampleRef.current = sample;
    setAnnotatedWindows((items) => [...items, next]);
  }, [sample]);

  const logBiologicalSample = useCallback((sampleType: BiologicalSampleType) => {
    setEvents((current) => {
      const sampleEventType = `biological_sample_${sampleType}` as SessionEventType;
      const count = current.filter((e) => e.event_type === sampleEventType).length;
      const sampleNumber = count + 1;
      const elapsed = Number.isFinite(sample.elapsedSec) ? sample.elapsedSec : 0;
      const event = logBiologicalSampleEvent(sampleType, sampleNumber, elapsed);
      return [...current, event];
    });
  }, [sample.elapsedSec]);

  const logEvent = useCallback((eventType: SessionEventType, optionalUserNote: string | null = null) => {
    setWarning(null);
    const phaseToStop = stopEventTypePhase(eventType);
    const elapsed = Number.isFinite(sample.elapsedSec) ? sample.elapsedSec : 0;

    if (isStart(eventType)) {
      if (activeEventRef.current) {
        setWarning("Please stop the current phase before starting a new one.");
        return;
      }
      const event = logSessionEvent(eventType, elapsed, optionalUserNote);
      setEvents((items) => [...items, event]);
      activeEventRef.current = event;
      setActiveEvent(event);
      return;
    }

    if (eventType === "manual_event") {
      const event = logSessionEvent(eventType, elapsed, optionalUserNote);
      setEvents((items) => [...items, event]);
      return;
    }

    if (!phaseToStop || activeEventRef.current?.phase !== phaseToStop) {
      setWarning("No matching active phase is running.");
      return;
    }

    const startEvent = activeEventRef.current;
    const stopEvent = logSessionEvent(eventType, elapsed, optionalUserNote);
    const windows = annotatedWindowsRef.current;
    setEvents((items) => [...items, stopEvent]);
    activeEventRef.current = null;
    setActiveEvent(null);

    if (phaseToStop === "baseline") {
      const summary = computeBaselineSummary(windows, startEvent, stopEvent);
      const corridor = computeBaselineCorridor(summary);
      const readout = generateDashboardReadout(null, summary);
      baselineSummaryRef.current = summary;
      baselineCorridorRef.current = corridor;
      setBaselineSummary(summary);
      setBaselineCorridor(corridor);
      setDashboardReadouts((items) => sendReadoutToDashboard(readout, items));
      return;
    }

    const summary = summarizeSegment(phaseToStop, startEvent, stopEvent, windows, baselineSummaryRef.current);
    const readout = generateDashboardReadout(summary, baselineSummaryRef.current);
    setSegmentSummaries((items) => [summary, ...items]);
    setDashboardReadouts((items) => sendReadoutToDashboard(readout, items));
  }, [sample.elapsedSec]);

  const exportObject: MLReadyExport = useMemo(() => buildMLReadyExport({
    sessionId,
    sessionStartedAt,
    activePhase: activeEvent?.phase ?? "none",
    annotatedWindows,
    events,
    baselineSummary,
    baselineCorridor,
    segmentSummaries,
    dashboardReadouts,
  }), [activeEvent?.phase, annotatedWindows, baselineCorridor, baselineSummary, dashboardReadouts, events, segmentSummaries, sessionId, sessionStartedAt]);

  return {
    activePhase: activeEvent?.phase ?? "none",
    activeEvent,
    currentElapsedSessionTimeS: Number.isFinite(sample.elapsedSec) ? sample.elapsedSec : 0,
    events,
    annotatedWindows,
    baselineSummary,
    baselineCorridor,
    segmentSummaries,
    dashboardReadouts,
    latestReadout: dashboardReadouts[0] ?? null,
    warning,
    exportReady: annotatedWindows.length > 0,
    logEvent,
    startEventTypeForPhase: phaseStartEventType,
    buildMLReadyExport: () => exportObject,
    exportAnnotatedWindowsCSV: () => exportAnnotatedWindowsCSV(annotatedWindows, segmentSummaries),
    exportFullSessionJSON: () => exportFullSessionJSON(exportObject),
    logBiologicalSample,
  };
}

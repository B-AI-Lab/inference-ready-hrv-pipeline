import { useCallback, useEffect, useRef, useState } from "react";
import type { HRVDashboardPayload, QualityState, RecoveryEvent } from "../lib/types";
import { createMockState, mockHRVGenerator } from "../hooks/useMockHRVStream";
import type { MockState, SubjectSeedParams } from "../hooks/useMockHRVStream";
import { createInitialSubjects, createSubject, seedForSlot, MAX_SUBJECTS } from "./subjectRegistry";
import { buildCustomMarker, buildPhaseMarker, phaseAfterMarker } from "./markerManager";
import type {
  GlobalMarkerEvent, MarkerPhase, MultiSubjectHRVSample, SessionMeta, Subject,
} from "./types";

export interface SubjectDataEntry {
  history: MultiSubjectHRVSample[];
  events: GlobalMarkerEvent[];
  recoveryEvents: RecoveryEvent[];
  quality: QualityState;
}

const EMPTY_QUALITY: QualityState = {
  nRawRR: 0, nValidRR: 0, nRejectedRR: 0, artifactRatioRecent: 0,
  signalStatus: "Active", psdWindowFilledSec: 0, psdReadiness: 0,
};

const DEFAULT_MULTI_STREAM_URL = "http://127.0.0.1:8765/stream";

interface LiveSubjectEvent {
  subject: Partial<Subject> & {
    subjectId: string;
    displayName?: string;
    macAddress?: string;
    source?: string;
    streamStatus?: Subject["streamStatus"];
    colorToken?: string;
  };
  payload: HRVDashboardPayload;
}

function blankEntry(): SubjectDataEntry {
  return { history: [], events: [], recoveryEvents: [], quality: EMPTY_QUALITY };
}

function newSessionMeta(): SessionMeta {
  return { sessionId: `session_${Date.now()}`, startedAt: new Date().toISOString(), status: "idle" };
}

function multiStreamUrl(): string {
  const multi = import.meta.env.VITE_HRV_MULTI_STREAM_URL;
  if (typeof multi === "string" && multi.trim()) return multi.trim();
  const single = import.meta.env.VITE_HRV_STREAM_URL;
  if (typeof single === "string" && single.trim()) return single.trim();
  return DEFAULT_MULTI_STREAM_URL;
}

function normalizeLiveSubject(input: LiveSubjectEvent["subject"], fallbackIndex: number): Subject {
  const fallback = createSubject(fallbackIndex);
  return {
    ...fallback,
    subjectId: input.subjectId,
    displayName: input.displayName || input.subjectId,
    active: input.active ?? true,
    visible: input.visible ?? true,
    streamStatus: input.streamStatus ?? "connected",
    source: input.source || "Polar H10 BLE",
    macAddress: input.macAddress || input.subjectId,
    colorToken: input.colorToken || fallback.colorToken,
  };
}

export interface MultiSubjectHRVStreamOutput {
  subjects: Subject[];
  dataBySubject: Record<string, SubjectDataEntry>;
  markerEvents: GlobalMarkerEvent[];
  session: SessionMeta;
  currentPhase: MarkerPhase;
  setSubjectCount: (n: number) => void;
  setSubjectActive: (subjectId: string, active: boolean) => void;
  setSubjectVisible: (subjectId: string, visible: boolean) => void;
  showAll: () => void;
  hideAll: () => void;
  focusOn: (subjectId: string) => void;
  startSession: () => void;
  pauseSession: () => void;
  stopSession: () => void;
  resetSession: () => void;
  triggerPhase: (phase: Exclude<MarkerPhase, "idle">, action: "start" | "end") => void;
  addCustomMarker: (label: string, note?: string | null) => void;
}

export function useMultiSubjectHRVStream(): MultiSubjectHRVStreamOutput {
  const [subjects, setSubjects] = useState<Subject[]>(() => createInitialSubjects(1));
  const [dataBySubject, setDataBySubject] = useState<Record<string, SubjectDataEntry>>({});
  const [markerEvents, setMarkerEvents] = useState<GlobalMarkerEvent[]>([]);
  const [session, setSession] = useState<SessionMeta>(newSessionMeta);
  const [currentPhase, setCurrentPhaseState] = useState<MarkerPhase>("idle");

  const subjectsRef = useRef<Subject[]>(subjects);
  const dataBySubjectRef = useRef<Record<string, SubjectDataEntry>>(dataBySubject);
  const sessionRef = useRef<SessionMeta>(session);
  const currentPhaseRef = useRef<MarkerPhase>("idle");
  const elapsedSecRef = useRef(0);
  const activeMarkerIdRef = useRef<Map<string, string | null>>(new Map());
  const simMapRef = useRef<Map<string, { simState: MockState; seed: SubjectSeedParams }>>(new Map());
  const liveModeRef = useRef(false);

  useEffect(() => { subjectsRef.current = subjects; }, [subjects]);
  useEffect(() => { dataBySubjectRef.current = dataBySubject; }, [dataBySubject]);
  useEffect(() => { sessionRef.current = session; }, [session]);

  useEffect(() => {
    const source = new EventSource(multiStreamUrl());

    source.addEventListener("subject", (event) => {
      try {
        const message = JSON.parse(event.data) as LiveSubjectEvent;
        if (!message.subject?.subjectId || !message.payload?.sample) return;

        const subjectId = message.subject.subjectId;
        liveModeRef.current = true;

        setSubjects((prev) => {
          const existingIndex = prev.findIndex((s) => s.subjectId === subjectId);
          const nextSubject = normalizeLiveSubject(message.subject, existingIndex >= 0 ? existingIndex : prev.length);
          if (existingIndex >= 0) {
            return prev.map((s, index) => (index === existingIndex
              ? { ...s, ...nextSubject, active: s.active, visible: s.visible, streamStatus: "connected" }
              : s));
          }
          const shouldReplaceSimulated = prev.every((s) => s.streamStatus === "simulated")
            && Object.keys(dataBySubjectRef.current).length === 0;
          if (shouldReplaceSimulated) return [nextSubject];
          if (prev.length >= MAX_SUBJECTS) return prev;
          return [...prev, nextSubject];
        });

        const phase = currentPhaseRef.current;
        const sessionId = sessionRef.current.sessionId;
        const tagged: MultiSubjectHRVSample = {
          ...message.payload.sample,
          subjectId,
          sessionId,
          currentPhase: phase,
          activeMarkerId: activeMarkerIdRef.current.get(subjectId) ?? null,
          source: message.subject.source || "Polar H10 BLE",
        };
        elapsedSecRef.current = Math.max(elapsedSecRef.current, tagged.elapsedSec);

        setDataBySubject((prev) => {
          const existing = prev[subjectId] ?? blankEntry();
          return {
            ...prev,
            [subjectId]: {
              ...existing,
              history: [...existing.history, tagged],
              recoveryEvents: message.payload.events,
              quality: message.payload.quality,
            },
          };
        });
      } catch (error) {
        console.warn("Ignoring malformed multi-subject HRV stream payload", error);
      }
    });

    source.addEventListener("status", (event) => {
      try {
        const status = JSON.parse(event.data) as { subjects?: Array<{ subject?: Partial<Subject>; connected?: boolean }> };
        if (!Array.isArray(status.subjects)) return;
        setSubjects((prev) => prev.map((subject) => {
          const statusSubject = status.subjects?.find((item) => item.subject?.subjectId === subject.subjectId);
          if (!statusSubject) return subject;
          return { ...subject, streamStatus: statusSubject.connected ? "connected" : "disconnected" };
        }));
      } catch {
        // Status events are advisory; malformed ones should not interrupt charting.
      }
    });

    source.onerror = () => {
      setSubjects((prev) => liveModeRef.current
        ? prev.map((s) => ({ ...s, streamStatus: s.streamStatus === "connected" ? "disconnected" : s.streamStatus }))
        : prev);
    };

    return () => source.close();
  }, []);

  // Keep one simulator instance per subject, seeded by slot index for stable variability.
  useEffect(() => {
    subjects.forEach((subject, index) => {
      if (!simMapRef.current.has(subject.subjectId)) {
        simMapRef.current.set(subject.subjectId, { simState: createMockState(), seed: seedForSlot(index) });
      }
    });
  }, [subjects]);

  // 1 Hz tick: advance every active subject's simulator, tag with current phase/marker.
  useEffect(() => {
    const id = window.setInterval(() => {
      if (liveModeRef.current) return;
      if (sessionRef.current.status !== "running") return;
      const activeSubjects = subjectsRef.current.filter((s) => s.active);
      if (activeSubjects.length === 0) return;
      elapsedSecRef.current += 1;
      const phase = currentPhaseRef.current;
      const sessionId = sessionRef.current.sessionId;

      setDataBySubject((prev) => {
        const next = { ...prev };
        for (const subject of activeSubjects) {
          const sim = simMapRef.current.get(subject.subjectId);
          if (!sim) continue;
          const payload = mockHRVGenerator(sim.simState, sim.seed);
          const tagged: MultiSubjectHRVSample = {
            ...payload.sample,
            subjectId: subject.subjectId,
            sessionId,
            currentPhase: phase,
            activeMarkerId: activeMarkerIdRef.current.get(subject.subjectId) ?? null,
            source: subject.source,
          };
          const existing = next[subject.subjectId] ?? blankEntry();
          next[subject.subjectId] = {
            ...existing,
            history: [...existing.history, tagged],
            recoveryEvents: payload.events,
            quality: payload.quality,
          };
        }
        return next;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  const applyMarker = useCallback((marker: GlobalMarkerEvent) => {
    setMarkerEvents((prev) => [...prev, marker]);
    currentPhaseRef.current = phaseAfterMarker(marker, currentPhaseRef.current);
    setCurrentPhaseState(currentPhaseRef.current);
    for (const subjectId of marker.affectedSubjects) {
      activeMarkerIdRef.current.set(subjectId, marker.eventType === "phase_end" ? null : marker.eventId);
    }
    setDataBySubject((prev) => {
      const next = { ...prev };
      for (const subjectId of marker.affectedSubjects) {
        const existing = next[subjectId] ?? blankEntry();
        next[subjectId] = { ...existing, events: [...existing.events, marker] };
      }
      return next;
    });
  }, []);

  const triggerPhase = useCallback((phase: Exclude<MarkerPhase, "idle">, action: "start" | "end") => {
    const activeIds = subjectsRef.current.filter((s) => s.active).map((s) => s.subjectId);
    applyMarker(buildPhaseMarker(action, phase, elapsedSecRef.current, activeIds));
  }, [applyMarker]);

  const addCustomMarker = useCallback((label: string, note: string | null = null) => {
    const activeIds = subjectsRef.current.filter((s) => s.active).map((s) => s.subjectId);
    applyMarker(buildCustomMarker(label, elapsedSecRef.current, activeIds, note));
  }, [applyMarker]);

  const setSubjectCount = useCallback((n: number) => {
    const bounded = Math.max(1, Math.min(MAX_SUBJECTS, n));
    setSubjects((prev) => {
      if (bounded === prev.length) return prev;
      if (bounded < prev.length) return prev.slice(0, bounded);
      const additions = Array.from({ length: bounded - prev.length }, (_, i) => createSubject(prev.length + i));
      return [...prev, ...additions];
    });
  }, []);

  const setSubjectActive = useCallback((subjectId: string, active: boolean) => {
    setSubjects((prev) => prev.map((s) => (s.subjectId === subjectId
      ? {
        ...s,
        active,
        streamStatus: active
          ? liveModeRef.current ? "connected" : sessionRef.current.status === "running" ? "simulated" : "disconnected"
          : "disconnected",
      }
      : s)));
  }, []);

  const setSubjectVisible = useCallback((subjectId: string, visible: boolean) => {
    setSubjects((prev) => prev.map((s) => (s.subjectId === subjectId ? { ...s, visible } : s)));
  }, []);

  const showAll = useCallback(() => setSubjects((prev) => prev.map((s) => ({ ...s, visible: true }))), []);
  const hideAll = useCallback(() => setSubjects((prev) => prev.map((s) => ({ ...s, visible: false }))), []);
  const focusOn = useCallback((subjectId: string) => {
    setSubjects((prev) => prev.map((s) => ({ ...s, visible: s.subjectId === subjectId })));
  }, []);

  const startSession = useCallback(() => {
    setSession((prev) => ({ ...prev, status: "running" }));
    setSubjects((prev) => prev.map((s) => (s.active ? { ...s, streamStatus: liveModeRef.current ? "connected" : "simulated" } : s)));
  }, []);

  const pauseSession = useCallback(() => {
    setSession((prev) => ({ ...prev, status: "paused" }));
    setSubjects((prev) => prev.map((s) => (s.active ? { ...s, streamStatus: "paused" } : s)));
  }, []);

  const stopSession = useCallback(() => {
    setSession((prev) => ({ ...prev, status: "stopped" }));
    setSubjects((prev) => prev.map((s) => (s.active ? { ...s, streamStatus: "disconnected" } : s)));
  }, []);

  const resetSession = useCallback(() => {
    simMapRef.current.clear();
    activeMarkerIdRef.current.clear();
    elapsedSecRef.current = 0;
    currentPhaseRef.current = "idle";
    setCurrentPhaseState("idle");
    setMarkerEvents([]);
    setDataBySubject({});
    setSession(newSessionMeta());
    setSubjects((prev) => prev.map((s) => ({
      ...s,
      streamStatus: s.active ? liveModeRef.current ? "connected" : "simulated" : "disconnected",
    })));
  }, []);

  return {
    subjects,
    dataBySubject,
    markerEvents,
    session,
    currentPhase,
    setSubjectCount,
    setSubjectActive,
    setSubjectVisible,
    showAll,
    hideAll,
    focusOn,
    startSession,
    pauseSession,
    stopSession,
    resetSession,
    triggerPhase,
    addCustomMarker,
  };
}

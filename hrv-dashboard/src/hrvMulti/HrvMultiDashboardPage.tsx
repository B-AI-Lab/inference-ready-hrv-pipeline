import { useState } from "react";
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import type { HRVDashboardPayload, HRVSample } from "../lib/types";
import type { PhaseLabel, SessionEvent, SessionEventType } from "../eventAnnotatedDataLayer";
import { ParticipantHeader } from "../components/Header";
import { LiveMetricsStrip, StressScoreCard, RecoveryScoreCard, SignalConfidenceCard } from "../components/HeroCards";
import {
  PrimaryTrendChart, AutonomicReactivityChart, EventRMSSDComparisonChart, PhysiologicalTimeline, RawRRIntervalsChart,
} from "../components/Charts";
import { RecoveryEventPanel } from "../components/Events";
import { ExpertMetricsGrid } from "../components/ExpertMetrics";
import { useMultiSubjectHRVStream } from "./useMultiSubjectHRVStream";
import { SubjectControlPanel } from "./components/SubjectControlPanel";
import { MarkerControlPanel } from "./components/MarkerControlPanel";
import { SessionControlPanel } from "./components/SessionControlPanel";
import { MultiSubjectMetricsGrid } from "./components/MultiSubjectMetricsGrid";
import { MultiSubjectTrendChart } from "./components/MultiSubjectTrendChart";
import { ComparativeOverviewPanel } from "./components/ComparativeOverviewPanel";
import type { GlobalMarkerEvent } from "./types";

const BLANK_SAMPLE: HRVSample = {
  timestamp: Date.now() / 1000,
  elapsedSec: 0,
  rrMs: null,
  heartRate: null,
  rmssd: null,
  sdnn: null,
  sdnnDetrended: null,
  pnn50: null,
  baevskySI: null,
  lfPower: null,
  hfPower: null,
  lfHfRatio: null,
  autonomicBalanceIndex: null,
  respirationProxyHz: null,
  respirationProxyConfidence: null,
  psdReadiness: 0,
  artifactRatio: 0,
  signalConfidence: 0,
  stressScore: null,
  recoveryScore: null,
  physiologicalState: "Initializing",
};

function toLegacyEventType(marker: GlobalMarkerEvent): SessionEventType {
  if (marker.eventType === "custom_marker") return "manual_event";
  if (marker.phase === "baseline") return marker.eventType === "phase_start" ? "start_baseline" : "stop_save_baseline";
  if (marker.phase === "task") return marker.eventType === "phase_start" ? "start_intervention_1" : "stop_intervention_1";
  if (marker.phase === "recovery") return marker.eventType === "phase_start" ? "start_recovery" : "stop_recovery";
  return "manual_event";
}

function toLegacyPhase(marker: GlobalMarkerEvent): PhaseLabel {
  if (marker.phase === "baseline") return "baseline";
  if (marker.phase === "task") return "intervention_1";
  if (marker.phase === "recovery") return "recovery";
  return "none";
}

function mapMarkersToLegacyEvents(markers: GlobalMarkerEvent[], subjectId: string): SessionEvent[] {
  return markers
    .filter((m) => m.affectedSubjects.includes(subjectId))
    .map((m) => ({
      event_id: m.eventId,
      event_type: toLegacyEventType(m),
      event_label: m.eventLabel,
      phase: toLegacyPhase(m),
      action: m.eventType === "phase_start" ? "start" : m.eventType === "phase_end" ? "stop" : "manual",
      timestamp_iso: new Date(m.timestamp).toISOString(),
      timestamp_unix_ms: m.timestamp,
      elapsed_session_time_s: m.elapsedSec,
      optional_user_note: m.notes ?? null,
    }));
}

function TechnicalDetailSection({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="glass-panel overflow-hidden rounded-2xl">
      <button
        type="button"
        className="flex w-full items-center justify-between px-5 py-4 text-left transition hover:bg-white/[0.02]"
        onClick={() => setOpen((prev) => !prev)}
      >
        <div>
          <p className="zone-label">Technical Detail</p>
          <h2 className="mt-1 text-base font-semibold text-white">
            Raw signals · Expert metrics · Signal diagnostics
          </h2>
        </div>
        <ChevronDown
          className={`h-5 w-5 flex-shrink-0 text-slate-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="flex flex-col gap-5 border-t border-white/10 p-5">
          {children}
        </div>
      )}
    </section>
  );
}

export function HrvMultiDashboardPage() {
  const stream = useMultiSubjectHRVStream();
  const { subjects, dataBySubject, markerEvents, session, currentPhase } = stream;
  const visibleSubjects = subjects.filter((s) => s.visible);
  const focusSubject = visibleSubjects.length === 1 ? visibleSubjects[0] : null;

  let focusView: ReactNode = null;
  if (focusSubject) {
    const entry = dataBySubject[focusSubject.subjectId];
    const history = entry?.history ?? [];
    const sample = history[history.length - 1] ?? BLANK_SAMPLE;
    const payload: HRVDashboardPayload = {
      sample,
      events: entry?.recoveryEvents ?? [],
      quality: entry?.quality ?? {
        nRawRR: 0, nValidRR: 0, nRejectedRR: 0, artifactRatioRecent: 0,
        signalStatus: "Active", psdWindowFilledSec: 0, psdReadiness: 0,
      },
    };
    const legacyEvents = mapMarkersToLegacyEvents(markerEvents, focusSubject.subjectId);

    focusView = (
      <>
        <ParticipantHeader
          payload={payload}
          participantLabel={`${focusSubject.displayName} (${focusSubject.subjectId})`}
          protocolLabel={`Source: ${focusSubject.source}`}
        />

        <section className="flex flex-col gap-4">
          <LiveMetricsStrip sample={sample} history={history} />
          <div className="grid gap-4 md:grid-cols-3">
            <StressScoreCard sample={sample} history={history} />
            <RecoveryScoreCard sample={sample} history={history} />
            <SignalConfidenceCard sample={sample} />
          </div>
          <PrimaryTrendChart history={history} layerEvents={legacyEvents} />
        </section>

        <div className="grid gap-5 xl:grid-cols-2">
          <PhysiologicalTimeline history={history} events={payload.events} layerEvents={legacyEvents} />
          <div className="grid gap-5">
            <RecoveryEventPanel events={payload.events} />
            <EventRMSSDComparisonChart history={history} layerEvents={legacyEvents} segmentSummaries={[]} />
          </div>
        </div>

        <TechnicalDetailSection>
          <div className="grid gap-5 xl:grid-cols-2">
            <AutonomicReactivityChart history={history} layerEvents={legacyEvents} />
            <RawRRIntervalsChart history={history} layerEvents={legacyEvents} />
          </div>
          <ExpertMetricsGrid sample={sample} history={history} />
        </TechnicalDetailSection>
      </>
    );
  }

  return (
    <main className="fine-grid min-h-screen p-4 text-slate-100 sm:p-6 xl:p-8">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: "easeOut" }}
        className="mx-auto flex max-w-[1800px] flex-col gap-5"
      >
        <SubjectControlPanel
          subjects={subjects}
          setSubjectCount={stream.setSubjectCount}
          setSubjectActive={stream.setSubjectActive}
          setSubjectVisible={stream.setSubjectVisible}
          showAll={stream.showAll}
          hideAll={stream.hideAll}
          focusOn={stream.focusOn}
        />
        <MarkerControlPanel currentPhase={currentPhase} triggerPhase={stream.triggerPhase} addCustomMarker={stream.addCustomMarker} />
        <SessionControlPanel
          session={session}
          subjects={subjects}
          dataBySubject={dataBySubject}
          startSession={stream.startSession}
          pauseSession={stream.pauseSession}
          stopSession={stream.stopSession}
          resetSession={stream.resetSession}
        />

        {focusSubject ? (
          focusView
        ) : (
          <>
            <MultiSubjectMetricsGrid subjects={subjects} dataBySubject={dataBySubject} />
            <MultiSubjectTrendChart subjects={subjects} dataBySubject={dataBySubject} markerEvents={markerEvents} />
            <ComparativeOverviewPanel subjects={subjects} dataBySubject={dataBySubject} />
          </>
        )}

        <footer className="pb-2 text-center text-xs text-slate-500">
          Research prototype. HRV-derived state estimates are experimental and not intended for clinical diagnosis.
          Simulated multi-subject Polar H10 streams for development/testing.
        </footer>
      </motion.div>
    </main>
  );
}

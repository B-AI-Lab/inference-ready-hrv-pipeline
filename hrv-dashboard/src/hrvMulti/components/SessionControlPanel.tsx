import { useState } from "react";
import { Download, Pause, Play, RotateCcw, Square } from "lucide-react";
import type { SessionMeta, Subject } from "../types";
import type { SubjectDataEntry } from "../useMultiSubjectHRVStream";
import { exportAllActiveSubjects, exportSubjectJSON } from "../exportService";

export function SessionControlPanel({
  session, subjects, dataBySubject, startSession, pauseSession, stopSession, resetSession,
}: {
  session: SessionMeta;
  subjects: Subject[];
  dataBySubject: Record<string, SubjectDataEntry>;
  startSession: () => void;
  pauseSession: () => void;
  stopSession: () => void;
  resetSession: () => void;
}) {
  const [exportTarget, setExportTarget] = useState("");
  const activeSubjects = subjects.filter((s) => s.active);

  function handleReset() {
    if (window.confirm("Reset will clear all recorded session data for every subject. This cannot be undone. Continue?")) {
      resetSession();
    }
  }

  function handleExportOne() {
    const subject = subjects.find((s) => s.subjectId === exportTarget);
    if (!subject) return;
    const entry = dataBySubject[subject.subjectId];
    exportSubjectJSON(subject, session, entry?.history ?? [], entry?.events ?? []);
  }

  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="zone-label">Session Control</p>
          <h2 className="mt-1 text-lg font-semibold text-white">
            {session.sessionId} <span className="ml-2 rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-0.5 text-xs font-medium text-slate-300">{session.status}</span>
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={startSession} className="inline-flex items-center gap-1.5 rounded-lg border border-lab-mint/40 bg-lab-mint/10 px-3 py-2 text-sm font-medium text-teal-100 transition hover:bg-lab-mint/20">
            <Play className="h-4 w-4" /> Start
          </button>
          <button type="button" onClick={pauseSession} className="inline-flex items-center gap-1.5 rounded-lg border border-lab-amber/40 bg-lab-amber/10 px-3 py-2 text-sm font-medium text-amber-100 transition hover:bg-lab-amber/20">
            <Pause className="h-4 w-4" /> Pause
          </button>
          <button type="button" onClick={stopSession} className="inline-flex items-center gap-1.5 rounded-lg border border-lab-coral/40 bg-lab-coral/10 px-3 py-2 text-sm font-medium text-rose-100 transition hover:bg-lab-coral/20">
            <Square className="h-4 w-4" /> Stop
          </button>
          <button type="button" onClick={handleReset} className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-lab-coral/40 hover:bg-white/[0.07]">
            <RotateCcw className="h-4 w-4" /> Reset
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/10 pt-4">
        <button
          type="button"
          onClick={() => exportAllActiveSubjects(subjects, session, dataBySubject)}
          disabled={activeSubjects.length === 0}
          className="inline-flex items-center gap-1.5 rounded-lg border border-lab-electric/40 bg-lab-electric/10 px-3 py-2 text-sm font-medium text-violet-100 transition hover:bg-lab-electric/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Download className="h-4 w-4" /> Export session (JSON per subject + combined Excel)
        </button>
        <select
          value={exportTarget}
          onChange={(e) => setExportTarget(e.target.value)}
          className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-200 focus:border-lab-electric/50 focus:outline-none"
        >
          <option value="">Export single subject JSON…</option>
          {subjects.map((s) => (
            <option key={s.subjectId} value={s.subjectId}>{s.displayName} ({s.macAddress})</option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleExportOne}
          disabled={!exportTarget}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-lab-electric/40 hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Download className="h-4 w-4" /> Export
        </button>
      </div>
    </section>
  );
}

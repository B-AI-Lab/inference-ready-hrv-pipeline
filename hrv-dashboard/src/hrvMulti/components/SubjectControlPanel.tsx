import { Eye, EyeOff, Focus, Radio, Users } from "lucide-react";
import type { Subject } from "../types";
import { MAX_SUBJECTS } from "../subjectRegistry";

function streamStatusClass(status: Subject["streamStatus"]): string {
  switch (status) {
    case "connected": return "text-lab-mint border-lab-mint/40 bg-lab-mint/10";
    case "simulated": return "text-lab-electric border-lab-electric/40 bg-lab-electric/10";
    case "paused": return "text-lab-amber border-lab-amber/40 bg-lab-amber/10";
    case "disconnected": return "text-slate-400 border-white/15 bg-white/[0.04]";
  }
}

export function SubjectControlPanel({
  subjects, setSubjectCount, setSubjectActive, setSubjectVisible, showAll, hideAll, focusOn,
}: {
  subjects: Subject[];
  setSubjectCount: (n: number) => void;
  setSubjectActive: (subjectId: string, active: boolean) => void;
  setSubjectVisible: (subjectId: string, visible: boolean) => void;
  showAll: () => void;
  hideAll: () => void;
  focusOn: (subjectId: string) => void;
}) {
  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-lab-electric">
          <Users className="h-4 w-4" />
          Subjects
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Active streams</span>
          <div className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] p-1">
            {Array.from({ length: MAX_SUBJECTS }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setSubjectCount(n)}
                className={`h-7 w-7 rounded-full text-xs font-semibold transition ${
                  subjects.length === n
                    ? "bg-lab-electric text-lab-bg shadow-glow"
                    : "text-slate-400 hover:bg-white/[0.08] hover:text-white"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={showAll}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-lab-mint/40 hover:bg-white/[0.07]"
        >
          <Eye className="h-3.5 w-3.5 text-lab-mint" /> Show all
        </button>
        <button
          type="button"
          onClick={hideAll}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-lab-coral/40 hover:bg-white/[0.07]"
        >
          <EyeOff className="h-3.5 w-3.5 text-lab-coral" /> Hide all
        </button>
      </div>

      <div className="flex flex-col gap-2">
        {subjects.map((subject) => (
          <div
            key={subject.subjectId}
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5"
          >
            <div className="flex items-center gap-2.5">
              <span className="h-2.5 w-2.5 flex-shrink-0 rounded-full" style={{ background: subject.colorToken, boxShadow: `0 0 6px ${subject.colorToken}80` }} />
              <div>
                <p className="text-sm font-semibold text-white">{subject.displayName}</p>
                <p className="text-[10px] text-slate-500">{subject.subjectId} &middot; {subject.macAddress} &middot; {subject.source}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${streamStatusClass(subject.streamStatus)}`}>
                <Radio className="h-3 w-3" /> {subject.streamStatus}
              </span>
              <label className="flex items-center gap-1.5 text-[11px] text-slate-400">
                <input
                  type="checkbox"
                  checked={subject.active}
                  onChange={(e) => setSubjectActive(subject.subjectId, e.target.checked)}
                  className="h-3.5 w-3.5 accent-violet-500"
                />
                Active
              </label>
              <label className="flex items-center gap-1.5 text-[11px] text-slate-400">
                <input
                  type="checkbox"
                  checked={subject.visible}
                  onChange={(e) => setSubjectVisible(subject.subjectId, e.target.checked)}
                  className="h-3.5 w-3.5 accent-teal-400"
                />
                Visible
              </label>
              <button
                type="button"
                onClick={() => focusOn(subject.subjectId)}
                className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-slate-200 transition hover:border-lab-electric/50 hover:bg-white/[0.08]"
              >
                <Focus className="h-3 w-3" /> Focus
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

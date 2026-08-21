import { formatValue } from "../../lib/formatters";
import type { Subject } from "../types";
import type { SubjectDataEntry } from "../useMultiSubjectHRVStream";

function meanOf(values: Array<number | null>): number | null {
  const numeric = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (!numeric.length) return null;
  return numeric.reduce((sum, v) => sum + v, 0) / numeric.length;
}

export function ComparativeOverviewPanel({
  subjects, dataBySubject,
}: {
  subjects: Subject[];
  dataBySubject: Record<string, SubjectDataEntry>;
}) {
  const visible = subjects.filter((s) => s.visible);
  const latestSamples = visible.map((s) => {
    const history = dataBySubject[s.subjectId]?.history ?? [];
    return history[history.length - 1] ?? null;
  });

  const groupAvgHr = meanOf(latestSamples.map((s) => s?.heartRate ?? null));
  const groupAvgRmssd = meanOf(latestSamples.map((s) => s?.rmssd ?? null));
  const groupAvgStress = meanOf(latestSamples.map((s) => s?.stressScore ?? null));

  return (
    <section className="glass-panel rounded-2xl p-5">
      <p className="zone-label mb-1">Cross-Subject Comparison</p>
      <h2 className="text-lg font-semibold text-white">Comparative Overview</h2>
      <p className="mb-4 text-xs text-slate-500">Per-subject values shown side by side — no silent averaging</p>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
              <th className="pb-2">Subject</th>
              <th className="pb-2">HR (bpm)</th>
              <th className="pb-2">RMSSD (ms)</th>
              <th className="pb-2">Stress</th>
              <th className="pb-2">Phase</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((s, i) => {
              const sample = latestSamples[i];
              return (
                <tr key={s.subjectId} className="border-t border-white/[0.06]">
                  <td className="py-2">
                    <span className="inline-flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full" style={{ background: s.colorToken }} />
                      {s.displayName}
                    </span>
                  </td>
                  <td className="py-2 tabular-nums text-slate-200">{formatValue(sample?.heartRate ?? null, 0)}</td>
                  <td className="py-2 tabular-nums text-slate-200">{formatValue(sample?.rmssd ?? null, 1)}</td>
                  <td className="py-2 tabular-nums text-slate-200">{formatValue(sample?.stressScore ?? null, 0)}</td>
                  <td className="py-2 text-slate-400">{sample?.currentPhase ?? "idle"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {visible.length > 1 && (
        <div className="mt-4 rounded-xl border border-lab-electric/20 bg-lab-electric/10 p-3">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-lab-electric">
            Group Average (n={visible.length}) — explicit group-level summary, not a per-subject value
          </p>
          <div className="mt-2 grid grid-cols-3 gap-3 text-sm text-slate-200">
            <span>HR {formatValue(groupAvgHr, 0)} bpm</span>
            <span>RMSSD {formatValue(groupAvgRmssd, 1)} ms</span>
            <span>Stress {formatValue(groupAvgStress, 0)}</span>
          </div>
        </div>
      )}
    </section>
  );
}

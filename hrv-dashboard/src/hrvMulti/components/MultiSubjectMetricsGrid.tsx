import { formatValue } from "../../lib/formatters";
import type { Subject } from "../types";
import type { SubjectDataEntry } from "../useMultiSubjectHRVStream";

function latestSample(entry: SubjectDataEntry | undefined) {
  return entry?.history[entry.history.length - 1] ?? null;
}

export function MultiSubjectMetricsGrid({
  subjects, dataBySubject,
}: {
  subjects: Subject[];
  dataBySubject: Record<string, SubjectDataEntry>;
}) {
  const visible = subjects.filter((s) => s.visible);

  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="zone-label">Per-Subject Metrics</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Visible Subjects</h2>
        </div>
        <span className="rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-xs text-slate-300">{visible.length} visible</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {visible.map((subject) => {
          const sample = latestSample(dataBySubject[subject.subjectId]);
          return (
            <div key={subject.subjectId} className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: subject.colorToken, boxShadow: `0 0 6px ${subject.colorToken}80` }} />
                  <span className="text-sm font-semibold text-white">{subject.displayName}</span>
                </div>
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-400">
                  {sample?.currentPhase ?? "idle"}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <Metric label="HR" value={formatValue(sample?.heartRate ?? null, 0)} unit="bpm" />
                <Metric label="RMSSD" value={formatValue(sample?.rmssd ?? null, 1)} unit="ms" />
                <Metric label="SDNN" value={formatValue(sample?.sdnn ?? null, 1)} unit="ms" />
                <Metric label="Stress" value={formatValue(sample?.stressScore ?? null, 0)} unit="" />
              </div>
            </div>
          );
        })}
        {visible.length === 0 && (
          <div className="col-span-full rounded-2xl border border-dashed border-white/15 bg-white/[0.03] p-6 text-center text-sm text-slate-400">
            No subjects are currently visible. Use the subject panel above to show one or more streams.
          </div>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="rounded-lg bg-black/20 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 font-semibold text-slate-100">{value}{unit && <span className="ml-1 text-[10px] text-slate-500">{unit}</span>}</p>
    </div>
  );
}

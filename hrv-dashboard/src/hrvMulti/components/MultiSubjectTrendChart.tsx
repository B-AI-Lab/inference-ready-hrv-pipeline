import { useMemo, useState } from "react";
import {
  CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { formatTime, formatValue } from "../../lib/formatters";
import type { GlobalMarkerEvent, MarkerPhase, Subject } from "../types";
import type { SubjectDataEntry } from "../useMultiSubjectHRVStream";

type MetricKey = "rmssd" | "heartRate";

const METRIC_OPTIONS: Array<{ key: MetricKey; label: string; unit: string }> = [
  { key: "rmssd", label: "RMSSD", unit: "ms" },
  { key: "heartRate", label: "Heart Rate", unit: "bpm" },
];

const tooltipStyle = {
  background: "rgba(12, 9, 22, 0.96)",
  border: "1px solid rgba(190, 147, 255, 0.22)",
  borderRadius: "14px",
  color: "#f8fafc",
};

function phaseColor(phase: MarkerPhase | null): string {
  if (phase === "baseline") return "#818cf8";
  if (phase === "task") return "#fb7185";
  if (phase === "recovery") return "#5eead4";
  return "#fbbf24";
}

function buildOverlayData(subjects: Subject[], dataBySubject: Record<string, SubjectDataEntry>, metric: MetricKey) {
  const perSubject = subjects.map((s) => {
    const map = new Map<number, number | null>();
    for (const sample of dataBySubject[s.subjectId]?.history ?? []) {
      map.set(sample.elapsedSec, sample[metric] ?? null);
    }
    return { subjectId: s.subjectId, map };
  });
  const xSet = new Set<number>();
  perSubject.forEach(({ map }) => map.forEach((_, x) => xSet.add(x)));
  const xs = Array.from(xSet).sort((a, b) => a - b);
  return xs.map((x) => {
    const row: Record<string, number | null> = { elapsedSec: x };
    for (const { subjectId, map } of perSubject) row[subjectId] = map.get(x) ?? null;
    return row;
  });
}

function MarkerLines({ events }: { events: GlobalMarkerEvent[] }) {
  return (
    <>
      {events.map((event) => (
        <ReferenceLine
          key={event.eventId}
          x={event.elapsedSec}
          stroke={phaseColor(event.phase)}
          strokeDasharray={event.eventType === "phase_end" ? "4 4" : "2 2"}
          strokeOpacity={0.7}
          label={{ value: event.eventLabel, position: "insideTop", fill: phaseColor(event.phase), fontSize: 10, fontWeight: 700 }}
        />
      ))}
    </>
  );
}

export function MultiSubjectTrendChart({
  subjects, dataBySubject, markerEvents,
}: {
  subjects: Subject[];
  dataBySubject: Record<string, SubjectDataEntry>;
  markerEvents: GlobalMarkerEvent[];
}) {
  const [metric, setMetric] = useState<MetricKey>("rmssd");
  const [mode, setMode] = useState<"overlay" | "small-multiples">("overlay");
  const visible = subjects.filter((s) => s.visible);
  const overlayData = useMemo(() => buildOverlayData(visible, dataBySubject, metric), [visible, dataBySubject, metric]);
  const minX = overlayData[0]?.elapsedSec ?? 0;
  const maxX = overlayData[overlayData.length - 1]?.elapsedSec ?? 60;
  const metricInfo = METRIC_OPTIONS.find((m) => m.key === metric) ?? METRIC_OPTIONS[0];

  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="zone-label">Multi-Subject Trend</p>
          <h2 className="mt-1 text-lg font-semibold text-white">{metricInfo.label} across visible subjects</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {METRIC_OPTIONS.map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => setMetric(m.key)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                metric === m.key ? "border-lab-mint/60 bg-lab-mint/15 text-white" : "border-white/10 bg-black/10 text-slate-300 hover:border-lab-electric/50"
              }`}
            >
              {m.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setMode(mode === "overlay" ? "small-multiples" : "overlay")}
            className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-lab-electric/40"
          >
            {mode === "overlay" ? "Switch to small multiples" : "Switch to overlay"}
          </button>
        </div>
      </div>

      {mode === "overlay" ? (
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={overlayData} margin={{ left: -10, right: 16, top: 10, bottom: 0 }}>
              <CartesianGrid stroke="rgba(148, 163, 184, 0.10)" vertical={false} />
              <XAxis dataKey="elapsedSec" type="number" domain={[minX, maxX || 60]} tickFormatter={(v) => formatTime(v, true)} stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip contentStyle={tooltipStyle} labelFormatter={(v) => formatTime(Number(v))} formatter={(v, name) => [formatValue(Number(v), 1), String(name)]} />
              <Legend formatter={(value) => subjects.find((s) => s.subjectId === value)?.displayName ?? value} />
              <MarkerLines events={markerEvents} />
              {visible.map((s) => (
                <Line
                  key={s.subjectId}
                  type="monotone"
                  dataKey={s.subjectId}
                  name={s.subjectId}
                  stroke={s.colorToken}
                  strokeWidth={2.4}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {visible.map((s) => {
            const data = (dataBySubject[s.subjectId]?.history ?? []).map((sample) => ({
              elapsedSec: sample.elapsedSec,
              value: sample[metric],
            }));
            return (
              <div key={s.subjectId} className="rounded-xl border border-white/10 bg-white/[0.025] p-3">
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-white">
                  <span className="h-2 w-2 rounded-full" style={{ background: s.colorToken }} />
                  {s.displayName}
                </div>
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data} margin={{ left: -20, right: 8, top: 4, bottom: 0 }}>
                      <XAxis dataKey="elapsedSec" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => formatTime(v, true)} stroke="#94a3b8" fontSize={9} />
                      <YAxis stroke="#94a3b8" fontSize={9} width={32} />
                      <Tooltip contentStyle={tooltipStyle} formatter={(v) => [formatValue(Number(v), 1), metricInfo.label]} />
                      <Line type="monotone" dataKey="value" stroke={s.colorToken} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

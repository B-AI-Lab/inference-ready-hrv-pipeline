import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ReactNode } from "react";
import type { ChartSample, HRVSample, RecoveryEvent } from "../lib/types";
import { formatTime, formatValue } from "../lib/formatters";
import type { PhaseLabel, SegmentSummary, SessionEvent } from "../eventAnnotatedDataLayer";

function chartData(history: HRVSample[]): ChartSample[] {
  return history.map((sample) => ({
    ...sample,
    timeLabel: formatTime(sample.elapsedSec, true),
    heartRateNorm: sample.heartRate === null ? null : Math.min(100, Math.max(0, (sample.heartRate - 45) * 1.35)),
    rmssdNorm: sample.rmssd === null ? null : Math.min(100, Math.max(0, sample.rmssd * 1.35)),
    psdReadinessPct: sample.psdReadiness * 100,
  }));
}

const tooltipStyle = {
  background: "rgba(12, 9, 22, 0.96)",
  border: "1px solid rgba(190, 147, 255, 0.22)",
  borderRadius: "14px",
  color: "#f8fafc",
};

function tooltipNumber(value: unknown, name: unknown): [string, string] {
  const numberValue = typeof value === "number" ? value : Number(value);
  return [formatValue(numberValue, 1), String(name ?? "")];
}

function eventColor(phase: PhaseLabel): string {
  if (phase === "baseline") return "#818cf8";
  if (phase === "recovery") return "#5eead4";
  if (phase.startsWith("intervention")) return "#fb7185";
  return "#fbbf24";
}

function markerColor(event: SessionEvent): string {
  if (event.event_type === "biological_sample_blood") return "#f87171";
  if (event.event_type === "biological_sample_saliva") return "#c084fc";
  if (event.event_type === "biological_sample_sweat") return "#fbbf24";
  return eventColor(event.phase);
}

function shortEventLabel(event: SessionEvent): string {
  if (event.event_type === "biological_sample_blood") return `Blood ${event.sample_number ?? ""}`.trim();
  if (event.event_type === "biological_sample_saliva") return `Saliva ${event.sample_number ?? ""}`.trim();
  if (event.event_type === "biological_sample_sweat") return `Sweat ${event.sample_number ?? ""}`.trim();
  if (event.action === "manual") return "M.";
  if (event.phase === "baseline") return event.action === "stop" ? "B._E" : "B.";
  if (event.phase === "recovery") return event.action === "stop" ? "R._E" : "R.";
  if (event.phase.startsWith("intervention_")) {
    const index = event.phase.replace("intervention_", "");
    return event.action === "stop" ? `I.${index}_E` : `I.${index}`;
  }
  return event.action === "stop" ? "E._E" : "E.";
}

function LayerEventMarkers({ events }: { events: SessionEvent[] }) {
  return (
    <>
      {events.map((event) => {
        const isSample = event.event_category === "biological_sample";
        return (
          <ReferenceLine
            key={event.event_id}
            x={event.elapsed_session_time_s}
            stroke={markerColor(event)}
            strokeDasharray={isSample ? "3 3" : event.action === "stop" ? "4 4" : "2 2"}
            strokeOpacity={isSample ? 0.9 : 0.75}
            label={{
              value: shortEventLabel(event),
              position: "insideTop",
              fill: markerColor(event),
              fontSize: 11,
              fontWeight: 800,
            }}
          />
        );
      })}
    </>
  );
}

function completedPhaseAreas(events: SessionEvent[]) {
  const starts = new Map<PhaseLabel, SessionEvent>();
  const areas: Array<{ key: string; phase: PhaseLabel; x1: number; x2: number; label: string }> = [];
  for (const event of events) {
    if (event.action === "start") starts.set(event.phase, event);
    if (event.action === "stop") {
      const start = starts.get(event.phase);
      if (start) {
        areas.push({
          key: `${start.event_id}_${event.event_id}`,
          phase: event.phase,
          x1: start.elapsed_session_time_s,
          x2: event.elapsed_session_time_s,
          label: start.event_label.replace("Start ", ""),
        });
        starts.delete(event.phase);
      }
    }
  }
  return areas;
}

export function PhysiologicalTimeline({ history, events, layerEvents }: { history: HRVSample[]; events: RecoveryEvent[]; layerEvents: SessionEvent[] }) {
  const data = chartData(history);
  const minX = data[0]?.elapsedSec ?? 0;
  const maxX = data[data.length - 1]?.elapsedSec ?? 0;
  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Physiological State Timeline</h2>
          <p className="text-sm text-slate-400">Processed backend state stream, full dashboard session</p>
        </div>
      </div>
      <div className="h-[430px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ left: -18, right: 18, top: 12, bottom: 4 }}>
            <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" vertical={false} />
            <XAxis dataKey="elapsedSec" type="number" domain={[minX, maxX || 60]} tickFormatter={(v) => formatTime(v, true)} stroke="#94a3b8" fontSize={12} />
            <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={12} />
            <Tooltip contentStyle={tooltipStyle} labelFormatter={(v) => formatTime(Number(v))} formatter={tooltipNumber} />
            <Legend />
            {events.map((event) => (
              <ReferenceArea
                key={event.id}
                x1={event.startSec}
                x2={event.endSec ?? maxX}
                fill="rgba(217, 70, 239, 0.14)"
                strokeOpacity={0}
              />
            ))}
            <LayerEventMarkers events={layerEvents} />
            <Line type="monotone" dataKey="stressScore" name="Autonomic Load Index" strokeWidth={3} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="recoveryScore" name="Recovery Score" stroke="#5eead4" strokeWidth={3} dot={false} isAnimationActive={false} />
            {events.map((event) => event.peakSec && (
              <ReferenceDot key={`peak-${event.id}`} x={event.peakSec} y={event.peakStressScore} r={5} fill="#fb7185" stroke="#fff" />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function AutonomicReactivityChart({ history, layerEvents }: { history: HRVSample[]; layerEvents: SessionEvent[] }) {
  const data = chartData(history);
  return (
    <ChartCard title="Autonomic Reactivity" subtitle="Live rolling-window metrics, normalized display">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ left: -18, right: 10, top: 10, bottom: 0 }}>
          <CartesianGrid stroke="rgba(148, 163, 184, 0.10)" vertical={false} />
          <XAxis dataKey="elapsedSec" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => formatTime(v, true)} stroke="#94a3b8" fontSize={11} />
          <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend />
          <LayerEventMarkers events={layerEvents} />
          <Line type="monotone" dataKey="heartRateNorm" name="Heart Rate normalized" stroke="#c084fc" strokeWidth={2.5} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="rmssdNorm" name="RMSSD normalized" stroke="#5eead4" strokeWidth={2.5} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function EventRMSSDComparisonChart({
  history,
  layerEvents,
  segmentSummaries,
}: {
  history: HRVSample[];
  layerEvents: SessionEvent[];
  segmentSummaries: SegmentSummary[];
}) {
  const data = chartData(history);
  return (
    <section className="glass-panel rounded-2xl p-5">
      <h2 className="text-lg font-semibold text-white">Event RMSSD Comparison</h2>
      <p className="mb-4 text-sm text-slate-400">Rolling RMSSD with baseline, intervention, and recovery markers</p>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ left: -18, right: 10, top: 10, bottom: 0 }}>
            <CartesianGrid stroke="rgba(148, 163, 184, 0.10)" vertical={false} />
            <XAxis dataKey="elapsedSec" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => formatTime(v, true)} stroke="#94a3b8" fontSize={11} />
            <YAxis stroke="#94a3b8" fontSize={11} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${formatValue(Number(v), 1)} ms`, "RMSSD rolling window"]} />
            <Legend />
            {completedPhaseAreas(layerEvents).map((area) => (
              <ReferenceArea
                key={area.key}
                x1={area.x1}
                x2={area.x2}
                fill={eventColor(area.phase)}
                fillOpacity={0.1}
                stroke={eventColor(area.phase)}
                strokeOpacity={0.25}
              />
            ))}
            <LayerEventMarkers events={layerEvents} />
            <Line type="monotone" dataKey="rmssd" name="RMSSD rolling window" stroke="#5eead4" strokeWidth={2.7} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {segmentSummaries.slice(0, 4).map((segment) => (
          <div key={segment.segment_id} className="rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
            <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
              <span>{segment.phase_label.replace("_", " ")}</span>
              <span>{formatValue(segment.mean_rmssd, 1)} ms</span>
            </div>
            <div className="mt-1 text-sm font-semibold text-white">RMSSD {signedPercent(segment.rmssd_delta_percent_vs_baseline)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function RawRRIntervalsChart({ history, layerEvents }: { history: HRVSample[]; layerEvents: SessionEvent[] }) {
  const data = history
    .filter((sample) => typeof sample.rrMs === "number" && Number.isFinite(sample.rrMs))
    .map((sample) => ({
      elapsedSec: sample.elapsedSec,
      timeLabel: formatTime(sample.elapsedSec, true),
      rrMs: sample.rrMs,
    }));
  const minX = data[0]?.elapsedSec ?? 0;
  const maxX = data[data.length - 1]?.elapsedSec ?? 60;
  const rrValues = data.map((item) => Number(item.rrMs)).filter((value) => Number.isFinite(value));
  const minY = rrValues.length ? Math.max(250, Math.floor(Math.min(...rrValues) - 80)) : 400;
  const maxY = rrValues.length ? Math.min(2200, Math.ceil(Math.max(...rrValues) + 80)) : 1200;

  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Raw RR Intervals - Live</h2>
          <p className="text-sm text-slate-400">Unsmoothed RR stream, milliseconds</p>
        </div>
      </div>
      <div className="h-[420px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ left: -8, right: 16, top: 10, bottom: 0 }}>
            <XAxis
              dataKey="elapsedSec"
              type="number"
              domain={[minX, maxX || 60]}
              tickFormatter={(v) => formatTime(v, true)}
              stroke="#94a3b8"
              fontSize={12}
            />
            <YAxis domain={[minY, maxY]} stroke="#94a3b8" fontSize={12} width={58} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(v) => formatTime(Number(v))}
              formatter={(v) => [`${formatValue(Number(v), 0)} ms`, "RR interval"]}
            />
            <LayerEventMarkers events={layerEvents} />
            <Line
              type="linear"
              dataKey="rrMs"
              name="RR interval"
              stroke="#d8b4fe"
              strokeWidth={2.25}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function PrimaryTrendChart({ history, layerEvents }: { history: HRVSample[]; layerEvents: SessionEvent[] }) {
  const data = history.map((s) => ({
    elapsedSec: s.elapsedSec,
    timeLabel: formatTime(s.elapsedSec, true),
    rmssd: s.rmssd,
    heartRate: s.heartRate,
  }));
  const minX = data[0]?.elapsedSec ?? 0;
  const maxX = data[data.length - 1]?.elapsedSec ?? 60;

  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="zone-label">Primary Trend</p>
          <h2 className="mt-1 text-lg font-semibold text-white">RMSSD & Heart Rate</h2>
          <p className="text-sm text-slate-400">Live rolling window — real units</p>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-1.5 w-4 rounded-full bg-lab-mint" />
            RMSSD (ms)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-1.5 w-4 rounded-full bg-lab-electric" />
            Heart Rate (bpm)
          </span>
        </div>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ left: 0, right: 42, top: 10, bottom: 4 }}>
            <CartesianGrid stroke="rgba(148, 163, 184, 0.10)" vertical={false} />
            <XAxis
              dataKey="elapsedSec"
              type="number"
              domain={[minX, maxX || 60]}
              tickFormatter={(v) => formatTime(v, true)}
              stroke="#94a3b8"
              fontSize={11}
            />
            <YAxis
              yAxisId="rmssd"
              domain={[0, "auto"]}
              stroke="#5eead4"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={46}
            />
            <YAxis
              yAxisId="hr"
              orientation="right"
              domain={["auto", "auto"]}
              stroke="#c084fc"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(v) => formatTime(Number(v))}
              formatter={tooltipNumber}
            />
            <LayerEventMarkers events={layerEvents} />
            <Line
              yAxisId="rmssd"
              type="monotone"
              dataKey="rmssd"
              name="RMSSD (ms)"
              stroke="#5eead4"
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
            <Line
              yAxisId="hr"
              type="monotone"
              dataKey="heartRate"
              name="Heart Rate (bpm)"
              stroke="#c084fc"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function signedPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(0)}%`;
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <section className="glass-panel rounded-2xl p-5">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <p className="mb-4 text-sm text-slate-400">{subtitle}</p>
      <div className="h-72">{children}</div>
    </section>
  );
}




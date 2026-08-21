import React, { useMemo, useState } from "react";
import { AlertTriangle, BookmarkPlus, Download, Droplets, FileJson, Flag, FlaskConical, Syringe, TimerReset } from "lucide-react";
import type { useEventAnnotatedDataLayer } from "../eventAnnotatedDataLayer";
import type { AnnotatedHRVWindow, BaselineSummary, InterpretabilityLabel, PhaseLabel, SegmentSummary, SessionEvent, SessionEventType } from "../eventAnnotatedDataLayer";
import { formatTime, formatValue } from "../lib/formatters";
import { downloadTextFile } from "../lib/fileDownload";

type LayerState = ReturnType<typeof useEventAnnotatedDataLayer>;

type CompletedBlockKind = "baseline" | "segment" | "manual";

interface CompletedBlock {
  id: string;
  kind: CompletedBlockKind;
  label: string;
  startIso: string;
  endIso: string;
  startElapsed: number | null;
  endElapsed: number | null;
  durationS: number;
  windows: number;
  interpretability: InterpretabilityLabel | "n/a";
  segmentSummary: SegmentSummary | null;
  baselineSummary: BaselineSummary | null;
  manualEvent: SessionEvent | null;
}

interface MetricDef {
  id: string;
  label: string;
  unit: string;
  decimals: number;
  summaryValue: (summary: SegmentSummary) => number | null;
  baselineValue: (summary: BaselineSummary) => number | null;
  windowValue: (window: AnnotatedHRVWindow) => number | null;
}

const METRICS: MetricDef[] = [
  {
    id: "rmssd",
    label: "RMSSD",
    unit: "ms",
    decimals: 1,
    summaryValue: (summary) => summary.mean_rmssd,
    baselineValue: (summary) => summary.baseline_rmssd_mean,
    windowValue: (window) => window.rmssd_ms,
  },
  {
    id: "sdnn",
    label: "SDNN",
    unit: "ms",
    decimals: 1,
    summaryValue: (summary) => summary.mean_sdnn,
    baselineValue: (summary) => summary.baseline_sdnn_mean,
    windowValue: (window) => window.sdnn_ms,
  },
  {
    id: "pnn50",
    label: "pNN50",
    unit: "%",
    decimals: 1,
    summaryValue: (summary) => summary.mean_pnn50,
    baselineValue: (summary) => summary.baseline_pnn50_mean,
    windowValue: (window) => window.pnn50_percent,
  },
  {
    id: "lf_hf",
    label: "LF/HF fraction",
    unit: "",
    decimals: 2,
    summaryValue: (summary) => summary.mean_lf_hf_ratio,
    baselineValue: () => null,
    windowValue: (window) => window.source_sample.lfHfRatio,
  },
  {
    id: "autonomic_balance",
    label: "Autonomic Balance",
    unit: "",
    decimals: 0,
    summaryValue: (summary) => summary.mean_autonomic_balance_index,
    baselineValue: () => null,
    windowValue: (window) => window.source_sample.autonomicBalanceIndex,
  },
  {
    id: "autonomic_load_index",
    label: "Autonomic Load Index",
    unit: "",
    decimals: 0,
    summaryValue: () => null,
    baselineValue: () => null,
    windowValue: (window) => window.source_sample.stressScore,
  },
  {
    id: "resp_rate",
    label: "Respiratory Rate",
    unit: "br/min",
    decimals: 1,
    summaryValue: (summary) => summary.mean_respiration_proxy_hz === null ? null : summary.mean_respiration_proxy_hz * 60,
    baselineValue: () => null,
    windowValue: (window) => typeof window.source_sample.respirationProxyHz === "number" ? window.source_sample.respirationProxyHz * 60 : null,
  },
  {
    id: "mean_hr",
    label: "Mean HR",
    unit: "bpm",
    decimals: 1,
    summaryValue: (summary) => summary.mean_hr,
    baselineValue: (summary) => summary.baseline_hr_mean,
    windowValue: (window) => window.mean_hr_bpm,
  },
  {
    id: "signal",
    label: "Signal Reliability",
    unit: "%",
    decimals: 0,
    summaryValue: (summary) => summary.mean_signal_reliability === null ? null : summary.mean_signal_reliability * 100,
    baselineValue: (summary) => summary.baseline_signal_reliability_mean === null ? null : summary.baseline_signal_reliability_mean * 100,
    windowValue: (window) => window.signal_reliability_score === null ? null : window.signal_reliability_score * 100,
  },
];

interface ControlDef {
  start: SessionEventType;
  stop: SessionEventType;
  phase: Exclude<PhaseLabel, "none">;
  label: string;
}

const CONTROLS: ControlDef[] = [
  { start: "start_baseline", stop: "stop_save_baseline", phase: "baseline", label: "Baseline" },
  { start: "start_intervention_1", stop: "stop_intervention_1", phase: "intervention_1", label: "Intervention 1" },
  { start: "start_intervention_2", stop: "stop_intervention_2", phase: "intervention_2", label: "Intervention 2" },
  { start: "start_intervention_3", stop: "stop_intervention_3", phase: "intervention_3", label: "Intervention 3" },
  { start: "start_recovery", stop: "stop_recovery", phase: "recovery", label: "Recovery" },
];

const SAMPLE_TYPES: Array<{
  key: "blood" | "saliva" | "sweat";
  label: string;
  Icon: React.ComponentType<{ className?: string }>;
  colorClass: string;
  activeClass: string;
}> = [
  {
    key: "blood",
    label: "Blood Sample",
    Icon: Syringe,
    colorClass: "border-lab-coral/40 bg-lab-coral/10 text-rose-100 hover:border-lab-coral/70 hover:bg-lab-coral/20",
    activeClass: "border-lab-coral bg-lab-coral/25 shadow-coral",
  },
  {
    key: "saliva",
    label: "Saliva Sample",
    Icon: Droplets,
    colorClass: "border-lab-electric/40 bg-lab-electric/10 text-violet-100 hover:border-lab-electric/70 hover:bg-lab-electric/20",
    activeClass: "border-lab-electric bg-lab-electric/25 shadow-glow",
  },
  {
    key: "sweat",
    label: "Sweat Sample",
    Icon: FlaskConical,
    colorClass: "border-lab-amber/40 bg-lab-amber/10 text-amber-100 hover:border-lab-amber/70 hover:bg-lab-amber/20",
    activeClass: "border-lab-amber bg-lab-amber/25",
  },
];

function SampleAnnotationPanel({ layer }: { layer: LayerState }) {
  const [lastAnnotated, setLastAnnotated] = useState<string | null>(null);

  function handleAnnotate(key: "blood" | "saliva" | "sweat") {
    layer.logBiologicalSample(key);
    setLastAnnotated(key);
    setTimeout(() => setLastAnnotated(null), 1800);
  }

  function nextSampleNumber(sampleEventType: string): number {
    return layer.events.filter((e) => e.event_type === sampleEventType).length + 1;
  }

  return (
    <div className="mt-4 border-t border-white/10 pt-4">
      <p className="zone-label mb-3">Sample Collection</p>
      <div className="grid grid-cols-3 gap-2">
        {SAMPLE_TYPES.map(({ key, label, Icon, colorClass, activeClass }) => {
          const isActive = lastAnnotated === key;
          const nextNum = nextSampleNumber(`biological_sample_${key}`);
          return (
            <button
              key={key}
              type="button"
              className={`flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-center text-xs font-semibold transition ${
                isActive ? activeClass : colorClass
              }`}
              onClick={() => handleAnnotate(key)}
            >
              <Icon className="h-4 w-4" />
              <span className="leading-tight">{label}</span>
              <span className="text-[10px] font-normal opacity-60">#{nextNum}</span>
              {isActive && <span className="text-[10px] font-normal opacity-70">Logged</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function phaseLabel(phase: PhaseLabel): string {
  const labels: Record<PhaseLabel, string> = {
    none: "No active phase",
    baseline: "Baseline running",
    intervention_1: "Intervention 1 running",
    intervention_2: "Intervention 2 running",
    intervention_3: "Intervention 3 running",
    recovery: "Recovery running",
  };
  return labels[phase];
}

export function EventControlPanel({ layer }: { layer: LayerState }) {
  const activePhase = layer.activePhase;
  const activeDuration = layer.activeEvent
    ? Math.max(0, layer.currentElapsedSessionTimeS - layer.activeEvent.elapsed_session_time_s)
    : 0;

  return (
    <section className="glass-panel rounded-2xl p-5 shadow-glow">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-lab-electric">
            <Flag className="h-4 w-4" />
            Event-Annotated HRV Data Layer
          </div>
          <h2 className="mt-2 text-xl font-semibold text-white">Event Control</h2>
        </div>
        <div className="rounded-full border border-lab-electric/30 bg-lab-electric/10 px-4 py-2 text-sm text-violet-100">
          Active phase: <span className="font-semibold text-white">{phaseLabel(activePhase)}</span>
          {layer.activeEvent && <span className="ml-2 text-lab-mint">{formatTime(activeDuration, true)}</span>}
        </div>
      </div>

      <div className="mt-5 grid gap-3 grid-cols-2">
        {CONTROLS.map((control) => {
          const isActive = activePhase === control.phase;
          const canStart = activePhase === "none";
          return (
            <div key={control.phase} className={`rounded-xl border p-3 transition ${isActive ? "border-lab-mint/50 bg-lab-mint/10 shadow-mint" : "border-white/10 bg-white/[0.035]"}`}>
              <div className="mb-3 flex items-center justify-between gap-2">
                <div>
                  <span className="text-sm font-semibold text-white">{control.label}</span>
                  <p className={`mt-1 text-xs ${isActive ? "text-lab-mint" : "text-slate-500"}`}>
                    {isActive ? `Running ${formatTime(activeDuration, true)}` : "Idle"}
                  </p>
                </div>
                <span className={`h-2.5 w-2.5 rounded-full ${isActive ? "bg-lab-mint shadow-mint" : "bg-slate-600"}`} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  className="rounded-lg border border-lab-electric/30 bg-lab-electric/10 px-3 py-2 text-sm font-medium text-violet-100 transition hover:border-lab-electric/70 hover:bg-lab-electric/20 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!canStart}
                  onClick={() => layer.logEvent(control.start)}
                >
                  Start
                </button>
                <button
                  className="rounded-lg border border-lab-coral/35 bg-lab-coral/10 px-3 py-2 text-sm font-medium text-rose-100 transition hover:border-lab-coral/70 hover:bg-lab-coral/20 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!isActive}
                  onClick={() => layer.logEvent(control.stop)}
                >
                  Stop
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-lab-electric/40 hover:bg-white/[0.07]"
          onClick={() => layer.logEvent("manual_event")}
        >
          <BookmarkPlus className="h-4 w-4 text-lab-electric" />
          Manual Event
        </button>
        {layer.warning && (
          <div className="inline-flex items-center gap-2 rounded-full border border-lab-amber/30 bg-lab-amber/10 px-4 py-2 text-sm text-amber-100">
            <AlertTriangle className="h-4 w-4" />
            {layer.warning}
          </div>
        )}
      </div>

      <SampleAnnotationPanel layer={layer} />
    </section>
  );
}

export function EventAnnotatedReadoutsPanel({ layer }: { layer: LayerState }) {
  const completedBlocks = useMemo(() => buildCompletedBlocks(layer), [layer]);
  const [segmentAId, setSegmentAId] = useState<string | null>(null);
  const [segmentBId, setSegmentBId] = useState<string | null>(null);
  const [metricId, setMetricId] = useState("rmssd");
  const metric = METRICS.find((item) => item.id === metricId) ?? METRICS[0];
  const segmentA = completedBlocks.find((block) => block.id === segmentAId) ?? null;
  const segmentB = completedBlocks.find((block) => block.id === segmentBId) ?? null;
  const comparison = segmentA && segmentB ? compareBlocks(segmentA, segmentB, metric, layer.annotatedWindows) : null;

  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-lab-mint">
            <TimerReset className="h-4 w-4" />
            Event-Annotated Readouts
          </div>
          <h2 className="mt-2 text-xl font-semibold text-white">Second Layer Readouts</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Readouts update after completed phases only. Active phases are annotated internally without summary output.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-100 transition hover:border-lab-mint/40 hover:bg-white/[0.07] disabled:opacity-40"
            disabled={!layer.exportReady}
            onClick={() => downloadTextFile("event_annotated_hrv_session.json", layer.exportFullSessionJSON(), "application/json")}
          >
            <FileJson className="h-4 w-4 text-lab-mint" />
            JSON
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-100 transition hover:border-lab-mint/40 hover:bg-white/[0.07] disabled:opacity-40"
            disabled={!layer.exportReady}
            onClick={() => downloadTextFile("event_annotated_hrv_windows.csv", layer.exportAnnotatedWindowsCSV(), "text/csv")}
          >
            <Download className="h-4 w-4 text-lab-mint" />
            CSV
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(360px,0.92fr)_minmax(0,1.08fr)]">
        <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Completed event blocks</p>
              <h3 className="mt-1 text-xl font-semibold text-white">Select two segments</h3>
            </div>
            <span className="rounded-full border border-lab-mint/30 bg-lab-mint/10 px-3 py-1 text-xs font-semibold text-lab-mint">
              {completedBlocks.length} complete
            </span>
          </div>
          <div className="grid max-h-[520px] gap-3 overflow-y-auto pr-1">
            {completedBlocks.length === 0 && (
              <p className="rounded-xl border border-white/10 bg-black/10 p-4 text-sm text-slate-400">
                No completed event blocks yet. Stop a baseline, intervention, or recovery phase to make it selectable.
              </p>
            )}
            {completedBlocks.map((block) => {
              const isA = block.id === segmentAId;
              const isB = block.id === segmentBId;
              return (
                <button
                  key={block.id}
                  className={`rounded-xl border p-4 text-left transition hover:border-lab-electric/50 hover:bg-white/[0.06] ${
                    isA || isB ? "border-lab-mint/60 bg-lab-mint/10 shadow-mint" : "border-white/10 bg-black/10"
                  }`}
                  onClick={() => {
                    if (!segmentAId || block.id === segmentAId) {
                      setSegmentAId(block.id);
                      return;
                    }
                    setSegmentBId(block.id);
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-base font-semibold text-white">{block.label}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {formatClock(block.startIso)} - {formatClock(block.endIso)}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      {isA && <span className="rounded-full bg-lab-mint px-2 py-0.5 text-xs font-bold text-lab-bg">A</span>}
                      {isB && <span className="rounded-full bg-lab-electric px-2 py-0.5 text-xs font-bold text-lab-bg">B</span>}
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <MiniMeta label="Duration" value={formatTime(block.durationS, true)} />
                    <MiniMeta label="Windows" value={String(block.windows)} />
                    <MiniMeta label="Signal" value={block.interpretability} />
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <span
                      role="button"
                      tabIndex={0}
                      className={`rounded-lg border px-3 py-2 text-center text-xs font-bold transition ${
                        isA
                          ? "border-lab-mint/70 bg-lab-mint/20 text-white"
                          : "border-white/10 bg-white/[0.035] text-slate-300 hover:border-lab-mint/50 hover:text-white"
                      }`}
                      onClick={(event) => {
                        event.stopPropagation();
                        setSegmentAId(block.id);
                        if (segmentBId === block.id) setSegmentBId(null);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          event.stopPropagation();
                          setSegmentAId(block.id);
                          if (segmentBId === block.id) setSegmentBId(null);
                        }
                      }}
                    >
                      Set as A
                    </span>
                    <span
                      role="button"
                      tabIndex={0}
                      className={`rounded-lg border px-3 py-2 text-center text-xs font-bold transition ${
                        isB
                          ? "border-lab-electric/70 bg-lab-electric/20 text-white"
                          : "border-white/10 bg-white/[0.035] text-slate-300 hover:border-lab-electric/50 hover:text-white"
                      }`}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (segmentAId === block.id) setSegmentAId(null);
                        setSegmentBId(block.id);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          event.stopPropagation();
                          if (segmentAId === block.id) setSegmentAId(null);
                          setSegmentBId(block.id);
                        }
                      }}
                    >
                      Set as B
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Event comparison selector</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <SelectedBlockSlot label="Segment A" block={segmentA} onClear={() => setSegmentAId(null)} />
            <SelectedBlockSlot label="Segment B" block={segmentB} onClear={() => setSegmentBId(null)} />
          </div>

          <div className="mt-5">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Metric</p>
            <div className="flex flex-wrap gap-2">
              {METRICS.map((item) => (
                <button
                  key={item.id}
                  className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
                    item.id === metric.id
                      ? "border-lab-mint/60 bg-lab-mint/15 text-white shadow-mint"
                      : "border-white/10 bg-black/10 text-slate-300 hover:border-lab-electric/50 hover:bg-white/[0.06]"
                  }`}
                  onClick={() => setMetricId(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-lab-electric/20 bg-lab-electric/10 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-lab-electric">Comparison readout</p>
            <h3 className="mt-2 text-xl font-semibold text-white">
              {segmentA && segmentB ? `${segmentA.label} vs ${segmentB.label}` : "Choose two completed blocks"}
            </h3>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              {comparison?.message ?? "Select two completed event blocks and one physiological metric to generate a numerical comparison."}
            </p>
            {comparison && (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <ReadoutStat label={comparison.segmentALabel} value={comparison.valueA} />
                <ReadoutStat label={comparison.segmentBLabel} value={comparison.valueB} />
                <ReadoutStat label="Difference" value={comparison.diff} />
                <ReadoutStat label="Interpretability" value={comparison.interpretability} />
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function ReadoutStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-3">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function MiniMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] px-2 py-2">
      <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-xs font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function SelectedBlockSlot({ label, block, onClear }: { label: string; block: CompletedBlock | null; onClear: () => void }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</p>
        {block && (
          <button className="text-xs font-semibold text-lab-coral transition hover:text-rose-200" onClick={onClear}>
            Clear
          </button>
        )}
      </div>
      <p className="mt-3 text-lg font-semibold text-white">{block?.label ?? "Not selected"}</p>
      <p className="mt-1 text-xs text-slate-500">{block ? `${formatClock(block.startIso)} - ${formatClock(block.endIso)}` : "Click a completed block"}</p>
    </div>
  );
}

function buildCompletedBlocks(layer: LayerState): CompletedBlock[] {
  const blocks: CompletedBlock[] = [];
  if (layer.baselineSummary) {
    const stopEvent = [...layer.events].reverse().find((event) => event.event_type === "stop_save_baseline");
    const startEvent = stopEvent
      ? [...layer.events].reverse().find((event) => event.event_type === "start_baseline" && event.timestamp_unix_ms <= stopEvent.timestamp_unix_ms)
      : null;
    blocks.push({
      id: "baseline",
      kind: "baseline",
      label: "Baseline",
      startIso: layer.baselineSummary.baseline_start_time,
      endIso: layer.baselineSummary.baseline_end_time,
      startElapsed: startEvent?.elapsed_session_time_s ?? null,
      endElapsed: stopEvent?.elapsed_session_time_s ?? null,
      durationS: layer.baselineSummary.baseline_duration_s,
      windows: layer.baselineSummary.number_of_windows_used,
      interpretability: layer.baselineSummary.baseline_stability_label,
      segmentSummary: null,
      baselineSummary: layer.baselineSummary,
      manualEvent: null,
    });
  }

  for (const summary of [...layer.segmentSummaries].reverse()) {
    blocks.push({
      id: summary.segment_id,
      kind: "segment",
      label: phaseDisplayName(summary.phase_label),
      startIso: summary.segment_start_time,
      endIso: summary.segment_end_time,
      startElapsed: null,
      endElapsed: null,
      durationS: summary.duration_s,
      windows: summary.number_of_windows_used,
      interpretability: summary.interpretability_label,
      segmentSummary: summary,
      baselineSummary: null,
      manualEvent: null,
    });
  }

  const manualEventTypes: SessionEventType[] = [
    "manual_event",
    "biological_sample_blood",
    "biological_sample_saliva",
    "biological_sample_sweat",
  ];
  for (const event of layer.events.filter((item) => manualEventTypes.includes(item.event_type))) {
    blocks.push({
      id: event.event_id,
      kind: "manual",
      label: event.event_label,
      startIso: event.timestamp_iso,
      endIso: event.timestamp_iso,
      startElapsed: event.elapsed_session_time_s,
      endElapsed: event.elapsed_session_time_s,
      durationS: 0,
      windows: 0,
      interpretability: "n/a",
      segmentSummary: null,
      baselineSummary: null,
      manualEvent: event,
    });
  }

  return blocks.sort((left, right) => Date.parse(left.startIso) - Date.parse(right.startIso));
}

function compareBlocks(blockA: CompletedBlock, blockB: CompletedBlock, metric: MetricDef, windows: AnnotatedHRVWindow[]) {
  const rawA = metricValueForBlock(blockA, metric, windows);
  const rawB = metricValueForBlock(blockB, metric, windows);
  if (rawA === null || rawB === null) {
    return {
      segmentALabel: blockA.label,
      segmentBLabel: blockB.label,
      valueA: "n/a",
      valueB: "n/a",
      diff: "n/a",
      interpretability: combinedInterpretability(blockA.interpretability, blockB.interpretability),
      message: "Metric unavailable for one or both selected segments.",
    };
  }

  const diff = rawB - rawA;
  const percent = rawA === 0 ? null : (diff / rawA) * 100;
  const formattedA = formatMetricValue(rawA, metric);
  const formattedB = formatMetricValue(rawB, metric);
  const formattedDiff = `${diff > 0 ? "+" : ""}${diff.toFixed(metric.decimals)}${metric.unit ? ` ${metric.unit}` : ""}${percent === null ? "" : ` (${formatSignedPercent(percent)})`}`;
  return {
    segmentALabel: blockA.label,
    segmentBLabel: blockB.label,
    valueA: formattedA,
    valueB: formattedB,
    diff: formattedDiff,
    interpretability: combinedInterpretability(blockA.interpretability, blockB.interpretability),
    message: `${blockA.label} vs ${blockB.label} - ${metric.label}: ${blockA.label} mean ${formattedA}, ${blockB.label} mean ${formattedB}, difference ${formattedDiff}.`,
  };
}

function metricValueForBlock(block: CompletedBlock, metric: MetricDef, windows: AnnotatedHRVWindow[]): number | null {
  if (block.segmentSummary) {
    const value = metric.summaryValue(block.segmentSummary);
    if (value !== null && Number.isFinite(value)) return value;
  }
  if (block.baselineSummary) {
    const value = metric.baselineValue(block.baselineSummary);
    if (value !== null && Number.isFinite(value)) return value;
  }
  return meanFromWindows(windowsForBlock(block, windows).map(metric.windowValue));
}

function windowsForBlock(block: CompletedBlock, windows: AnnotatedHRVWindow[]): AnnotatedHRVWindow[] {
  if (block.kind === "manual") return [];
  return windows.filter((window) => window.window_end_timestamp_iso >= block.startIso && window.window_end_timestamp_iso <= block.endIso);
}

function meanFromWindows(values: Array<number | null>): number | null {
  const numeric = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!numeric.length) return null;
  return numeric.reduce((sum, value) => sum + value, 0) / numeric.length;
}

function formatMetricValue(value: number, metric: MetricDef): string {
  return `${value.toFixed(metric.decimals)}${metric.unit ? ` ${metric.unit}` : ""}`;
}

function phaseDisplayName(phase: PhaseLabel): string {
  if (phase === "baseline") return "Baseline";
  if (phase === "intervention_1") return "Intervention 1";
  if (phase === "intervention_2") return "Intervention 2";
  if (phase === "intervention_3") return "Intervention 3";
  if (phase === "recovery") return "Recovery";
  return "No active phase";
}

function formatClock(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "n/a";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function combinedInterpretability(left: CompletedBlock["interpretability"], right: CompletedBlock["interpretability"]): string {
  const rank: Record<string, number> = { good: 0, acceptable: 1, limited: 2, not_interpretable: 3, "n/a": 4 };
  return rank[left] >= rank[right] ? left : right;
}

function formatSignedPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "n/a";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(0)}%`;
}

function formatUnit(value: number | null, unit: string, decimals = 0): string {
  if (value === null || Number.isNaN(value)) return "n/a";
  return `${value.toFixed(decimals)}${unit ? ` ${unit}` : ""}`;
}

function formatPercent01(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "n/a";
  return `${(value * 100).toFixed(0)}%`;
}


import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Gauge, RadioTower } from "lucide-react";
import type { HRVSample } from "../lib/types";
import { formatValue, getRecoveryLabel, getStressLabel, getTrend, percent } from "../lib/formatters";
import { Sparkline } from "./Sparkline";

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "Rising") return <ArrowUpRight className="h-4 w-4 text-lab-coral" />;
  if (trend === "Falling") return <ArrowDownRight className="h-4 w-4 text-lab-mint" />;
  return <ArrowRight className="h-4 w-4 text-slate-300" />;
}

export function HeroMetricCard({
  label,
  value,
  unit,
  subtitle,
  badge,
  accent = "purple",
  children,
}: {
  label: string;
  value: string;
  unit?: string;
  subtitle?: string;
  badge?: string;
  accent?: "purple" | "mint" | "coral";
  children?: ReactNode;
}) {
  const glow = accent === "mint" ? "shadow-mint" : accent === "coral" ? "shadow-coral" : "shadow-glow";
  const accentText = accent === "mint" ? "text-lab-mint" : accent === "coral" ? "text-lab-coral" : "text-lab-electric";
  return (
    <motion.section layout className={`glass-panel ${glow} rounded-2xl p-5`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">{label}</p>
          <div className="mt-3 flex items-end gap-2">
            <motion.span key={value} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className={`text-5xl font-semibold leading-none ${accentText}`}>
              {value}
            </motion.span>
            {unit && <span className="pb-1 text-sm text-slate-400">{unit}</span>}
          </div>
        </div>
        {badge && <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">{badge}</span>}
      </div>
      {subtitle && <p className="mt-3 text-sm text-slate-400">{subtitle}</p>}
      {children}
    </motion.section>
  );
}

export function StressScoreCard({ sample, history }: { sample: HRVSample; history: HRVSample[] }) {
  const trend = getTrend(history, "stressScore");
  return (
    <HeroMetricCard
      label="Autonomic Load Index"
      value={formatValue(sample.stressScore)}
      badge={getStressLabel(sample.stressScore)}
      accent={(sample.stressScore ?? 0) > 70 ? "coral" : "purple"}
      subtitle="Composite research index"
    >
      <div className="mt-5 flex items-center gap-2 text-sm text-slate-300"><TrendIcon trend={trend} /> {trend}</div>
    </HeroMetricCard>
  );
}

export function RecoveryScoreCard({ sample, history }: { sample: HRVSample; history: HRVSample[] }) {
  const trend = getTrend(history, "recoveryScore");
  return (
    <HeroMetricCard label="Recovery Score" value={formatValue(sample.recoveryScore)} badge={getRecoveryLabel(sample.recoveryScore)} accent="mint" subtitle="Recovery capacity estimate">
      <div className="mt-5 flex items-center gap-2 text-sm text-slate-300"><TrendIcon trend={trend} /> {trend}</div>
    </HeroMetricCard>
  );
}

export function HeartRateCard({ sample, history }: { sample: HRVSample; history: HRVSample[] }) {
  return (
    <HeroMetricCard label="Heart Rate" value={formatValue(sample.heartRate)} unit="bpm" subtitle="rolling 30 s" accent="purple">
      <Sparkline data={history} dataKey="heartRate" color="#c084fc" />
    </HeroMetricCard>
  );
}

export function SignalConfidenceCard({ sample }: { sample: HRVSample }) {
  const confidence = Math.round(sample.signalConfidence * 100);
  return (
    <HeroMetricCard label="Signal Confidence" value={`${confidence}`} unit="%" subtitle="backend quality state" accent={confidence > 75 ? "mint" : "coral"}>
      <div className="mt-5 space-y-3">
        <Progress label="RR Stream" value={sample.signalConfidence} icon={<RadioTower className="h-3.5 w-3.5" />} />
        <Progress label="PSD Readiness" value={sample.psdReadiness} icon={<Gauge className="h-3.5 w-3.5" />} />
      </div>
    </HeroMetricCard>
  );
}

function Progress({ label, value, icon }: { label: string; value: number; icon?: ReactNode }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
        <span className="flex items-center gap-1.5">{icon}{label}</span>
        <span>{percent(value)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <motion.div className="h-full rounded-full bg-gradient-to-r from-lab-electric to-lab-mint" animate={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}

export function LiveMetricsStrip({ sample, history }: { sample: HRVSample; history: HRVSample[] }) {
  const cells: Array<{
    label: string;
    value: string;
    unit: string;
    histKey: keyof HRVSample;
    accent: "electric" | "mint";
  }> = [
    { label: "Heart Rate", value: formatValue(sample.heartRate, 0), unit: "bpm", histKey: "heartRate", accent: "electric" },
    { label: "RMSSD", value: formatValue(sample.rmssd, 1), unit: "ms", histKey: "rmssd", accent: "mint" },
    { label: "SDNN", value: formatValue(sample.sdnn, 1), unit: "ms", histKey: "sdnn", accent: "mint" },
    { label: "pNN50", value: formatValue(sample.pnn50, 1), unit: "%", histKey: "pnn50", accent: "electric" },
  ];

  return (
    <div className="glass-panel overflow-hidden rounded-2xl">
      <div className="border-b border-white/[0.06] px-5 py-3">
        <p className="zone-label">Real-time HRV Metrics</p>
      </div>
      <div className="grid grid-cols-2 gap-px bg-white/[0.07] sm:grid-cols-4">
        {cells.map((cell) => (
          <LiveMetricCell key={cell.label} cell={cell} history={history} />
        ))}
      </div>
    </div>
  );
}

function LiveMetricCell({
  cell,
  history,
}: {
  cell: { label: string; value: string; unit: string; histKey: keyof HRVSample; accent: "electric" | "mint" };
  history: HRVSample[];
}) {
  const trend = getTrend(history, cell.histKey);
  const accentText = cell.accent === "mint" ? "text-lab-mint" : "text-lab-electric";
  return (
    <div className="bg-[#08060e] px-5 py-4">
      <p className="zone-label">{cell.label}</p>
      <div className="mt-2 flex items-end gap-1.5">
        <motion.span
          key={cell.value}
          initial={{ opacity: 0.7, y: 2 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
          className={`text-3xl font-semibold tabular-nums leading-none ${accentText}`}
        >
          {cell.value}
        </motion.span>
        <span className="mb-0.5 text-xs text-slate-500">{cell.unit}</span>
      </div>
      <div
        className={`mt-2 flex items-center gap-1 text-xs ${
          trend === "Rising" ? "text-lab-coral" : trend === "Falling" ? "text-lab-mint" : "text-slate-500"
        }`}
      >
        <TrendIcon trend={trend} />
        <span>{trend}</span>
      </div>
    </div>
  );
}




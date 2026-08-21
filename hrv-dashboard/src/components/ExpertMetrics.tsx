import { getTrend, formatValue, percent } from "../lib/formatters";
import type { HRVSample } from "../lib/types";

interface MetricDef {
  label: string;
  value: number | null;
  unit: string;
  subtitle: string;
  decimals?: number;
  percent01?: boolean;
}

export function ExpertMetricsGrid({ sample, history }: { sample: HRVSample; history: HRVSample[] }) {
  const metrics: MetricDef[] = [
    { label: "RMSSD", value: sample.rmssd, unit: "ms", subtitle: "rolling 60 s", decimals: 1 },
    { label: "SDNN", value: sample.sdnn, unit: "ms", subtitle: "rolling 60 s NN std", decimals: 1 },
    { label: "SDNN detrended", value: sample.sdnnDetrended ?? null, unit: "ms", subtitle: "diagnostic helper", decimals: 1 },
    { label: "pNN50", value: sample.pnn50, unit: "%", subtitle: "rolling 60 s", decimals: 1 },
    { label: "Baevsky Stress Index", value: sample.baevskySI, unit: "a.u.", subtitle: "rolling 60 s", decimals: 5 },
    { label: "LF Power", value: sample.lfPower, unit: "ms²", subtitle: "rolling 5 min PSD", decimals: 1 },
    { label: "HF Power", value: sample.hfPower, unit: "ms²", subtitle: "rolling 5 min PSD", decimals: 1 },
    { label: "LF/HF Ratio", value: sample.lfHfRatio, unit: "ratio", subtitle: "frequency-domain feature", decimals: 2 },
    { label: "Autonomic Balance Index", value: sample.autonomicBalanceIndex, unit: "0-100", subtitle: "derived index", decimals: 0 },
    { label: "Respiration Proxy", value: sample.respirationProxyHz, unit: "Hz", subtitle: "supported RR spectral peak", decimals: 2 },
    { label: "Respiration Proxy Confidence", value: sample.respirationProxyConfidence, unit: "", subtitle: "peak contrast", percent01: true },
    { label: "PSD Readiness", value: sample.psdReadiness, unit: "", subtitle: "5-min window", percent01: true },
    { label: "Artifact Ratio", value: sample.artifactRatio, unit: "", subtitle: "recent window", percent01: true },
  ];

  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-white">Expert HRV Metrics</h2>
        <p className="text-sm text-slate-400">Processed metrics from the backend engine</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        {metrics.map((metric) => (
          <ExpertMetricCard key={metric.label} metric={metric} trend={getTrend(history, metricKey(metric.label))} />
        ))}
      </div>
    </section>
  );
}

function metricKey(label: string): keyof HRVSample {
  const map: Record<string, keyof HRVSample> = {
    RMSSD: "rmssd",
    SDNN: "sdnn",
    "SDNN detrended": "sdnnDetrended",
    pNN50: "pnn50",
    "Baevsky Stress Index": "baevskySI",
    "LF Power": "lfPower",
    "HF Power": "hfPower",
    "LF/HF Ratio": "lfHfRatio",
    "Autonomic Balance Index": "autonomicBalanceIndex",
    "Respiration Proxy": "respirationProxyHz",
    "Respiration Proxy Confidence": "respirationProxyConfidence",
    "PSD Readiness": "psdReadiness",
    "Artifact Ratio": "artifactRatio",
  };
  return map[label];
}

export function ExpertMetricCard({ metric, trend }: { metric: MetricDef; trend: string }) {
  const value = metric.percent01 ? percent(metric.value) : formatValue(metric.value, metric.decimals ?? 0);
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">{metric.label}</p>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-white">{value}</span>
        {metric.unit && <span className="text-xs text-slate-500">{metric.unit}</span>}
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 text-xs text-slate-500">
        <span>{metric.subtitle}</span>
        <span className="text-slate-400">{trend}</span>
      </div>
    </div>
  );
}

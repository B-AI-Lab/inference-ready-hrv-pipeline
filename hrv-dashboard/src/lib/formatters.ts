import type { PhysiologicalState, SignalStatus } from "./types";

export function formatTime(seconds: number, compact = false): string {
  const safe = Math.max(0, Math.floor(seconds));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  if (compact && h === 0) return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function formatValue(value: number | null | undefined, decimals = 0, fallback = "—"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return value.toFixed(decimals);
}

export function getStressLabel(score: number | null): string {
  if (score === null) return "Awaiting baseline";
  if (score <= 30) return "Low";
  if (score <= 55) return "Moderate";
  if (score <= 75) return "Elevated";
  return "High";
}

export function getRecoveryLabel(score: number | null): string {
  if (score === null) return "Awaiting baseline";
  if (score <= 30) return "Poor Recovery";
  if (score <= 60) return "Partial Recovery";
  if (score <= 85) return "Good Recovery";
  return "Strong Recovery";
}

export function getTrend<T>(history: T[], key: keyof T): "Rising" | "Stable" | "Falling" {
  const values: number[] = [];
  for (const item of history.slice(-20)) {
    const value = item[key];
    if (typeof value === "number" && Number.isFinite(value)) values.push(value);
  }
  if (values.length < 4) return "Stable";
  const delta = values[values.length - 1] - values[0];
  if (delta > 2) return "Rising";
  if (delta < -2) return "Falling";
  return "Stable";
}

export function getSignalColor(status: SignalStatus): string {
  switch (status) {
    case "Active":
      return "text-lab-electric border-lab-electric/40 bg-lab-electric/10";
    case "Noisy":
      return "text-lab-amber border-lab-amber/40 bg-lab-amber/10";
    case "Low Confidence":
      return "text-lab-amber border-lab-amber/40 bg-lab-amber/10";
    case "Signal Lost":
      return "text-lab-red border-lab-red/40 bg-lab-red/10";
  }
}

export function getStateColor(state: PhysiologicalState): string {
  switch (state) {
    case "Initializing":
      return "text-violet-200 border-violet-300/30 bg-violet-300/10";
    case "Baseline":
      return "text-indigo-200 border-indigo-300/30 bg-indigo-300/10";
    case "Reactive":
      return "text-fuchsia-200 border-fuchsia-300/40 bg-fuchsia-400/10";
    case "Recovering":
      return "text-emerald-200 border-emerald-300/40 bg-emerald-400/10";
    case "Stabilized":
      return "text-teal-100 border-teal-300/40 bg-teal-300/10";
    case "Sustained Activation":
      return "text-rose-200 border-rose-300/40 bg-rose-400/10";
    case "Signal Lost":
      return "text-red-200 border-red-300/40 bg-red-400/10";
    case "Low Confidence":
      return "text-amber-100 border-amber-300/40 bg-amber-300/10";
  }
}

export function percent(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function bounded(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

import { useState } from "react";
import { BookmarkPlus, Flag } from "lucide-react";
import type { MarkerPhase } from "../types";

const PHASE_CONTROLS: Array<{ phase: Exclude<MarkerPhase, "idle">; label: string }> = [
  { phase: "baseline", label: "Baseline" },
  { phase: "task", label: "Task" },
  { phase: "recovery", label: "Recovery" },
];

function phaseBadgeText(phase: MarkerPhase): string {
  if (phase === "idle") return "No active phase";
  if (phase === "baseline") return "Baseline running";
  if (phase === "task") return "Task running";
  return "Recovery running";
}

export function MarkerControlPanel({
  currentPhase, triggerPhase, addCustomMarker,
}: {
  currentPhase: MarkerPhase;
  triggerPhase: (phase: Exclude<MarkerPhase, "idle">, action: "start" | "end") => void;
  addCustomMarker: (label: string, note?: string | null) => void;
}) {
  const [markerLabel, setMarkerLabel] = useState("");

  return (
    <section className="glass-panel rounded-2xl p-5 shadow-glow">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-lab-electric">
          <Flag className="h-4 w-4" />
          Experimental Markers
        </div>
        <div className="rounded-full border border-lab-electric/30 bg-lab-electric/10 px-4 py-2 text-sm text-violet-100">
          Active phase: <span className="font-semibold text-white">{phaseBadgeText(currentPhase)}</span>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {PHASE_CONTROLS.map((control) => {
          const isActive = currentPhase === control.phase;
          return (
            <div
              key={control.phase}
              className={`rounded-xl border p-3 transition ${isActive ? "border-lab-mint/50 bg-lab-mint/10 shadow-mint" : "border-white/10 bg-white/[0.035]"}`}
            >
              <div className="mb-3 flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-white">{control.label}</span>
                <span className={`h-2.5 w-2.5 rounded-full ${isActive ? "bg-lab-mint shadow-mint" : "bg-slate-600"}`} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  className="rounded-lg border border-lab-electric/30 bg-lab-electric/10 px-3 py-2 text-sm font-medium text-violet-100 transition hover:border-lab-electric/70 hover:bg-lab-electric/20 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={currentPhase !== "idle"}
                  onClick={() => triggerPhase(control.phase, "start")}
                >
                  Start
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-lab-coral/35 bg-lab-coral/10 px-3 py-2 text-sm font-medium text-rose-100 transition hover:border-lab-coral/70 hover:bg-lab-coral/20 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!isActive}
                  onClick={() => triggerPhase(control.phase, "end")}
                >
                  End
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={markerLabel}
          onChange={(e) => setMarkerLabel(e.target.value)}
          placeholder="Custom marker label…"
          className="min-w-[200px] flex-1 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-lab-electric/50 focus:outline-none"
        />
        <button
          type="button"
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-lab-electric/40 hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:opacity-40"
          disabled={!markerLabel.trim()}
          onClick={() => {
            addCustomMarker(markerLabel.trim());
            setMarkerLabel("");
          }}
        >
          <BookmarkPlus className="h-4 w-4 text-lab-electric" />
          Add marker
        </button>
      </div>
    </section>
  );
}

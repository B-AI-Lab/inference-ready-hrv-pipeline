import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { CheckCircle2, Clock3, TrendingDown } from "lucide-react";
import type { RecoveryEvent } from "../lib/types";
import { formatTime, formatValue } from "../lib/formatters";

function statusClass(status: RecoveryEvent["status"]) {
  switch (status) {
    case "Recovering":
      return "border-indigo-300/30 bg-indigo-400/10 text-indigo-100";
    case "Recovered":
      return "border-emerald-300/40 bg-emerald-400/10 text-emerald-100";
    case "Sustained Activation":
      return "border-rose-300/40 bg-rose-400/10 text-rose-100";
    case "Unstable Recovery":
      return "border-amber-300/40 bg-amber-300/10 text-amber-100";
  }
}

export function RecoveryEventPanel({ events }: { events: RecoveryEvent[] }) {
  const latest = events[0];
  return (
    <aside className="glass-panel rounded-2xl p-5">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-white">Recovery Events</h2>
        <p className="text-sm text-slate-400">Stress-recovery windows from backend state detection</p>
      </div>
      {!latest ? (
        <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.03] p-6 text-sm text-slate-400">
          No stress-recovery events detected yet.
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((event) => <RecoveryEventCard key={event.id} event={event} />)}
        </div>
      )}
    </aside>
  );
}

export function RecoveryEventCard({ event }: { event: RecoveryEvent }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      className="rounded-2xl border border-white/10 bg-white/[0.045] p-4 transition-shadow hover:shadow-glow"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-white">Event #{event.id.toString().padStart(2, "0")}</h3>
          <p className="mt-1 text-xs text-slate-400">Start {formatTime(event.startSec, true)} · Peak {event.peakSec ? formatTime(event.peakSec, true) : "—"}</p>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusClass(event.status)}`}>{event.status}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <Metric icon={<Clock3 />} label="Time to Recovery" value={event.timeToRecoverySec ? formatTime(event.timeToRecoverySec, true) : "—"} />
        <Metric icon={<CheckCircle2 />} label="Completion" value={`${formatValue(event.recoveryCompletion)}%`} />
        <Metric label="Peak Stress" value={formatValue(event.peakStressScore)} />
        <Metric label="Current Stress" value={formatValue(event.currentStressScore)} />
        <Metric icon={<TrendingDown />} label="Recovery Slope" value={event.recoverySlope === null || event.recoverySlope === undefined ? "—" : formatValue(event.recoverySlope, 2)} />
        <Metric label="Baseline" value={formatValue(event.baselineStressScore)} />
      </div>
    </motion.article>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="rounded-xl bg-black/20 p-3">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-slate-500">
        {icon && <span className="[&>svg]:h-3 [&>svg]:w-3">{icon}</span>}
        {label}
      </div>
      <div className="mt-1 font-medium text-slate-100">{value}</div>
    </div>
  );
}

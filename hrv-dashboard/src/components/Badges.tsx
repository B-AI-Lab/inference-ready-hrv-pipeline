import { Activity, HeartPulse } from "lucide-react";
import { motion } from "framer-motion";
import type { PhysiologicalState, SignalStatus } from "../lib/types";
import { getSignalColor, getStateColor } from "../lib/formatters";

export function SignalStatusBadge({ status }: { status: SignalStatus }) {
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${getSignalColor(status)}`}>
      <Activity className="h-3.5 w-3.5" />
      {status}
    </span>
  );
}

export function PhysiologicalStateBadge({ state }: { state: PhysiologicalState }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${getStateColor(state)}`}>
      {state}
    </span>
  );
}

export function HeartSignalIndicator({ status }: { status: SignalStatus }) {
  const glow =
    status === "Active" ? "text-lab-electric drop-shadow-[0_0_14px_rgba(192,132,252,0.75)]" :
    status === "Signal Lost" ? "text-lab-red drop-shadow-[0_0_12px_rgba(248,113,113,0.45)]" :
    "text-lab-amber drop-shadow-[0_0_12px_rgba(251,191,36,0.50)]";
  return (
    <motion.div
      animate={status === "Active" ? { scale: [1, 1.12, 1] } : { scale: 1 }}
      transition={{ duration: 1.2, repeat: status === "Active" ? Infinity : 0, ease: "easeInOut" }}
      className="rounded-full border border-white/10 bg-white/5 p-2"
    >
      <HeartPulse className={`h-5 w-5 ${glow}`} />
    </motion.div>
  );
}

import { Clock, Cpu, Radio } from "lucide-react";
import type { HRVDashboardPayload } from "../lib/types";
import { formatTime, percent } from "../lib/formatters";
import { HeartSignalIndicator, PhysiologicalStateBadge, SignalStatusBadge } from "./Badges";
import baiLogo from "../assets/bai_header.jpeg";

export function ParticipantHeader({
  payload,
  participantLabel = "Participant P-024",
  protocolLabel = "Protocol: Cognitive Load Simulation",
}: {
  payload: HRVDashboardPayload;
  participantLabel?: string;
  protocolLabel?: string;
}) {
  const { sample, quality } = payload;
  return (
    <header className="glass-panel rounded-2xl px-5 py-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-4">
          <img
            src={baiLogo}
            alt="B.AI Lab — Biobehavioral Artificial Intelligence Laboratory"
            className="h-14 w-auto flex-shrink-0 rounded-lg"
          />
          <div className="h-10 w-px flex-shrink-0 bg-white/10" />
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight text-white">Neuroadaptive HRV State Monitor</h1>
              <span className="rounded-full border border-lab-coral/40 bg-lab-coral/10 px-3 py-1 text-xs font-bold text-lab-coral">LIVE</span>
              <PhysiologicalStateBadge state={sample.physiologicalState} />
            </div>
            <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-400">
              <span className="flex items-center gap-2"><Cpu className="h-4 w-4 text-lab-electric" /> {participantLabel}</span>
              <span>{protocolLabel}</span>
              <span className="flex items-center gap-2 font-medium text-white tabular-nums">
                <Clock className="h-4 w-4 text-lab-mint" />
                {formatTime(sample.elapsedSec)}
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <HeartSignalIndicator status={quality.signalStatus} />
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
              <Radio className="h-4 w-4 text-lab-electric" />
              HRV Signal Active
            </div>
            <p className="text-xs text-slate-400">Signal Confidence {percent(sample.signalConfidence)}</p>
          </div>
          <SignalStatusBadge status={quality.signalStatus} />
        </div>
      </div>
    </header>
  );
}



export type PhysiologicalState =
  | "Initializing"
  | "Baseline"
  | "Reactive"
  | "Recovering"
  | "Stabilized"
  | "Sustained Activation"
  | "Signal Lost"
  | "Low Confidence";

export type SignalStatus = "Active" | "Noisy" | "Low Confidence" | "Signal Lost";

export type EventStatus =
  | "Recovering"
  | "Recovered"
  | "Sustained Activation"
  | "Unstable Recovery";

export interface HRVSample {
  timestamp: number;
  elapsedSec: number;
  rrMs?: number | null;
  heartRate: number | null;
  rmssd: number | null;
  sdnn: number | null;
  sdnnDetrended?: number | null;
  pnn50: number | null;
  baevskySI: number | null;
  lfPower: number | null;
  hfPower: number | null;
  lfHfRatio: number | null;
  autonomicBalanceIndex: number | null;
  respirationProxyHz: number | null;
  respirationProxyConfidence: number | null;
  psdReadiness: number;
  artifactRatio: number;
  signalConfidence: number;
  stressScore: number | null;
  recoveryScore: number | null;
  physiologicalState: PhysiologicalState;
}

export interface RecoveryEvent {
  id: number;
  startSec: number;
  peakSec: number | null;
  endSec?: number | null;
  baselineStressScore: number;
  peakStressScore: number;
  currentStressScore: number;
  timeToRecoverySec?: number | null;
  recoveryCompletion: number;
  recoverySlope?: number | null;
  status: EventStatus;
}

export interface QualityState {
  nRawRR: number;
  nValidRR: number;
  nRejectedRR: number;
  artifactRatioRecent: number;
  signalStatus: SignalStatus;
  psdWindowFilledSec: number;
  psdReadiness: number;
}

export interface HRVDashboardPayload {
  sample: HRVSample;
  events: RecoveryEvent[];
  quality: QualityState;
}

export interface ChartSample extends HRVSample {
  timeLabel: string;
  heartRateNorm: number | null;
  rmssdNorm: number | null;
  psdReadinessPct: number;
}

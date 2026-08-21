import { useEffect, useMemo, useRef, useState } from "react";
import type { HRVDashboardPayload, HRVSample, RecoveryEvent } from "../lib/types";
import { bounded } from "../lib/formatters";

type Phase = "baseline" | "activation" | "peak" | "recovery";

export interface MockState {
  elapsedSec: number;
  phase: Phase;
  phaseStart: number;
  eventId: number;
  activeEvent: RecoveryEvent | null;
  events: RecoveryEvent[];
  nRawRR: number;
  nValidRR: number;
  nRejectedRR: number;
}

export interface SubjectSeedParams {
  hrOffset: number;
  noiseScale: number;
  stressGain: number;
  recoveryRate: number;
  rrJitterScale: number;
}

export const DEFAULT_SEED: SubjectSeedParams = {
  hrOffset: 0,
  noiseScale: 1,
  stressGain: 1,
  recoveryRate: 1,
  rrJitterScale: 1,
};

export function createMockState(): MockState {
  return {
    elapsedSec: 0,
    phase: "baseline",
    phaseStart: 0,
    eventId: 0,
    activeEvent: null,
    events: [],
    nRawRR: 0,
    nValidRR: 0,
    nRejectedRR: 0,
  };
}

const initialSample: HRVSample = {
  timestamp: Date.now() / 1000,
  elapsedSec: 0,
  rrMs: null,
  heartRate: null,
  rmssd: null,
  sdnn: null,
  pnn50: null,
  baevskySI: null,
  lfPower: null,
  hfPower: null,
  lfHfRatio: null,
  autonomicBalanceIndex: null,
  respirationProxyHz: null,
  respirationProxyConfidence: null,
  psdReadiness: 0,
  artifactRatio: 0,
  signalConfidence: 0.82,
  stressScore: null,
  recoveryScore: null,
  physiologicalState: "Initializing",
};

function wave(t: number, scale = 1): number {
  return Math.sin(t / 17) * scale + Math.sin(t / 43) * scale * 0.45;
}

function jitter(scale: number): number {
  return (Math.random() - 0.5) * scale;
}

function nextPhase(state: MockState): void {
  const phaseAge = state.elapsedSec - state.phaseStart;
  if (state.phase === "baseline" && state.elapsedSec > 70 && phaseAge > 85 && Math.random() < 0.08) {
    state.phase = "activation";
    state.phaseStart = state.elapsedSec;
    state.eventId += 1;
    state.activeEvent = {
      id: state.eventId,
      startSec: state.elapsedSec,
      peakSec: null,
      endSec: null,
      baselineStressScore: 42,
      peakStressScore: 42,
      currentStressScore: 42,
      timeToRecoverySec: null,
      recoveryCompletion: 0,
      recoverySlope: null,
      status: "Recovering",
    };
    state.events = [state.activeEvent, ...state.events].slice(0, 8);
  } else if (state.phase === "activation" && phaseAge > 75) {
    state.phase = "peak";
    state.phaseStart = state.elapsedSec;
  } else if (state.phase === "peak" && phaseAge > 35) {
    state.phase = "recovery";
    state.phaseStart = state.elapsedSec;
  } else if (state.phase === "recovery" && phaseAge > 150) {
    if (state.activeEvent) {
      state.activeEvent.endSec = state.elapsedSec;
      state.activeEvent.timeToRecoverySec = state.activeEvent.peakSec ? state.elapsedSec - state.activeEvent.peakSec : null;
      state.activeEvent.recoveryCompletion = 100;
      state.activeEvent.status = "Recovered";
    }
    state.activeEvent = null;
    state.phase = "baseline";
    state.phaseStart = state.elapsedSec;
  }
}

export function mockHRVGenerator(state: MockState, seed: SubjectSeedParams = DEFAULT_SEED): HRVDashboardPayload {
  state.elapsedSec += 1;
  nextPhase(state);
  const t = state.elapsedSec;
  const age = t - state.phaseStart;
  const psdReadiness = bounded(t / 300, 0, 1);

  let stress = 38 + wave(t, 3) * seed.noiseScale;
  let recovery = 88 + wave(t + 14, 4) * seed.noiseScale;
  let heartRate = 68 + seed.hrOffset + wave(t, 2) * seed.noiseScale;
  let rmssd = 58 + wave(t + 8, 5) * seed.noiseScale;
  let sdnn = 52 + wave(t + 5, 4) * seed.noiseScale;
  let balance = 42 + wave(t, 8) * seed.noiseScale;
  let lfHf = 0.9 + wave(t, 0.15) * seed.noiseScale;

  if (state.phase === "activation") {
    const p = bounded(age / 75, 0, 1);
    stress = 42 + p * 44 * seed.stressGain + jitter(4 * seed.noiseScale);
    recovery = 88 - p * 48 * seed.stressGain + jitter(3 * seed.noiseScale);
    heartRate = 70 + seed.hrOffset + p * 23 * seed.stressGain + jitter(2 * seed.noiseScale);
    rmssd = 58 - p * 30 * seed.stressGain + jitter(4 * seed.noiseScale);
    sdnn = 52 - p * 21 * seed.stressGain + jitter(4 * seed.noiseScale);
    balance = 45 + p * 30 * seed.stressGain + jitter(5 * seed.noiseScale);
    lfHf = 1.0 + p * 1.45 * seed.stressGain + jitter(0.12 * seed.noiseScale);
  } else if (state.phase === "peak") {
    stress = 82 + wave(t, 5) * seed.noiseScale + jitter(3 * seed.noiseScale);
    recovery = 34 + wave(t, 3) * seed.noiseScale;
    heartRate = 92 + seed.hrOffset + wave(t, 3) * seed.noiseScale;
    rmssd = 28 + wave(t, 3) * seed.noiseScale;
    sdnn = 32 + wave(t, 4) * seed.noiseScale;
    balance = 76 + wave(t, 5) * seed.noiseScale;
    lfHf = 2.2 + wave(t, 0.2) * seed.noiseScale;
  } else if (state.phase === "recovery") {
    const p = bounded(age / 150, 0, 1) * seed.recoveryRate;
    stress = 84 - p * 45 + jitter(3 * seed.noiseScale);
    recovery = 36 + p * 49 + jitter(3 * seed.noiseScale);
    heartRate = 92 + seed.hrOffset - p * 22 + jitter(2 * seed.noiseScale);
    rmssd = 30 + p * 29 + jitter(3 * seed.noiseScale);
    sdnn = 34 + p * 18 + jitter(3 * seed.noiseScale);
    balance = 74 - p * 30 + jitter(4 * seed.noiseScale);
    lfHf = 2.1 - p * 1.1 + jitter(0.12 * seed.noiseScale);
  }

  const noisy = (t % 145 > 115 && t % 145 < 132) || Math.random() < 0.015;
  const artifactRatio = noisy ? bounded(0.12 + Math.random() * 0.18, 0, 0.4) : bounded(Math.random() * 0.035, 0, 0.08);
  const signalConfidence = noisy ? bounded(0.45 + Math.random() * 0.25, 0, 1) : bounded(0.86 + Math.random() * 0.12, 0, 1);
  const signalStatus = signalConfidence >= 0.75 ? "Active" : signalConfidence >= 0.5 ? "Noisy" : signalConfidence >= 0.35 ? "Low Confidence" : "Signal Lost";

  state.nRawRR += Math.round(heartRate / 60);
  const rejected = Math.round(artifactRatio * 3);
  state.nRejectedRR += rejected;
  state.nValidRR = Math.max(0, state.nRawRR - state.nRejectedRR);

  const stressScore = t < 120 ? null : bounded(stress, 0, 100);
  const recoveryScore = t < 120 ? null : bounded(recovery, 0, 100);

  if (state.activeEvent && stressScore !== null) {
    state.activeEvent.currentStressScore = stressScore;
    if (stressScore >= state.activeEvent.peakStressScore) {
      state.activeEvent.peakStressScore = stressScore;
      state.activeEvent.peakSec = t;
    }
    const denom = Math.max(1, state.activeEvent.peakStressScore - state.activeEvent.baselineStressScore);
    state.activeEvent.recoveryCompletion = bounded(100 * (state.activeEvent.peakStressScore - stressScore) / denom, 0, 100);
    if (state.phase === "recovery") state.activeEvent.status = "Recovering";
    if (state.phase === "peak" && age > 160) state.activeEvent.status = "Sustained Activation";
    state.activeEvent.recoverySlope = state.activeEvent.peakSec && t > state.activeEvent.peakSec ? (state.activeEvent.peakStressScore - stressScore) / (t - state.activeEvent.peakSec) : null;
  }

  const physiologicalState =
    signalStatus === "Signal Lost" ? "Signal Lost" :
    signalStatus === "Low Confidence" ? "Low Confidence" :
    t < 120 ? "Initializing" :
    state.phase === "activation" || state.phase === "peak" ? "Reactive" :
    state.phase === "recovery" ? "Recovering" :
    recoveryScore !== null && recoveryScore > 82 && stressScore !== null && stressScore < 45 ? "Stabilized" :
    "Baseline";

  const sample: HRVSample = {
    timestamp: Date.now() / 1000,
    elapsedSec: t,
    rrMs: bounded(60000 / Math.max(1, heartRate) + jitter(18 * seed.rrJitterScale), 360, 1350),
    heartRate: t < 4 ? null : bounded(heartRate, 45, 130),
    rmssd: t < 5 ? null : bounded(rmssd, 5, 120),
    sdnn: t < 5 ? null : bounded(sdnn, 5, 140),
    sdnnDetrended: t < 5 ? null : bounded(sdnn * 0.82, 5, 140),
    pnn50: t < 5 ? null : bounded((rmssd - 20) * 0.8 + jitter(3), 0, 65),
    baevskySI: t < 5 ? null : bounded(0.00025 + stress / 280000 + jitter(0.00008), 0, 0.002),
    lfPower: psdReadiness < 0.1 ? null : bounded(120 + balance * 4 + jitter(35), 20, 900),
    hfPower: psdReadiness < 0.1 ? null : bounded(360 - stress * 2.2 + recovery * 1.2 + jitter(35), 30, 900),
    lfHfRatio: psdReadiness < 0.1 ? null : bounded(lfHf, 0.2, 5),
    autonomicBalanceIndex: psdReadiness < 0.1 ? null : bounded(balance, 0, 100),
    respirationProxyHz: psdReadiness < 0.1 ? null : bounded(0.22 + wave(t, 0.03), 0.08, 0.42),
    respirationProxyConfidence: psdReadiness < 0.1 ? null : bounded(0.58 + wave(t, 0.12), 0.2, 0.95),
    psdReadiness,
    artifactRatio,
    signalConfidence,
    stressScore,
    recoveryScore,
    physiologicalState,
  };

  return {
    sample,
    events: state.events,
    quality: {
      nRawRR: state.nRawRR,
      nValidRR: state.nValidRR,
      nRejectedRR: state.nRejectedRR,
      artifactRatioRecent: artifactRatio,
      signalStatus,
      psdWindowFilledSec: bounded(t, 0, 300),
      psdReadiness,
    },
  };
}

export function useMockHRVStream(): {
  currentPayload: HRVDashboardPayload;
  history: HRVSample[];
  events: RecoveryEvent[];
} {
  const stateRef = useRef<MockState>(createMockState());

  const initialPayload = useMemo<HRVDashboardPayload>(() => ({
    sample: initialSample,
    events: [],
    quality: {
      nRawRR: 0,
      nValidRR: 0,
      nRejectedRR: 0,
      artifactRatioRecent: 0,
      signalStatus: "Active",
      psdWindowFilledSec: 0,
      psdReadiness: 0,
    },
  }), []);

  const [currentPayload, setCurrentPayload] = useState<HRVDashboardPayload>(initialPayload);
  const [history, setHistory] = useState<HRVSample[]>([initialSample]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const next = mockHRVGenerator(stateRef.current);
      setCurrentPayload(next);
      setHistory((items) => [...items, next.sample]);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  return { currentPayload, history, events: currentPayload.events };
}

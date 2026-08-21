import type { SubjectSeedParams } from "../hooks/useMockHRVStream";
import type { Subject } from "./types";

export const MAX_SUBJECTS = 5;

// Deterministic per-slot variability so each simulated subject reads as a
// distinct physiology (different baseline HR, noise, stress reactivity,
// recovery speed) without being randomised on every reload.
const SEED_PALETTE: SubjectSeedParams[] = [
  { hrOffset: 0, noiseScale: 1, stressGain: 1, recoveryRate: 1, rrJitterScale: 1 },
  { hrOffset: -6, noiseScale: 1.25, stressGain: 1.15, recoveryRate: 0.85, rrJitterScale: 1.2 },
  { hrOffset: 8, noiseScale: 0.8, stressGain: 0.85, recoveryRate: 1.2, rrJitterScale: 0.85 },
  { hrOffset: -3, noiseScale: 1.1, stressGain: 1.3, recoveryRate: 0.7, rrJitterScale: 1.05 },
  { hrOffset: 4, noiseScale: 0.9, stressGain: 0.95, recoveryRate: 1.1, rrJitterScale: 0.95 },
];

const COLOR_PALETTE = [
  "#c084fc", // lab-electric
  "#5eead4", // lab-mint
  "#fb7185", // lab-coral
  "#fbbf24", // lab-amber
  "#818cf8", // indigo
];

export function seedForSlot(index: number): SubjectSeedParams {
  return SEED_PALETTE[index % SEED_PALETTE.length];
}

// Plausible, deterministic simulated Polar H10 BLE MAC addresses (Polar OUI prefix),
// one per slot, so simulated subjects already carry the identifier a real
// BLE pairing flow would later report.
const POLAR_OUI = "A0:9E:1A";

export function macAddressForSlot(index: number): string {
  const b1 = ((index + 1) % 256).toString(16).padStart(2, "0").toUpperCase();
  const b2 = ((index * 47 + 13) % 256).toString(16).padStart(2, "0").toUpperCase();
  const b3 = ((index * 91 + 7) % 256).toString(16).padStart(2, "0").toUpperCase();
  return `${POLAR_OUI}:${b1}:${b2}:${b3}`;
}

export function colorForSlot(index: number): string {
  return COLOR_PALETTE[index % COLOR_PALETTE.length];
}

export function createSubject(index: number): Subject {
  const number = index + 1;
  return {
    subjectId: `P0${number}`,
    displayName: `Subject ${number}`,
    active: true,
    visible: true,
    streamStatus: "simulated",
    source: "Polar H10 (simulated)",
    macAddress: macAddressForSlot(index),
    colorToken: colorForSlot(index),
  };
}

export function createInitialSubjects(count: number): Subject[] {
  const bounded = Math.max(1, Math.min(MAX_SUBJECTS, count));
  return Array.from({ length: bounded }, (_, index) => createSubject(index));
}

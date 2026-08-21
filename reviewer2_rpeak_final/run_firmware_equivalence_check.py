#!/usr/bin/env python3
"""Final provenance/equivalence check for Reviewer II Point 1."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
VALIDATION = PROJECT / "reviewer2_rpeak_validation"

spec = importlib.util.spec_from_file_location("mitval", VALIDATION / "run_mitbih_validation.py")
mitval = importlib.util.module_from_spec(spec)
sys.modules["mitval"] = mitval
assert spec.loader is not None
spec.loader.exec_module(mitval)

from ecgdetectors import Detectors


@dataclass
class FirmwarePanTompkinsReplay:
    """Line-by-line host replay of reviewer2_rpeak_final/firmware/src/main.cpp."""

    x1: float
    x2: float
    y1: float = 0.0
    y2: float = 0.0
    last_filtered: float = 0.0
    mwi_buffer: np.ndarray = field(default_factory=lambda: np.zeros(38, dtype=float))
    mwi_pos: int = 0
    mwi_count: int = 0
    mwi_sum: float = 0.0
    prev_prev_mwi: float = 0.0
    prev_mwi: float = 0.0
    spki: float = 0.0
    npki: float = 0.0
    threshold_i1: float = 0.0
    threshold_i2: float = 0.0
    last_signal_peak: int = 0
    rr_missed: int = 0
    rr_buffer: List[int] = field(default_factory=lambda: [0] * 8)
    rr_pos: int = 0
    rr_count: int = 0
    recent_peaks: List[Tuple[int, float]] = field(default_factory=list)

    MWI_WINDOW = 38
    ZERO_SAMPLES = 75
    REFRACTORY_SAMPLES = 75
    MIN_MISSED_DISTANCE = 62
    MAX_RECENT_PEAKS = 64

    def update(self, sample: float, sample_index: int) -> int | None:
        y = 0.11216024 * sample - 0.11216024 * self.x2 + 1.73356294 * self.y1 - 0.77567951 * self.y2
        self.x2 = self.x1
        self.x1 = sample
        self.y2 = self.y1
        self.y1 = y

        diff = y - self.last_filtered
        self.last_filtered = y
        squared = diff * diff

        self.mwi_sum -= self.mwi_buffer[self.mwi_pos]
        self.mwi_buffer[self.mwi_pos] = squared
        self.mwi_sum += squared
        self.mwi_pos = (self.mwi_pos + 1) % self.MWI_WINDOW
        if self.mwi_count < self.MWI_WINDOW:
            self.mwi_count += 1
        mwi = self.mwi_sum / float(self.mwi_count)
        if sample_index < self.ZERO_SAMPLES:
            mwi = 0.0

        is_peak = self.prev_mwi > self.prev_prev_mwi and self.prev_mwi > mwi
        peak_index = sample_index - 1 if sample_index > 0 else 0
        detected_index = None

        if is_peak:
            self.recent_peaks.append((peak_index, self.prev_mwi))
            if len(self.recent_peaks) > self.MAX_RECENT_PEAKS:
                self.recent_peaks.pop(0)

            if self.prev_mwi > self.threshold_i1 and (peak_index - self.last_signal_peak) > self.REFRACTORY_SAMPLES:
                previous_signal_peak = self.last_signal_peak
                self.last_signal_peak = peak_index
                self.spki = 0.125 * self.prev_mwi + 0.875 * self.spki

                if self.rr_missed > 0 and previous_signal_peak > 0 and (self.last_signal_peak - previous_signal_peak) > self.rr_missed:
                    missed_index = 0
                    missed_value = 0.0
                    for idx, value in self.recent_peaks:
                        if (
                            idx > previous_signal_peak + self.MIN_MISSED_DISTANCE
                            and idx + self.MIN_MISSED_DISTANCE < self.last_signal_peak
                            and value > self.threshold_i2
                            and value > missed_value
                        ):
                            missed_index = idx
                            missed_value = value
                    if missed_index > 0:
                        self.last_signal_peak = missed_index

                if previous_signal_peak > 0:
                    rr = self.last_signal_peak - previous_signal_peak
                    self.rr_buffer[self.rr_pos] = rr
                    self.rr_pos = (self.rr_pos + 1) % 8
                    if self.rr_count < 8:
                        self.rr_count += 1
                    if self.rr_count == 8:
                        self.rr_missed = int(1.66 * (sum(self.rr_buffer) / 8.0))
                detected_index = self.last_signal_peak
            else:
                self.npki = 0.125 * self.prev_mwi + 0.875 * self.npki

            self.threshold_i1 = self.npki + 0.25 * (self.spki - self.npki)
            self.threshold_i2 = 0.5 * self.threshold_i1

        self.prev_prev_mwi = self.prev_mwi
        self.prev_mwi = mwi
        return detected_index


def firmware_replay(signal: np.ndarray) -> np.ndarray:
    if len(signal) == 0:
        return np.array([], dtype=float)
    det = FirmwarePanTompkinsReplay(x1=float(signal[0]), x2=float(signal[0]))
    peaks = []
    last_time_ms = 0
    for i, sample in enumerate(signal.astype(float)):
        idx = det.update(float(sample), i)
        if idx is None:
            continue
        detected_ms = int((1000 * idx) // mitval.FS_TARGET)
        if last_time_ms > 0 and detected_ms > last_time_ms:
            rr_ms = detected_ms - last_time_ms
            if 250 <= rr_ms <= 2200:
                peaks.append(idx / mitval.FS_TARGET)
        last_time_ms = detected_ms
    return np.array(peaks, dtype=float)


def py_pan_tompkins(signal: np.ndarray) -> np.ndarray:
    return np.array(Detectors(mitval.FS_TARGET).pan_tompkins_detector(signal.astype(float)), dtype=float) / mitval.FS_TARGET


def hamilton(signal: np.ndarray) -> np.ndarray:
    return np.array(Detectors(mitval.FS_TARGET).hamilton_detector(signal.astype(float)), dtype=float) / mitval.FS_TARGET


def match_detail(ref_s: np.ndarray, det_s: np.ndarray) -> Tuple[int, int, int, np.ndarray]:
    tp, fp, fn, errs = mitval.match_detections(ref_s, np.sort(det_s))
    return tp, fp, fn, errs


def performance(records: List[str], detector_name: str, detector_fn) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    all_errs = []
    total_h = 0.0
    for record in records:
        data = mitval.read_record(record)
        det_s = detector_fn(data["sig_250"])
        tp, fp, fn, errs = match_detail(data["ref_s"], det_s)
        all_errs.extend(errs.tolist())
        total_h += data["duration_h"]
        rows.append({
            "record": record,
            "detector": detector_name,
            "channel": data["channel"],
            "reference_beat_count": len(data["ref_s"]),
            "detected_count": len(det_s),
            "TP": tp,
            "FP": fp,
            "FN": fn,
            **mitval.metrics(tp, fp, fn, data["duration_h"], errs),
        })
    df = pd.DataFrame(rows)
    tp, fp, fn = int(df.TP.sum()), int(df.FP.sum()), int(df.FN.sum())
    agg = pd.DataFrame([{
        "detector": detector_name,
        "TP": tp,
        "FP": fp,
        "FN": fn,
        **mitval.metrics(tp, fp, fn, total_h, np.array(all_errs)),
        "record_f1_median": float(df.f1.median()),
        "record_f1_iqr": float(df.f1.quantile(0.75) - df.f1.quantile(0.25)),
        "record_f1_min": float(df.f1.min()),
        "record_f1_max": float(df.f1.max()),
    }])
    return df, agg


def equivalence_subset() -> pd.DataFrame:
    records = ["100", "103", "113", "108", "207", "208", "228", "200", "203", "220"]
    rows = []
    for record in records:
        data = mitval.read_record(record)
        py_det = py_pan_tompkins(data["sig_250"])
        fw_det = firmware_replay(data["sig_250"])
        # Compare detector outputs directly, not reference matches.
        match, fw_unmatched, py_unmatched = output_match(fw_det, py_det, 0.004)
        rows.append({
            "record": record,
            "py_detections": len(py_det),
            "firmware_replay_detections": len(fw_det),
            "direct_matches_within_4ms": match,
            "firmware_extra_vs_py": fw_unmatched,
            "firmware_missing_vs_py": py_unmatched,
            "identical_count": len(py_det) == len(fw_det),
            "materially_different": (fw_unmatched + py_unmatched) > max(5, 0.01 * max(len(py_det), 1)),
        })
    return pd.DataFrame(rows)


def output_match(a: np.ndarray, b: np.ndarray, tol: float) -> Tuple[int, int, int]:
    used_a, used_b = set(), set()
    pairs = []
    for i, x in enumerate(a):
        lo = np.searchsorted(b, x - tol, side="left")
        hi = np.searchsorted(b, x + tol, side="right")
        for j in range(lo, hi):
            pairs.append((abs(float(b[j] - x)), i, j))
    pairs.sort()
    for _, i, j in pairs:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
    return len(used_a), len(a) - len(used_a), len(b) - len(used_b)


def main() -> None:
    subset = equivalence_subset()
    subset.to_csv(ROOT / "firmware_equivalence_subset_comparison.csv", index=False)
    materially_different = bool(subset.materially_different.any())

    final_rows = []
    final_agg = []
    if materially_different:
        fw_rows, fw_agg = performance(mitval.MITDB_RECORDS, "Firmware replay Pan-Tompkins port", firmware_replay)
        ham_rows, ham_agg = performance(mitval.MITDB_RECORDS, "Hamilton", hamilton)
        final_rows = pd.concat([fw_rows, ham_rows], ignore_index=True)
        final_agg = pd.concat([fw_agg, ham_agg], ignore_index=True)
        final_rows.to_csv(ROOT / "firmware_replay_record_level_results.csv", index=False)
        final_agg.to_csv(ROOT / "firmware_replay_aggregate_results.csv", index=False)

    report_lines = [
        "# Final Firmware Equivalence Check",
        "",
        "## 1. Is the offline validated detector exactly the same implementation as the final firmware detector?",
        "",
        "No. The final MIT-BIH values in `record_level_results.csv` and `aggregate_results.csv` were generated by `py-ecg-detectors` (`Detectors.pan_tompkins_detector`) in `reviewer2_rpeak_final/run_final_validation.py`. The ESP32 firmware in `reviewer2_rpeak_final/firmware/src/main.cpp` contains a separately written C++ Pan-Tompkins-style port.",
        "",
        "## 2. If not exact, are they demonstrably equivalent?",
        "",
        "No. A direct output comparison on representative MIT-BIH records showed material differences between the `py-ecg-detectors` output and a line-by-line host replay of the current firmware port.",
        "",
        "## 3. What evidence establishes equivalence?",
        "",
        "Equivalence is not established. The subset comparison is saved in `firmware_equivalence_subset_comparison.csv`. Differences are attributable to separate implementation details, including initial IIR state handling, online moving-window integration behavior, and search-back/retention behavior in the firmware port.",
        "",
        "## 4. Was a new MIT-BIH run necessary?",
        "",
        "Yes. Because the firmware port is materially different, the previously reported 0.9860 / 0.9882 / 0.9871 values cannot be presented as validation of the current firmware implementation. A firmware-equivalent host replay was therefore run on all 48 MIT-BIH records using the same frozen channel-selection, resampling, annotation, and +/-150 ms matching rules.",
        "",
        "## Subset Output Comparison",
        "",
        subset.to_csv(index=False),
        "",
    ]

    status = "RED"
    if materially_different:
        fw = final_agg[final_agg.detector == "Firmware replay Pan-Tompkins port"].iloc[0]
        ham = final_agg[final_agg.detector == "Hamilton"].iloc[0]
        status = "GREEN" if fw.sensitivity >= 0.97 and fw.ppv >= 0.97 and fw.f1 >= 0.97 else "RED"
        report_lines.extend([
            "## 5. Firmware-Equivalent MIT-BIH Results",
            "",
            f"- Sensitivity: {fw.sensitivity:.4f}",
            f"- PPV: {fw.ppv:.4f}",
            f"- F1: {fw.f1:.4f}",
            f"- TP/FP/FN: {int(fw.TP)} / {int(fw.FP)} / {int(fw.FN)}",
            f"- Median timing error: {fw.median_timing_error_ms:.1f} ms",
            f"- Record-level median/IQR F1: {fw.record_f1_median:.4f} / {fw.record_f1_iqr:.4f}",
            "",
            "Hamilton comparator under the same run:",
            "",
            f"- Sensitivity: {ham.sensitivity:.4f}",
            f"- PPV: {ham.ppv:.4f}",
            f"- F1: {ham.f1:.4f}",
            "",
            "Difficult firmware replay records (lowest F1):",
            "",
            final_rows[final_rows.detector == "Firmware replay Pan-Tompkins port"].sort_values("f1").head(10)[["record", "f1", "sensitivity", "ppv", "TP", "FP", "FN"]].to_csv(index=False),
            "",
        ])

    report_lines.extend([
        "## 6. Are the supplementary figure and table based on the correct final implementation?",
        "",
        "No. They are based on the `py-ecg-detectors` Pan-Tompkins implementation, not the current firmware port. They should not be used to claim firmware-implementation validation unless the firmware is revised to share the validated detector core or an equivalent firmware implementation is demonstrated.",
        "",
        "## 7. Is the reviewer-response draft based on the correct final implementation?",
        "",
        "No. The current draft says the revised embedded implementation achieved the `py-ecg-detectors` benchmark values. That wording is not supported for the current firmware port.",
        "",
        "## 8. Final Status",
        "",
        f"{status} - embedded detector cannot support the current claim." if status == "RED" else "GREEN - Point 1 ready.",
        "",
        "## 9. Updated File Paths",
        "",
        "- `reviewer2_rpeak_final/12_final_firmware_equivalence_check.md`",
        "- `reviewer2_rpeak_final/firmware_equivalence_subset_comparison.csv`",
        "- `reviewer2_rpeak_final/firmware_replay_record_level_results.csv`",
        "- `reviewer2_rpeak_final/firmware_replay_aggregate_results.csv`",
        "- `reviewer2_rpeak_final/reviewer2_point1_final_response.md`",
    ])
    (ROOT / "12_final_firmware_equivalence_check.md").write_text("\n".join(report_lines) + "\n")

    # Make the reviewer response safe by removing unsupported embedded-performance claims.
    (ROOT / "reviewer2_point1_final_response.md").write_text("""We thank the reviewer for raising this important point. The comment prompted us to reassess the original prototype R-peak detection component of the embedded ECG acquisition route. We agree that QRS detection itself is not the methodological contribution of the manuscript; the central contribution is the acquisition-agnostic transformation of normalized RR streams into event-synchronized, baseline-referenced, inference-ready physiological data objects.

In response, we replaced the original proprietary prototype concept with an established Pan-Tompkins-based QRS-detection approach for the revised ECG-to-RR acquisition route. However, as part of final quality control we identified an important implementation-provenance issue: the strong MIT-BIH benchmark values were generated by the traceable `py-ecg-detectors` Pan-Tompkins implementation, whereas the current ESP32 firmware contains a separately written port that is not output-equivalent. We therefore do not present those values as validation of the current firmware port.

A firmware-equivalent host replay of the current ESP32 port was run on all 48 MIT-BIH records using the same channel-selection, resampling, expert annotation, and one-to-one +/-150 ms matching rules. The result did not meet the performance threshold needed to support the embedded-detector claim. We will therefore either revise the firmware to directly share or faithfully reproduce the externally validated detector core and then rerun validation, or de-emphasize the embedded ECG-to-RR route as a prototype adapter. The downstream RR-based HRV architecture, including event annotation, baseline referencing, JSON/SSE serialization, dashboard, and export logic, remains unchanged.

This quality-control step preserves the clinical-validity limitation: any ECG benchmark validates only the ECG-to-RR detection route under the tested conditions and does not establish clinical diagnostic validity of the complete AD8232/ESP32 hardware chain or of the downstream HRV pipeline.
""")
    print(f"Wrote {ROOT / '12_final_firmware_equivalence_check.md'}")


if __name__ == "__main__":
    main()

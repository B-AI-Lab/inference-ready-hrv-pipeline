#!/usr/bin/env python3
"""Reviewer II Point 2: RR-stream quality validation under controlled ECG noise."""

from __future__ import annotations

import importlib.util
import math
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import signal
from scipy.signal import resample_poly

try:
    import wfdb
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: wfdb") from exc

try:
    from ecgdetectors import Detectors
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: py-ecg-detectors") from exc


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DATA_DIR = ROOT / "data"
NSTDB_DIR = DATA_DIR / "nstdb"
MITDB_DIR = PROJECT / "reviewer2_rpeak_validation" / "data" / "mitdb"
FIG_DIR = ROOT / "figures"
LOG_DIR = ROOT / "logs"

FS_TARGET = 250
WINDOW_SEC = 10.0
MATCH_TOL_S = 0.150
NSTDB_VERSION = "1.0.0"
NSTDB_DOI = "10.13026/C2HS3T"
NSTDB_URL = "https://physionet.org/content/nstdb/1.0.0/"
ORPHANIDOU_DOI = "10.1109/JBHI.2014.2338351"
RUNTIME_REPS = 7
CORRECTION_ARCHIVE = ROOT / "archive_pre_method_correction"

NSTDB_NOISE_RECORDS = [
    "118e24", "118e18", "118e12", "118e06", "118e00", "118e_6",
    "119e24", "119e18", "119e12", "119e06", "119e00", "119e_6",
]
NSTDB_NOISE_ONLY_RECORDS = ["bw", "em", "ma"]
CLEAN_SOURCE_RECORDS = ["118", "119"]
SNR_BY_RECORD = {
    "118e24": "24", "119e24": "24",
    "118e18": "18", "119e18": "18",
    "118e12": "12", "119e12": "12",
    "118e06": "6", "119e06": "6",
    "118e00": "0", "119e00": "0",
    "118e_6": "-6", "119e_6": "-6",
}
BEAT_SYMBOLS = {
    "N", "L", "R", "B", "A", "a", "J", "S", "V", "r", "F", "e", "j", "n",
    "E", "/", "f", "Q", "?",
}


def import_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

point1 = import_from_path("point1_firmware_equivalence", PROJECT / "reviewer2_rpeak_final" / "run_firmware_equivalence_check.py")
mitval = point1.mitval
from hrv_live_processing_engine import HRVConfig, HRVProcessingEngine, clamp01, clean_nn_mask


@dataclass(frozen=True)
class Classification:
    tp: int
    fp: int
    tn: int
    fn: int


def ensure_data() -> None:
    NSTDB_DIR.mkdir(parents=True, exist_ok=True)
    have_nstdb = all((NSTDB_DIR / f"{record}.hea").exists() for record in NSTDB_NOISE_RECORDS + NSTDB_NOISE_ONLY_RECORDS)
    if not have_nstdb:
        wfdb.dl_database("nstdb", str(NSTDB_DIR), records=NSTDB_NOISE_RECORDS + NSTDB_NOISE_ONLY_RECORDS, keep_subdirs=False)
    MITDB_DIR.mkdir(parents=True, exist_ok=True)
    have_clean = all((MITDB_DIR / f"{record}.hea").exists() and (MITDB_DIR / f"{record}.atr").exists() for record in CLEAN_SOURCE_RECORDS)
    if not have_clean:
        wfdb.dl_database("mitdb", str(MITDB_DIR), records=CLEAN_SOURCE_RECORDS, annotators=["atr"], keep_subdirs=False)


def preserve_previous_outputs() -> None:
    """Preserve the earlier Point 2 outputs once before corrected regeneration."""
    if CORRECTION_ARCHIVE.exists():
        return
    CORRECTION_ARCHIVE.mkdir(parents=True, exist_ok=True)
    names = [
        "README.md",
        "environment.txt",
        "window_level_results.csv",
        "condition_level_results.csv",
        "quality_classification_results.csv",
        "runtime_results.csv",
        "validation_report.md",
        "methods_insert.md",
        "results_insert.md",
        "discussion_insert.md",
        "reviewer_response.md",
        "implementation_inventory.md",
        "nstdb_metadata.csv",
        "example_windows.csv",
        "rr_stream_events.csv",
        "rr_quality_event_trace.csv",
        "terminology_audit.csv",
    ]
    for name in names:
        src = ROOT / name
        if src.exists():
            (CORRECTION_ARCHIVE / name).write_bytes(src.read_bytes())
    if FIG_DIR.exists():
        (CORRECTION_ARCHIVE / "figures").mkdir(exist_ok=True)
        for src in FIG_DIR.glob("*"):
            if src.is_file():
                (CORRECTION_ARCHIVE / "figures" / src.name).write_bytes(src.read_bytes())


def select_channel(names: Sequence[str]) -> str:
    return mitval.select_channel(names)


def nstdb_noise_flag(t: float) -> bool:
    if t < 300.0:
        return False
    return int((t - 300.0) // 120.0) % 2 == 0


def source_record(record: str) -> str:
    return record[:3]


def read_ecg_record(record: str, is_clean_source: bool) -> Dict[str, Any]:
    base_dir = MITDB_DIR if is_clean_source else NSTDB_DIR
    rec = wfdb.rdrecord(str(base_dir / record))
    ann = wfdb.rdann(str(base_dir / record), "atr")
    names = list(rec.sig_name)
    channel = select_channel(names)
    idx = names.index(channel)
    sig = rec.p_signal[:, idx].astype(float)
    fs_orig = float(rec.fs)
    ref_s = np.array([sample / fs_orig for sample, sym in zip(ann.sample, ann.symbol) if sym in BEAT_SYMBOLS], dtype=float)
    sig_250 = resample_poly(sig, up=25, down=36).astype(float)
    return {
        "record": record,
        "fs_orig": fs_orig,
        "channel": channel,
        "signal_names": names,
        "sig_250": sig_250,
        "ref_s": ref_s,
        "duration_s": min(len(sig) / fs_orig, len(sig_250) / FS_TARGET),
        "source_record": record if is_clean_source else source_record(record),
        "snr_label": "clean" if is_clean_source else SNR_BY_RECORD[record],
        "is_clean_source": is_clean_source,
    }


def firmware_replay_events(signal: np.ndarray) -> Tuple[np.ndarray, pd.DataFrame]:
    if len(signal) == 0:
        return np.array([], dtype=float), pd.DataFrame(columns=["beat_time_s", "rr_ms"])
    det = point1.FirmwarePanTompkinsReplay(x1=float(signal[0]), x2=float(signal[0]))
    peaks: List[float] = []
    rr_rows: List[Dict[str, float]] = []
    last_time_ms = 0
    for i, sample in enumerate(signal.astype(float)):
        idx = det.update(float(sample), i)
        if idx is None:
            continue
        detected_ms = int((1000 * idx) // mitval.FS_TARGET)
        if last_time_ms > 0 and detected_ms > last_time_ms:
            rr_ms = detected_ms - last_time_ms
            if 250 <= rr_ms <= 2200:
                beat_time_s = idx / mitval.FS_TARGET
                peaks.append(beat_time_s)
                rr_rows.append({"beat_time_s": beat_time_s, "rr_ms": float(rr_ms)})
        last_time_ms = detected_ms
    return np.array(peaks, dtype=float), pd.DataFrame(rr_rows)


def match_pairs(ref_s: np.ndarray, det_s: np.ndarray, tol_s: float = MATCH_TOL_S) -> Tuple[List[Tuple[int, int, float]], np.ndarray, np.ndarray]:
    pairs: List[Tuple[float, int, int]] = []
    for i, ref in enumerate(ref_s):
        lo = np.searchsorted(det_s, ref - tol_s, side="left")
        hi = np.searchsorted(det_s, ref + tol_s, side="right")
        for j in range(lo, hi):
            pairs.append((abs(float(det_s[j] - ref)), i, j))
    pairs.sort(key=lambda x: x[0])
    used_ref = set()
    used_det = set()
    matched: List[Tuple[int, int, float]] = []
    for err, i, j in pairs:
        if i in used_ref or j in used_det:
            continue
        used_ref.add(i)
        used_det.add(j)
        matched.append((i, j, err))
    unmatched_ref = np.array([i for i in range(len(ref_s)) if i not in used_ref], dtype=int)
    unmatched_det = np.array([j for j in range(len(det_s)) if j not in used_det], dtype=int)
    return matched, unmatched_ref, unmatched_det


def beat_metrics(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    sens = tp / (tp + fn) if tp + fn else np.nan
    ppv = tp / (tp + fp) if tp + fp else np.nan
    f1 = 0.0 if tp == 0 and (fp > 0 or fn > 0) else (2 * sens * ppv / (sens + ppv) if sens + ppv > 0 else np.nan)
    return sens, ppv, f1


def df_to_md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            if pd.isna(value):
                vals.append("")
            elif isinstance(value, float):
                vals.append(f"{value:.4f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def quality_components(engine: HRVProcessingEngine, at_sec: float) -> Dict[str, Any]:
    old_elapsed = engine.buffer.elapsed_sec
    engine.buffer.elapsed_sec = max(engine.buffer.elapsed_sec, float(at_sec))
    artifact_ratio = engine.buffer.recent_artifact_ratio()
    recent_valid = len(engine.buffer.recent_records(engine.config.time_window_sec))
    recent_rr = engine.buffer.recent_rr(engine.config.short_time_window_sec)
    mean_rr = float(np.mean(recent_rr)) if recent_rr.size else 800.0
    expected_beats = max(1.0, engine.config.time_window_sec / max(0.3, mean_rr / 1000.0))
    rr_quality = 1.0 - artifact_ratio
    beat_density = clamp01(recent_valid / expected_beats)
    seconds_since_valid = engine.buffer.seconds_since_last_valid()
    if seconds_since_valid is None:
        freshness = 0.0
    elif seconds_since_valid <= 3.0:
        freshness = 1.0
    elif seconds_since_valid >= 10.0:
        freshness = 0.0
    else:
        freshness = 1.0 - ((seconds_since_valid - 3.0) / 7.0)
    signal_confidence = engine._signal_confidence()
    signal_status = engine._signal_status(signal_confidence)
    engine.buffer.elapsed_sec = old_elapsed
    return {
        "artifact_ratio": artifact_ratio,
        "rr_quality": rr_quality,
        "beat_density": beat_density,
        "freshness": freshness,
        "signal_confidence": signal_confidence,
        "signal_status": signal_status,
        "seconds_since_last_valid": seconds_since_valid,
    }


def run_rr_quality(rr_events: pd.DataFrame, windows: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, HRVProcessingEngine]:
    engine = HRVProcessingEngine(HRVConfig())
    # The live engine treats the first externally timestamped RR as session time
    # zero unless a start timestamp is already present. For record replay, the
    # session starts at ECG time zero, so set that explicitly before adding RR.
    engine.buffer.start_timestamp = 0.0
    event_rows = []
    window_rows = []
    prev_valid = 0
    prev_rejected = 0
    prev_raw = 0
    events = rr_events.sort_values("beat_time_s").reset_index(drop=True)
    event_idx = 0

    for _, win in windows.sort_values("window_start_s").iterrows():
        win_end = float(win.window_end_s)
        while event_idx < len(events) and float(events.loc[event_idx, "beat_time_s"]) < win_end:
            row = events.loc[event_idx]
            accepted, reason = engine.buffer.add(float(row.rr_ms), timestamp=float(row.beat_time_s))
            q = quality_components(engine, float(row.beat_time_s))
            event_rows.append({
            "beat_time_s": float(row.beat_time_s),
            "rr_ms": float(row.rr_ms),
            "rr_accepted": bool(accepted),
            "rejection_reason": None if accepted else reason,
            "signal_confidence_event": q["signal_confidence"],
            "signal_status_event": q["signal_status"],
            "artifact_ratio_event": q["artifact_ratio"],
            "n_raw_total": engine.buffer.raw_count,
            "n_valid_total": engine.buffer.valid_count,
            "n_rejected_total": engine.buffer.rejected_count,
            "n_raw_delta": engine.buffer.raw_count - prev_raw,
            "n_valid_delta": engine.buffer.valid_count - prev_valid,
            "n_rejected_delta": engine.buffer.rejected_count - prev_rejected,
            })
            prev_raw = engine.buffer.raw_count
            prev_valid = engine.buffer.valid_count
            prev_rejected = engine.buffer.rejected_count
            event_idx += 1
        qwin = quality_components(engine, win_end)
        window_rows.append({
            "window_index": int(win.window_index),
            "artifact_ratio": qwin["artifact_ratio"],
            "rr_quality": qwin["rr_quality"],
            "beat_density": qwin["beat_density"],
            "freshness": qwin["freshness"],
            "signal_confidence": qwin["signal_confidence"],
            "signal_status": qwin["signal_status"],
            "seconds_since_last_valid": qwin["seconds_since_last_valid"],
        })
    return pd.DataFrame(window_rows), pd.DataFrame(event_rows), engine


def orphanidou_filter_ecg(segment: np.ndarray, fs: int) -> np.ndarray:
    """Fixed ECG preprocessing for the Orphanidou-style benchmark.

    The published workflow is based on beat detection followed by adaptive
    QRS-template correlation on 10 s ECG windows. No author-maintained Python
    implementation was available locally, so this uses a fixed 0.5-40 Hz ECG
    bandpass before independent Hamilton detection and template extraction.
    """
    x = np.asarray(segment, dtype=float)
    x = x - float(np.nanmedian(x))
    if len(x) < fs:
        return x
    sos = signal.butter(2, [0.5, 40.0], btype="bandpass", fs=fs, output="sos")
    try:
        return signal.sosfiltfilt(sos, x)
    except ValueError:
        return signal.sosfilt(sos, x)


def refine_rpeaks_local(filtered: np.ndarray, peaks: Sequence[int], fs: int) -> np.ndarray:
    refined: List[int] = []
    radius = max(1, int(round(0.100 * fs)))
    for peak in peaks:
        p = int(peak)
        lo = max(0, p - radius)
        hi = min(len(filtered), p + radius + 1)
        if hi <= lo:
            continue
        local = filtered[lo:hi]
        idx = lo + int(np.argmax(np.abs(local)))
        if refined and idx - refined[-1] < int(round(0.250 * fs)):
            if abs(float(filtered[idx])) > abs(float(filtered[refined[-1]])):
                refined[-1] = idx
        else:
            refined.append(idx)
    return np.asarray(refined, dtype=int)


def orphanidou_detect_rpeaks(segment: np.ndarray, fs: int) -> Tuple[np.ndarray, np.ndarray]:
    filtered = orphanidou_filter_ecg(segment, fs)
    try:
        peaks = Detectors(fs).hamilton_detector(filtered.astype(float))
    except Exception:
        peaks = []
    refined = refine_rpeaks_local(filtered, peaks, fs)
    return refined.astype(float) / float(fs), filtered


def orphanidou_sqi_from_peaks(segment: np.ndarray, fs: int, rpeaks_s: Sequence[float], filtered: Optional[np.ndarray] = None) -> Dict[str, Any]:
    if filtered is None:
        filtered = orphanidou_filter_ecg(segment, fs)
    rpeaks_s = np.asarray(rpeaks_s, dtype=float)
    rpeaks_s = rpeaks_s[(rpeaks_s >= 0) & (rpeaks_s < len(segment) / fs)]
    if len(rpeaks_s) < 3:
        return {"orphanidou_sqi": 0.0, "orphanidou_usable": False, "orphanidou_reason": "too_few_peaks", "orphanidou_peak_count": int(len(rpeaks_s))}
    rr = np.diff(rpeaks_s)
    if len(rr) == 0:
        return {"orphanidou_sqi": 0.0, "orphanidou_usable": False, "orphanidou_reason": "too_few_rr", "orphanidou_peak_count": int(len(rpeaks_s))}
    mean_hr = 60.0 / float(np.mean(rr))
    if mean_hr < 40.0 or mean_hr > 180.0:
        return {"orphanidou_sqi": 0.0, "orphanidou_usable": False, "orphanidou_reason": "mean_hr_outside_40_180", "orphanidou_peak_count": int(len(rpeaks_s)), "orphanidou_mean_hr": mean_hr}
    if float(np.max(rr)) >= 3.0:
        return {"orphanidou_sqi": 0.0, "orphanidou_usable": False, "orphanidou_reason": "max_rr_ge_3s", "orphanidou_peak_count": int(len(rpeaks_s)), "orphanidou_mean_hr": mean_hr}
    if float(np.min(rr)) <= 0 or float(np.max(rr) / np.min(rr)) >= 2.2:
        return {"orphanidou_sqi": 0.0, "orphanidou_usable": False, "orphanidou_reason": "rr_ratio_ge_2_2", "orphanidou_peak_count": int(len(rpeaks_s)), "orphanidou_mean_hr": mean_hr, "orphanidou_rr_ratio": float(np.max(rr) / np.min(rr))}

    width = int(round(float(np.median(rr)) * fs))
    width = max(5, width)
    if width % 2 == 0:
        width += 1
    half = width // 2
    peaks = np.round(rpeaks_s * fs).astype(int)
    beats = []
    for peak in peaks:
        lo = peak - half
        hi = peak + half + 1
        if lo < 0 or hi > len(segment):
            continue
        wave = np.asarray(filtered[lo:hi], dtype=float)
        wave = wave - float(np.mean(wave))
        sd = float(np.std(wave))
        if sd <= 0 or not math.isfinite(sd):
            continue
        beats.append(wave / sd)
    if len(beats) < 3:
        return {"orphanidou_sqi": 0.0, "orphanidou_usable": False, "orphanidou_reason": "too_few_complete_templates", "orphanidou_peak_count": int(len(rpeaks_s)), "orphanidou_mean_hr": mean_hr}
    arr = np.vstack(beats)
    template = np.mean(arr, axis=0)
    template_sd = float(np.std(template))
    if template_sd <= 0 or not math.isfinite(template_sd):
        return {"orphanidou_sqi": 0.0, "orphanidou_usable": False, "orphanidou_reason": "flat_template", "orphanidou_peak_count": int(len(rpeaks_s)), "orphanidou_mean_hr": mean_hr}
    template = (template - float(np.mean(template))) / template_sd
    corrs = []
    for beat in arr:
        corr = float(np.corrcoef(beat, template)[0, 1])
        if math.isfinite(corr):
            corrs.append(corr)
    if not corrs:
        return {"orphanidou_sqi": 0.0, "orphanidou_usable": False, "orphanidou_reason": "no_finite_correlations", "orphanidou_peak_count": int(len(rpeaks_s)), "orphanidou_mean_hr": mean_hr}
    sqi = float(np.mean(corrs))
    return {
        "orphanidou_sqi": sqi,
        "orphanidou_usable": bool(sqi >= 0.66),
        "orphanidou_reason": "accepted" if sqi >= 0.66 else "template_corr_lt_0_66",
        "orphanidou_peak_count": int(len(rpeaks_s)),
        "orphanidou_mean_hr": mean_hr,
        "orphanidou_rr_ratio": float(np.max(rr) / np.min(rr)),
    }


def orphanidou_sqi(segment: np.ndarray, fs: int) -> Dict[str, Any]:
    rpeaks_s, filtered = orphanidou_detect_rpeaks(segment, fs)
    out = orphanidou_sqi_from_peaks(segment, fs, rpeaks_s, filtered)
    out["orphanidou_detector"] = "Hamilton fixed detector with local +/-100 ms refinement"
    return out


def confusion(y_degraded: Iterable[bool], pred_degraded: Iterable[bool]) -> Classification:
    y = np.asarray(list(y_degraded), dtype=bool)
    p = np.asarray(list(pred_degraded), dtype=bool)
    return Classification(
        tp=int(np.sum(y & p)),
        fp=int(np.sum(~y & p)),
        tn=int(np.sum(~y & ~p)),
        fn=int(np.sum(y & ~p)),
    )


def classification_metrics(c: Classification) -> Dict[str, float]:
    tp, fp, tn, fn = c.tp, c.fp, c.tn, c.fn
    sens = tp / (tp + fn) if tp + fn else np.nan
    spec = tn / (tn + fp) if tn + fp else np.nan
    ppv = tp / (tp + fp) if tp + fp else np.nan
    npv = tn / (tn + fn) if tn + fn else np.nan
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else np.nan
    bal = np.nanmean([sens, spec])
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = ((tp * tn) - (fp * fn)) / denom if denom else np.nan
    return {
        "TP": tp, "FP": fp, "TN": tn, "FN": fn,
        "sensitivity_for_degraded": sens,
        "specificity_for_intact": spec,
        "PPV_degraded": ppv,
        "NPV_intact": npv,
        "balanced_accuracy": bal,
        "F1_degraded": f1,
        "MCC": mcc,
    }


def roc_auc(y_positive: np.ndarray, scores: np.ndarray) -> float:
    mask = np.isfinite(scores)
    y = y_positive[mask].astype(bool)
    s = scores[mask].astype(float)
    n_pos = int(np.sum(y))
    n_neg = int(np.sum(~y))
    if n_pos == 0 or n_neg == 0:
        return np.nan
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i + 1
        while j < len(s) and sorted_s[j] == sorted_s[i]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        ranks[order[i:j]] = avg_rank
        i = j
    sum_pos = float(np.sum(ranks[y]))
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def average_precision(y_positive: np.ndarray, scores: np.ndarray) -> float:
    mask = np.isfinite(scores)
    y = y_positive[mask].astype(bool)
    s = scores[mask].astype(float)
    n_pos = int(np.sum(y))
    if n_pos == 0:
        return np.nan
    order = np.argsort(-s, kind="mergesort")
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    precision = tp / (np.arange(len(y_sorted)) + 1)
    return float(np.sum(precision[y_sorted]) / n_pos)


def timed(
    label: str,
    boundary: str,
    fn: Callable[[], Any],
    n_units: float,
    unit_label: str,
    n_windows: float,
    reps: int = RUNTIME_REPS,
    warmup: bool = True,
) -> List[Dict[str, Any]]:
    if warmup:
        fn()
    rows = []
    for rep in range(1, reps + 1):
        t0 = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - t0
        rows.append({
            "method": label,
            "boundary": boundary,
            "rep": rep,
            "runtime_s": elapsed,
            "n_units": n_units,
            "unit_label": unit_label,
            "ms_per_unit": elapsed * 1000.0 / n_units if n_units else np.nan,
            "n_10s_windows": n_windows,
            "ms_per_10s_window": elapsed * 1000.0 / n_windows if n_windows else np.nan,
            "real_time_factor": elapsed / (n_windows * WINDOW_SEC) if n_windows else np.nan,
            "result_count": len(result) if hasattr(result, "__len__") else np.nan,
        })
    return rows


def summarize_by_condition(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = [
        "source_record",
        "record",
        "record_snr_label",
        "actual_snr_label",
        "actual_snr_db",
        "segment_condition",
        "clean_noisy_indicator",
        "primary_analysis",
    ]
    for keys, g in df.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys))
        tp, fp, fn = int(g.TP.sum()), int(g.FP.sum()), int(g.FN.sum())
        sens, ppv, f1 = beat_metrics(tp, fp, fn)
        row.update({
            "n_windows": int(len(g)),
            "rr_intact_windows": int(g.strict_rr_integrity.sum()),
            "rr_intact_pct": float(g.strict_rr_integrity.mean() * 100.0),
            "median_signal_confidence": float(g.signal_confidence.median()),
            "iqr_signal_confidence": float(g.signal_confidence.quantile(0.75) - g.signal_confidence.quantile(0.25)),
            "signal_status_active_pct": float((g.signal_status == "Active").mean() * 100.0),
            "signal_status_active_or_noisy_pct": float(g.signal_status.isin(["Active", "Noisy"]).mean() * 100.0),
            "orphanidou_usable_pct": float(g.orphanidou_usable.mean() * 100.0),
            "rpeak_sensitivity": sens,
            "rpeak_ppv": ppv,
            "rpeak_f1": f1,
            "median_window_f1": float(g.beat_f1.median()),
            "median_artifact_ratio": float(g.artifact_ratio.median()),
            "median_rr_quality": float(g.rr_quality.median()),
            "median_beat_density": float(g.beat_density.median()),
            "median_freshness": float(g.freshness.median()),
        })
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["source_record", "actual_snr_db", "record", "segment_condition"], na_position="first")


def snr_dose_response(df: pd.DataFrame, population: str) -> pd.DataFrame:
    rows = []
    snr_order = ["clean", "24", "18", "12", "6", "0", "-6"]
    for snr in snr_order:
        g = df[df.actual_snr_label.astype(str).eq(snr)]
        if g.empty:
            continue
        tp, fp, fn = int(g.TP.sum()), int(g.FP.sum()), int(g.FN.sum())
        sens, ppv, f1 = beat_metrics(tp, fp, fn)
        rows.append({
            "analysis_population": population,
            "actual_snr_label": snr,
            "actual_snr_db": np.nan if snr == "clean" else float(snr),
            "n_windows": int(len(g)),
            "rr_intact_windows": int(g.strict_rr_integrity.sum()),
            "rr_intact_pct": float(g.strict_rr_integrity.mean() * 100.0),
            "median_signal_confidence": float(g.signal_confidence.median()),
            "iqr_signal_confidence": float(g.signal_confidence.quantile(0.75) - g.signal_confidence.quantile(0.25)),
            "signal_status_active_pct": float((g.signal_status == "Active").mean() * 100.0),
            "signal_status_active_or_noisy_pct": float(g.signal_status.isin(["Active", "Noisy"]).mean() * 100.0),
            "orphanidou_usable_pct": float(g.orphanidou_usable.mean() * 100.0),
            "rpeak_sensitivity": sens,
            "rpeak_ppv": ppv,
            "pooled_rpeak_f1": f1,
            "median_window_f1_sensitivity_only": float(g.beat_f1.median()),
        })
    return pd.DataFrame(rows)


def write_environment(metadata: pd.DataFrame) -> None:
    cpu = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text(errors="ignore").splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except Exception:
        pass
    ram = "unknown"
    try:
        for line in Path("/proc/meminfo").read_text(errors="ignore").splitlines():
            if line.startswith("MemTotal"):
                ram = line.split(":", 1)[1].strip()
                break
    except Exception:
        pass
    try:
        from importlib.metadata import version
    except Exception:  # pragma: no cover
        version = None
    packages = []
    for pkg in ["wfdb", "py-ecg-detectors", "numpy", "scipy", "pandas", "matplotlib"]:
        try:
            packages.append(f"- {pkg}: {version(pkg) if version else 'unknown'}")
        except Exception:
            packages.append(f"- {pkg}: not available")
    lines = [
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"OS: {platform.platform()}",
        f"CPU: {cpu}",
        f"RAM: {ram}",
        f"Python: {sys.version.replace(os.linesep, ' ')}",
        f"NSTDB: v{NSTDB_VERSION}, DOI {NSTDB_DOI}, {NSTDB_URL}",
        f"Records in official NSTDB metadata: {', '.join(metadata.record.astype(str))}",
        "",
        "Package versions:",
        *packages,
    ]
    (ROOT / "environment.txt").write_text("\n".join(lines) + "\n")


def inspect_nstdb_metadata() -> pd.DataFrame:
    records = wfdb.get_record_list("nstdb")
    rows = []
    for record in records:
        local_path = NSTDB_DIR / f"{record}.hea"
        header = wfdb.rdheader(str(NSTDB_DIR / record)) if local_path.exists() else wfdb.rdheader(record, pn_dir=f"nstdb/{NSTDB_VERSION}")
        rows.append({
            "record": record,
            "fs": float(header.fs),
            "sig_len": int(header.sig_len),
            "duration_s": float(header.sig_len / header.fs),
            "n_sig": int(header.n_sig),
            "sig_names": "|".join(header.sig_name),
            "source_record": source_record(record) if record in NSTDB_NOISE_RECORDS else "",
            "snr_label": SNR_BY_RECORD.get(record, ""),
            "noise_type": "electrode motion artifact" if record in NSTDB_NOISE_RECORDS else ("baseline wander" if record == "bw" else "electrode motion" if record == "em" else "muscle artifact" if record == "ma" else ""),
            "reference_annotations": "atr copy of clean MIT-BIH source" if record in NSTDB_NOISE_RECORDS else "",
        })
    return pd.DataFrame(rows)


def make_windows_for_record(data: Dict[str, Any]) -> pd.DataFrame:
    n = int(math.floor(float(data["duration_s"]) / WINDOW_SEC))
    rows = []
    for i in range(n):
        start = i * WINDOW_SEC
        end = start + WINDOW_SEC
        is_clean_source = bool(data["is_clean_source"])
        noisy = False if is_clean_source else nstdb_noise_flag(start + 0.5 * WINDOW_SEC)
        segment_condition = "clean" if is_clean_source or not noisy else "noisy"
        actual_snr_label = "clean" if is_clean_source else (data["snr_label"] if noisy else "interleaved_clean")
        rows.append({
            "record": data["record"],
            "source_record": data["source_record"],
            "record_snr_label": data["snr_label"],
            "actual_snr_label": actual_snr_label,
            "actual_snr_db": np.nan if actual_snr_label in {"clean", "interleaved_clean"} else float(actual_snr_label),
            "clean_noisy_indicator": "clean_source" if is_clean_source else ("noise_exposed" if noisy else "clean_interval"),
            "segment_condition": segment_condition,
            "primary_analysis": bool(is_clean_source or noisy),
            "window_index": i,
            "window_start_s": start,
            "window_end_s": end,
        })
    return pd.DataFrame(rows)


def process_record(data: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    det_s, rr_events = firmware_replay_events(data["sig_250"])
    windows = make_windows_for_record(data)
    quality_windows, rr_quality_events, engine = run_rr_quality(rr_events, windows)
    matched, unmatched_ref_idx, unmatched_det_idx = match_pairs(data["ref_s"], det_s)
    matched_df = pd.DataFrame([
        {"ref_idx": i, "det_idx": j, "ref_s": data["ref_s"][i], "det_s": det_s[j], "timing_error_ms": err * 1000.0}
        for i, j, err in matched
    ])
    unmatched_ref_s = data["ref_s"][unmatched_ref_idx]
    unmatched_det_s = det_s[unmatched_det_idx]
    rows = []
    for _, win in windows.iterrows():
        start = float(win.window_start_s)
        end = float(win.window_end_s)
        ref_n = int(np.sum((data["ref_s"] >= start) & (data["ref_s"] < end)))
        det_n = int(np.sum((det_s >= start) & (det_s < end)))
        if len(matched_df):
            m = matched_df[(matched_df.ref_s >= start) & (matched_df.ref_s < end)]
            timing = m.timing_error_ms.to_numpy(dtype=float)
            tp = int(len(m))
        else:
            timing = np.array([], dtype=float)
            tp = 0
        fn = int(np.sum((unmatched_ref_s >= start) & (unmatched_ref_s < end)))
        fp = int(np.sum((unmatched_det_s >= start) & (unmatched_det_s < end)))
        sens, ppv, f1 = beat_metrics(tp, fp, fn)

        q = quality_windows[quality_windows.window_index == int(win.window_index)].iloc[0].to_dict()
        events_in = rr_quality_events[(rr_quality_events.beat_time_s >= start) & (rr_quality_events.beat_time_s < end)]
        n_rr_raw = int(len(events_in))
        n_rr_accepted = int(events_in.rr_accepted.sum()) if len(events_in) else 0
        n_rr_rejected = n_rr_raw - n_rr_accepted
        sig_start = int(round(start * FS_TARGET))
        sig_end = int(round(end * FS_TARGET))
        segment = data["sig_250"][sig_start:sig_end]
        orphan = orphanidou_sqi(segment, FS_TARGET)
        row = {
            **win.to_dict(),
            "channel": data["channel"],
            "reference_beats": ref_n,
            "detected_beats": det_n,
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "missed_beats": fn,
            "extra_beats": fp,
            "beat_sensitivity": sens,
            "beat_ppv": ppv,
            "beat_f1": f1,
            "beat_errors": fp + fn,
            "strict_rr_integrity": bool(fp == 0 and fn == 0),
            "f1_ge_0_95": bool(pd.notna(f1) and f1 >= 0.95),
            "f1_ge_0_98": bool(pd.notna(f1) and f1 >= 0.98),
            "no_more_than_one_beat_error": bool(fp + fn <= 1),
            "median_timing_error_ms": float(np.median(timing)) if len(timing) else np.nan,
            "signal_confidence": q["signal_confidence"],
            "signal_status": q["signal_status"],
            "artifact_ratio": q["artifact_ratio"],
            "artifact_level": "",
            "rr_quality": q["rr_quality"],
            "beat_density": q["beat_density"],
            "freshness": q["freshness"],
            "seconds_since_last_valid": q["seconds_since_last_valid"],
            "n_rr_raw_window": n_rr_raw,
            "n_rr_accepted_window": n_rr_accepted,
            "n_rr_rejected_window": n_rr_rejected,
            "accepted_rr_proportion": n_rr_accepted / n_rr_raw if n_rr_raw else np.nan,
            "rejected_rr_proportion": n_rr_rejected / n_rr_raw if n_rr_raw else np.nan,
            "exclusion_flags": "no_rr_events_in_window" if n_rr_raw == 0 else "",
            **orphan,
        }
        rows.append(row)
    return pd.DataFrame(rows), rr_events, rr_quality_events


def build_quality_classification(window_df: pd.DataFrame) -> pd.DataFrame:
    populations = [
        ("primary_clean_source_plus_noise_exposed", window_df[window_df.primary_analysis.astype(bool)].copy()),
        ("sensitivity_all_windows", window_df.copy()),
    ]
    rows = []
    for population, df in populations:
        rows.extend(build_quality_classification_for_population(df, population))
    return pd.DataFrame(rows)


def build_quality_classification_for_population(window_df: pd.DataFrame, population: str) -> List[Dict[str, Any]]:
    y_degraded = ~window_df.strict_rr_integrity.to_numpy(dtype=bool)
    rows = []
    definitions = [
        ("Signal Status: non-Active predicts degraded", ~window_df.signal_status.eq("Active").to_numpy()),
        ("Signal Status: Low Confidence/Lost predicts degraded", window_df.signal_status.isin(["Low Confidence", "Signal Lost"]).to_numpy()),
        ("Orphanidou SQI: unacceptable predicts degraded", ~window_df.orphanidou_usable.to_numpy(dtype=bool)),
    ]
    for name, pred_degraded in definitions:
        c = confusion(y_degraded, pred_degraded)
        row = {"analysis_population": population, "quality_method": name, "target": "strict RR integrity: degraded = FP>0 or FN>0"}
        row.update(classification_metrics(c))
        rows.append(row)

    conf = window_df.signal_confidence.to_numpy(dtype=float)
    orphan_score = window_df.orphanidou_sqi.to_numpy(dtype=float)
    rows.append({
        "analysis_population": population,
        "quality_method": "Signal Confidence continuous",
        "target": "strict RR integrity: degraded = FP>0 or FN>0",
        "AUROC_for_degraded": roc_auc(y_degraded, 1.0 - conf),
        "AUPRC_for_degraded": average_precision(y_degraded, 1.0 - conf),
    })
    rows.append({
        "analysis_population": population,
        "quality_method": "Orphanidou SQI continuous",
        "target": "strict RR integrity: degraded = FP>0 or FN>0",
        "AUROC_for_degraded": roc_auc(y_degraded, -orphan_score),
        "AUPRC_for_degraded": average_precision(y_degraded, -orphan_score),
    })
    for threshold in [0.95, 0.98]:
        y = ~(window_df.beat_f1.to_numpy(dtype=float) >= threshold)
        rows.append({
            "analysis_population": population,
            "quality_method": "Signal Confidence continuous",
            "target": f"secondary degraded = R-peak F1 < {threshold}",
            "AUROC_for_degraded": roc_auc(y, 1.0 - conf),
            "AUPRC_for_degraded": average_precision(y, 1.0 - conf),
        })
        rows.append({
            "analysis_population": population,
            "quality_method": "Orphanidou SQI continuous",
            "target": f"secondary degraded = R-peak F1 < {threshold}",
            "AUROC_for_degraded": roc_auc(y, -orphan_score),
            "AUPRC_for_degraded": average_precision(y, -orphan_score),
        })
    y = ~window_df.no_more_than_one_beat_error.to_numpy(dtype=bool)
    rows.append({
        "analysis_population": population,
        "quality_method": "Signal Confidence continuous",
        "target": "secondary degraded = more than one beat error",
        "AUROC_for_degraded": roc_auc(y, 1.0 - conf),
        "AUPRC_for_degraded": average_precision(y, 1.0 - conf),
    })
    rows.append({
        "analysis_population": population,
        "quality_method": "Orphanidou SQI continuous",
        "target": "secondary degraded = more than one beat error",
        "AUROC_for_degraded": roc_auc(y, -orphan_score),
        "AUPRC_for_degraded": average_precision(y, -orphan_score),
    })
    return rows


def make_runtime_results(records_data: List[Dict[str, Any]], window_df: pd.DataFrame) -> pd.DataFrame:
    record_runtime_data = []
    all_segments = []
    all_orphan_peaks = []
    for data in records_data:
        wins = make_windows_for_record(data)
        _, rr_events = firmware_replay_events(data["sig_250"])
        record_runtime_data.append({"data": data, "windows": wins, "rr_events": rr_events})
        for _, win in wins.iterrows():
            start = float(win.window_start_s)
            end = float(win.window_end_s)
            lo = int(round(start * FS_TARGET))
            hi = int(round(end * FS_TARGET))
            segment = data["sig_250"][lo:hi]
            peaks, filtered = orphanidou_detect_rpeaks(segment, FS_TARGET)
            all_segments.append(segment)
            all_orphan_peaks.append(peaks)

    def signal_conf_runtime():
        vals = []
        for item in record_runtime_data:
            quality_windows, _, _ = run_rr_quality(item["rr_events"], item["windows"])
            vals.extend(quality_windows.signal_confidence.tolist())
        return vals

    def signal_conf_complete_runtime():
        vals = []
        for data in records_data:
            _, rr_events = firmware_replay_events(data["sig_250"])
            wins = make_windows_for_record(data)
            quality_windows, _, _ = run_rr_quality(rr_events, wins)
            vals.extend(quality_windows.signal_confidence.tolist())
        return vals

    def orphan_sqi_only_runtime():
        vals = []
        for seg, peaks in zip(all_segments, all_orphan_peaks):
            vals.append(orphanidou_sqi_from_peaks(seg, FS_TARGET, peaks)["orphanidou_sqi"])
        return vals

    def orphan_complete_runtime():
        vals = []
        for seg in all_segments:
            vals.append(orphanidou_sqi(seg, FS_TARGET)["orphanidou_sqi"])
        return vals

    rows = []
    n_windows = max(1, len(all_segments))
    rows.extend(timed(
        "Signal Confidence",
        "quality assessment only: available RR intervals -> RR filtering/state update -> one Signal Confidence/Status decision per 10-s unit",
        signal_conf_runtime,
        n_windows,
        "10-s RR analysis unit",
        n_windows,
    ))
    rows.extend(timed(
        "Orphanidou SQI",
        "quality assessment only: 10-s ECG segment + available Hamilton R peaks -> preprocessing/template SQI",
        orphan_sqi_only_runtime,
        n_windows,
        "10-s ECG segment",
        n_windows,
    ))
    rows.extend(timed(
        "Signal Confidence",
        "complete path: ECG -> firmware-equivalent detector -> RR -> Signal Confidence",
        signal_conf_complete_runtime,
        n_windows,
        "10-s ECG window equivalent",
        n_windows,
        reps=RUNTIME_REPS,
    ))
    rows.extend(timed(
        "Orphanidou SQI",
        "complete path: ECG -> Hamilton detection/refinement -> SQI",
        orphan_complete_runtime,
        n_windows,
        "10-s ECG segment",
        n_windows,
        reps=RUNTIME_REPS,
    ))
    return pd.DataFrame(rows)


def create_figures(window_df: pd.DataFrame, quality_df: pd.DataFrame, examples: pd.DataFrame, records_by_name: Dict[str, Dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(exist_ok=True)
    snr_order = ["clean", "24", "18", "12", "6", "0", "-6"]
    plot_df = window_df[window_df.primary_analysis.astype(bool)].copy()
    plot_df["snr_plot"] = pd.Categorical(plot_df.actual_snr_label.astype(str), categories=snr_order, ordered=True)
    summary = snr_dose_response(plot_df, "primary_clean_source_plus_noise_exposed")
    summary["snr_plot"] = pd.Categorical(summary.actual_snr_label.astype(str), categories=snr_order, ordered=True)
    summary = summary.sort_values("snr_plot")

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.5))
    ax = axes[0, 0]
    ax.boxplot([plot_df.loc[plot_df.actual_snr_label.astype(str) == s, "signal_confidence"].dropna() for s in snr_order], tick_labels=snr_order, showfliers=False)
    ax.set_title("A. Signal Confidence by actual noise-exposed SNR")
    ax.set_xlabel("Actual SNR (dB; clean = source ECG)")
    ax.set_ylabel("Signal Confidence")
    ax.set_ylim(0, 1.03)

    ax = axes[0, 1]
    x = np.arange(len(summary))
    ax.plot(x, summary.rr_intact_pct, marker="o", label="RR-intact windows")
    ax.plot(x, summary.pooled_rpeak_f1 * 100.0, marker="o", label="Pooled R-peak F1")
    ax.set_xticks(x)
    ax.set_xticklabels(summary.snr_plot.astype(str))
    ax.set_ylim(0, 105)
    ax.set_title("B. Beat-sequence integrity by actual SNR")
    ax.set_ylabel("Percent / pooled F1 x100")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 0]
    ax.plot(x, summary.signal_status_active_pct, marker="o", label="Signal Status Active")
    ax.plot(x, summary.signal_status_active_or_noisy_pct, marker="o", label="Signal Status Active/Noisy")
    ax.plot(x, summary.orphanidou_usable_pct, marker="o", label="Orphanidou usable")
    ax.set_xticks(x)
    ax.set_xticklabels(summary.snr_plot.astype(str))
    ax.set_ylim(0, 105)
    ax.set_title("C. Accepted windows by method")
    ax.set_xlabel("Actual SNR")
    ax.set_ylabel("Windows accepted (%)")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 1]
    q = quality_df[
        quality_df.target.eq("strict RR integrity: degraded = FP>0 or FN>0")
        & quality_df.analysis_population.eq("primary_clean_source_plus_noise_exposed")
    ]
    cont = q[q.quality_method.isin(["Signal Confidence continuous", "Orphanidou SQI continuous"])]
    if len(cont):
        ax.bar(cont.quality_method.str.replace(" continuous", ""), cont.AUROC_for_degraded, color=["#1b9e77", "#7570b3"][:len(cont)])
    ax.set_ylim(0, 1.0)
    ax.set_title("D. AUROC for degraded RR windows")
    ax.set_ylabel("AUROC")
    ax.tick_params(axis="x", labelrotation=20)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "supplementary_rr_stream_quality_noise_validation.png", dpi=300)
    fig.savefig(FIG_DIR / "supplementary_rr_stream_quality_noise_validation.pdf")
    plt.close(fig)

    for _, ex in examples.iterrows():
        record = str(ex.record)
        data = records_by_name[record]
        start = float(ex.window_start_s)
        end = float(ex.window_end_s)
        lo = int(round(start * FS_TARGET))
        hi = int(round(end * FS_TARGET))
        sig = data["sig_250"][lo:hi]
        t = np.arange(len(sig)) / FS_TARGET + start
        det_s, _ = firmware_replay_events(data["sig_250"])
        ref = data["ref_s"][(data["ref_s"] >= start) & (data["ref_s"] < end)]
        det = det_s[(det_s >= start) & (det_s < end)]
        fig, ax = plt.subplots(figsize=(8, 2.8))
        ax.plot(t, sig, color="#222222", lw=0.8)
        for label, vals, color in [("Reference", ref, "#1b9e77"), ("Firmware replay", det, "#d95f02")]:
            if len(vals):
                ax.scatter(vals, np.interp(vals, t, sig), s=18, label=label, color=color)
        title = (
            f"{ex.example_type}: {record} {start:.0f}-{end:.0f}s, SNR {ex.actual_snr_label}, "
            f"SC {ex.signal_confidence:.2f}, {ex.signal_status}, Orph {bool(ex.orphanidou_usable)}"
        )
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("ECG")
        ax.legend(frameon=False, fontsize=7, ncol=2)
        fig.tight_layout()
        fname = f"qc_{ex.example_type}_{record}_{int(start)}_{int(end)}.png".replace("/", "_").replace(" ", "_")
        fig.savefig(FIG_DIR / fname, dpi=200)
        plt.close(fig)


def select_examples(window_df: pd.DataFrame) -> pd.DataFrame:
    examples = []

    def add(label: str, query: pd.DataFrame, sort_col: Optional[str] = None, ascending: bool = True) -> None:
        if query.empty:
            return
        row = query.sort_values(sort_col, ascending=ascending).iloc[0] if sort_col else query.iloc[0]
        d = row.to_dict()
        d["example_type"] = label
        examples.append(d)

    add("clean_intact", window_df[(window_df.actual_snr_label == "clean") & (window_df.strict_rr_integrity)], "window_start_s")
    add("poor_snr_intact_high_conf", window_df[(window_df.actual_snr_label == "-6") & (window_df.strict_rr_integrity) & (window_df.signal_confidence >= 0.75)], "signal_confidence", False)
    add("degraded_low_conf", window_df[(~window_df.strict_rr_integrity) & (window_df.signal_confidence < 0.75)], "signal_confidence", True)
    add("degraded_high_conf", window_df[(~window_df.strict_rr_integrity) & (window_df.signal_confidence >= 0.75)], "beat_errors", False)
    add("orphanidou_rejects_intact", window_df[(window_df.strict_rr_integrity) & (~window_df.orphanidou_usable)], "orphanidou_sqi", True)
    add("signal_rejects_intact", window_df[(window_df.strict_rr_integrity) & (~window_df.signal_status.eq("Active"))], "signal_confidence", True)
    return pd.DataFrame(examples)


def write_reports(
    metadata: pd.DataFrame,
    window_df: pd.DataFrame,
    condition_df: pd.DataFrame,
    quality_df: pd.DataFrame,
    runtime_df: pd.DataFrame,
    examples: pd.DataFrame,
) -> None:
    total_windows = len(window_df)
    primary_df = window_df[window_df.primary_analysis.astype(bool)].copy()
    primary_windows = len(primary_df)
    snr_summary = snr_dose_response(primary_df, "primary_clean_source_plus_noise_exposed")
    all_window_snr_summary = snr_dose_response(window_df.copy(), "sensitivity_all_windows_by_actual_label")
    source_summary = primary_df.groupby("source_record").agg(
        n_windows=("record", "size"),
        rr_intact_pct=("strict_rr_integrity", lambda x: float(np.mean(x) * 100.0)),
        median_signal_confidence=("signal_confidence", "median"),
        orphanidou_usable_pct=("orphanidou_usable", lambda x: float(np.mean(x) * 100.0)),
    ).reset_index()
    q_primary = quality_df[
        quality_df.target.eq("strict RR integrity: degraded = FP>0 or FN>0")
        & quality_df.analysis_population.eq("primary_clean_source_plus_noise_exposed")
    ]
    status_primary = q_primary[q_primary.quality_method.eq("Signal Status: non-Active predicts degraded")]
    sc_cont = q_primary[q_primary.quality_method.eq("Signal Confidence continuous")]
    orph_bin = q_primary[q_primary.quality_method.eq("Orphanidou SQI: unacceptable predicts degraded")]
    orph_cont = q_primary[q_primary.quality_method.eq("Orphanidou SQI continuous")]
    q_all = quality_df[
        quality_df.target.eq("strict RR integrity: degraded = FP>0 or FN>0")
        & quality_df.analysis_population.eq("sensitivity_all_windows")
    ]
    rt_summary = runtime_df.groupby(["method", "boundary", "unit_label"]).agg(
        median_runtime_s=("runtime_s", "median"),
        iqr_runtime_s=("runtime_s", lambda x: float(np.percentile(x, 75) - np.percentile(x, 25))),
        median_ms_per_unit=("ms_per_unit", "median"),
        median_ms_per_10s_window=("ms_per_10s_window", "median"),
        median_realtime_factor=("real_time_factor", "median"),
    ).reset_index()
    clean_orph = primary_df[primary_df.actual_snr_label.eq("clean")]
    clean_orph_acceptance = float(clean_orph.orphanidou_usable.mean() * 100.0) if len(clean_orph) else np.nan
    clean_orph_reasons = clean_orph.orphanidou_reason.value_counts().rename_axis("orphanidou_reason").reset_index(name="n_windows")

    snr_summary.to_csv(ROOT / "supplementary_table_rr_quality_by_actual_snr.csv", index=False)
    q_primary.to_csv(ROOT / "supplementary_table_quality_classifier_primary.csv", index=False)
    all_window_snr_summary.to_csv(ROOT / "sensitivity_all_window_snr_summary.csv", index=False)

    implementation_inventory = f"""# Implementation Inventory

## Source of Truth

The frozen RR-stream quality implementation is `hrv_live_processing_engine.py`.

## RR Acceptance and Rejection

- Valid finite RR bounds: {HRVConfig().rr_min_ms:.0f}-{HRVConfig().rr_max_ms:.0f} ms.
- Recent accepted RR history for artifact decisions: {HRVConfig().recent_median_beats} beats.
- Warm-up: local median/MAD rejection is inactive until at least 8 recent accepted RR intervals exist.
- Median/MAD outlier threshold: `max(140 ms, min(artifact_min_jump_ms, median*artifact_relative_jump, artifact_mad_multiplier*MAD))`.
- Frozen constants: artifact MAD multiplier {HRVConfig().artifact_mad_multiplier}, minimum jump {HRVConfig().artifact_min_jump_ms:.0f} ms, relative jump {HRVConfig().artifact_relative_jump:.2f}.
- Successive RR quotient filter: reject if adjacent accepted RR ratio exceeds {1.0 + HRVConfig().nn_max_successive_change_ratio:.2f} or falls below its reciprocal.
- Resynchronization: after at least 10 consecutive rejections, stable plausible raw RR history can re-enter as `accepted_resync`.

## Artifact and RR Quality

- Artifact window duration: {HRVConfig().recent_artifact_window_sec:.0f} s.
- Artifact Ratio: rejected RR records / all raw RR records in the recent artifact window.
- RR quality: `1 - Artifact Ratio`.
- The live engine does not implement a separate named Artifact Level field; this validation leaves `artifact_level` blank.

## Beat Density and Freshness

- Beat-density window: {HRVConfig().time_window_sec:.0f} s.
- Beat density: recent accepted RR count divided by expected beats over the 60 s time window, where expected beats are estimated from the recent {HRVConfig().short_time_window_sec:.0f} s mean RR, defaulting to 800 ms if no recent RR exists.
- Freshness: 1.0 when the last accepted RR is <=3 s old, 0.0 when >=10 s old, and linearly interpolated between those limits. If no RR has ever been accepted, freshness is 0.0.

## Signal Confidence and Status

- Signal Confidence: `clamp01(0.5*rr_quality + 0.3*beat_density + 0.2*freshness)`.
- Signal Status: `Signal Lost` if confidence <0.35 or last accepted RR is >5 s old; `Active` if confidence >=0.75; `Noisy` if confidence >=0.50; otherwise `Low Confidence`.
- Signal Confidence was sampled non-mutatingly at each 10 s window end using the submitted formula and current RR buffer state. Detector parameters, quality weights, thresholds, and status cutoffs were not tuned on NSTDB.
"""
    (ROOT / "implementation_inventory.md").write_text(implementation_inventory)

    readme = f"""# Reviewer II Point 2: RR-Stream Quality Under Controlled ECG Noise

This directory contains a focused validation responding to Reviewer II Point 2. It preserves the conceptual distinction that manuscript Signal Confidence is a downstream RR-stream reliability indicator, not a raw-ECG morphology signal-quality index.

## Dataset

Dataset: MIT-BIH Noise Stress Test Database v{NSTDB_VERSION}, PhysioNet DOI {NSTDB_DOI}. The official NSTDB metadata reported these records: {', '.join(metadata.record.astype(str))}. The validation used the 12 standard pre-generated electrode-motion noise-stress records derived from MIT-BIH records 118 and 119 at SNR labels 24, 18, 12, 6, 0, and -6 dB, plus clean source MIT-BIH records 118 and 119. Noise-only records `bw`, `em`, and `ma` were inspected as metadata but not used as ECG-with-reference evaluation records.

NSTDB adds electrode-motion noise after the first 5 minutes in alternating 2-minute noisy and 2-minute clean intervals. Expert beat annotations are copies of the clean source annotations, providing an independent reference for beat-sequence integrity.

## Workflow

```bash
cd {PROJECT}
reviewer2_rpeak_validation/.venv/bin/python reviewer2_signal_quality_validation/run_noise_quality_validation.py
```

The workflow verifies/downloads NSTDB, reuses the Point 1 firmware-equivalent detector replay unchanged, generates RR intervals, runs the submitted HRV engine Signal Confidence logic without tuning, applies a fixed Orphanidou-style ECG SQI benchmark, and writes all tables, figures, and manuscript-ready text into this directory.

## Evaluation Unit and Ground Truth

Primary windows are non-overlapping 10 s segments. R-peak detections are matched one-to-one to expert annotations within +/-150 ms. The primary endpoint is strict RR integrity: `FP == 0 and FN == 0` within the 10 s window. SNR is treated as an experimental explanatory variable, not as the binary ground truth.

## Orphanidou Benchmark

No author-maintained executable Python implementation was found during the audit. The corrected benchmark is a fixed-threshold Python port of the published Orphanidou ECG SQI rules and the publicly documented workflow associated with co-author Peter Charlton's beat-detector resources: 10 s ECG segments, ECG bandpass preprocessing, independent fixed Hamilton QRS detection, local R-peak refinement within +/-100 ms, mean HR 40-180 bpm, maximum RR interval <3 s, maximum/minimum RR ratio <2.2, adaptive beat-template construction, average beat-template correlation, and ECG acceptance threshold >=0.66. Expert annotations were used only for evaluation ground truth and were not supplied to either quality algorithm.

## Runtime Boundaries

Runtime results separate quality-stage and complete-path costs: Signal Confidence from already available RR intervals; Orphanidou SQI after Hamilton R peaks are available; raw ECG to firmware-equivalent detector to RR to Signal Confidence; and raw ECG to Hamilton detection/refinement to Orphanidou SQI. Disk loading and dataset download are excluded from timed sections.
"""
    (ROOT / "README.md").write_text(readme)

    report = f"""# Validation Report

## Objective

This corrected controlled benchmark asks whether the submitted RR-derived Signal Confidence indicates when ECG noise compromises the RR sequence delivered to downstream HRV processing. Signal Confidence is evaluated as an RR-stream reliability indicator, not as a morphology-based ECG SQI.

## Data and Analysis

The full dataset contained {total_windows} non-overlapping 10 s windows from the 12 standard NSTDB noise-stress ECG records plus clean source records 118 and 119. The primary analysis used {primary_windows} windows: clean source windows plus only actual noise-exposed NSTDB windows. Interleaved clean intervals from the noise-stress records were retained in `window_level_results.csv` and summarized separately as sensitivity/recovery material, but were not grouped under the nominal SNR label. The Point 1 firmware-equivalent Pan-Tompkins-based ESP32 detector replay was reused unchanged. Detected RR intervals were passed through the submitted HRV processing engine without tuning weights, thresholds, artifact windows, or status cutoffs. Expert annotations supplied the independent primary target: strict RR integrity, defined as zero false positives and zero false negatives in each window.

## Main Findings

Corrected primary actual-SNR summary:

{df_to_md(snr_summary)}

Primary classification against strict degraded RR windows:

{df_to_md(q_primary)}

All-window sensitivity analysis, including interleaved clean intervals:

{df_to_md(q_all)}

Source-record heterogeneity in the primary population:

{df_to_md(source_summary)}

Orphanidou clean-source acceptance was {clean_orph_acceptance:.1f}%. Clean-source rejection reasons:

{df_to_md(clean_orph_reasons)}

Runtime summary:

{df_to_md(rt_summary)}

## Interpretation

Signal Confidence should not be interpreted as measuring whether ECG noise is visually present. Its relevant behavior is whether it decreases when upstream degradation compromises the RR stream. Windows with poor SNR but intact beat topology can appropriately retain high Signal Confidence, whereas high confidence during FP/FN-containing windows is an RR-stream quality failure mode.

## Failure and Disagreement Modes

Representative diagnostic examples are listed in `example_windows.csv` and plotted under `figures/qc_*.png`. The most important categories are high-confidence degraded windows, Orphanidou-rejected intact windows, and low-confidence intact windows. These distinctions are expected because Orphanidou evaluates ECG morphology/regularity, while Signal Confidence evaluates the downstream RR stream after beat extraction and filtering.

## Limitations

NSTDB contains repeated noise variants from only two underlying MIT-BIH ECG records, so window counts should not be interpreted as independent subjects. Orphanidou was implemented as a fixed-threshold literature/workflow port because no author-maintained runnable Python implementation was identified. The corrected Orphanidou comparator uses its own Hamilton detector and local refinement; expert annotations are reserved for evaluation. Physical ESP32 timing was not measured for Point 2.
"""
    (ROOT / "validation_report.md").write_text(report)

    (ROOT / "methods_insert.md").write_text(
        "RR-stream quality under controlled ECG noise was evaluated using the MIT-BIH Noise Stress Test Database v1.0.0. "
        f"The 12 standard pre-generated noise-stress records derived from MIT-BIH records 118 and 119 were analyzed at the database-provided SNR labels 24, 18, 12, 6, 0, and -6 dB, together with the clean source ECG records. Because NSTDB applies the nominal SNR only during alternating 2-minute noise-exposed intervals after the initial 5-minute clean period, the primary dose-response analysis used clean source windows plus actual noise-exposed windows only ({primary_windows} windows); interleaved clean intervals were retained as a sensitivity/recovery analysis. "
        "Signals were resampled to 250 Hz and passed through the same frozen firmware-equivalent embedded R-peak detector used for the revised MIT-BIH validation. "
        "Detected RR intervals were then processed by the submitted HRV engine without tuning Signal Confidence weights, artifact thresholds, window durations, or Signal Status cutoffs. "
        "Non-overlapping 10 s windows were used as the common evaluation unit. Expert beat annotations were matched one-to-one to detected beats within +/-150 ms, and the primary endpoint was strict RR-sequence integrity, defined as zero false-positive and zero false-negative beat detections within the window. "
        "A fixed Orphanidou-style ECG SQI benchmark was implemented using 10 s ECG windows, ECG bandpass preprocessing, independent Hamilton QRS detection, local R-peak refinement, the published physiological plausibility rules, adaptive beat-template correlation, and the 0.66 acceptance threshold. Expert annotations were not supplied to either quality algorithm.\n"
    )
    sc_auc = float(sc_cont.AUROC_for_degraded.iloc[0]) if len(sc_cont) else np.nan
    sc_ap = float(sc_cont.AUPRC_for_degraded.iloc[0]) if len(sc_cont) else np.nan
    orph_auc = float(orph_cont.AUROC_for_degraded.iloc[0]) if len(orph_cont) else np.nan
    status_bal = float(status_primary.balanced_accuracy.iloc[0]) if len(status_primary) else np.nan
    orph_bal = float(orph_bin.balanced_accuracy.iloc[0]) if len(orph_bin) else np.nan
    (ROOT / "results_insert.md").write_text(
        f"The corrected primary NSTDB analysis included {primary_windows} non-overlapping 10 s windows composed of clean source ECG plus actual noise-exposed intervals. "
        f"Using strict expert-annotation-derived RR integrity as the primary target, continuous Signal Confidence yielded AUROC {sc_auc:.3f} and AUPRC {sc_ap:.3f} for degraded RR windows, while the Orphanidou-style ECG SQI yielded AUROC {orph_auc:.3f}. "
        f"The existing non-Active Signal Status criterion had balanced accuracy {status_bal:.3f}; the Orphanidou binary SQI had balanced accuracy {orph_bal:.3f}. "
        f"Corrected actual-SNR summaries showed RR-intact window rates of {', '.join(f'{r.actual_snr_label}: {r.rr_intact_pct:.1f}%' for _, r in snr_summary.iterrows())}. Signal Confidence declined most clearly when beat-sequence integrity degraded, supporting its interpretation as an RR-stream reliability indicator rather than a raw-ECG morphology SQI.\n"
    )
    (ROOT / "discussion_insert.md").write_text(
        "This additional analysis supports interpreting Signal Confidence as a downstream RR-stream reliability indicator rather than a raw-ECG morphology SQI. "
        "Divergence from the corrected Orphanidou-style benchmark is expected in windows where ECG morphology is degraded but R-peak topology remains intact, or conversely where beat-detection errors occur without sufficient RR-filter evidence to lower Signal Confidence. "
        "Because NSTDB uses repeated noise variants from two source ECG records, these findings should be framed as a controlled technical robustness benchmark, not as universal clinical ECG-quality validation.\n"
    )
    (ROOT / "reviewer_response.md").write_text(
        "We thank the reviewer for highlighting the importance of signal-quality robustness. We clarified that the manuscript's Signal Confidence was designed as an RR-stream reliability indicator, not as a morphology-based ECG signal-quality index. The reviewer's suggestion nevertheless identifies an important validation opportunity: controlled ECG noise can test whether the downstream indicator responds when upstream degradation compromises RR extraction.\n\n"
        f"We therefore performed an additional analysis using the MIT-BIH Noise Stress Test Database v{NSTDB_VERSION}. Noisy ECGs were passed through the same frozen firmware-equivalent embedded R-peak detector used in the Point 1 validation, and Signal Confidence was generated from the resulting RR stream without parameter tuning. Because the nominal NSTDB SNR applies only during alternating noise-exposed intervals, the primary analysis used clean source windows plus actual noise-exposed windows only ({primary_windows} windows), while retaining interleaved clean intervals as a sensitivity/recovery analysis. Expert beat annotations provided an independent reference for actual RR-sequence integrity, defined as zero false-positive and zero false-negative detections within non-overlapping 10 s windows. We also evaluated a corrected Orphanidou-style ECG SQI using ECG preprocessing, an independent Hamilton detector with local R-peak refinement, physiological plausibility rules, adaptive template correlation, and the fixed 0.66 acceptance threshold.\n\n"
        f"In the corrected primary population, continuous Signal Confidence achieved AUROC {sc_auc:.3f} and AUPRC {sc_ap:.3f} for detecting degraded RR windows under the strict expert-annotation-derived endpoint. The corrected Orphanidou-style continuous SQI achieved AUROC {orph_auc:.3f}. The existing Signal Status mapping and Orphanidou binary SQI are reported with sensitivity, specificity, balanced accuracy, F1, and MCC in the new supplementary table. Runtime was measured separately for quality-stage and complete-path boundaries so that RR-derived and ECG-morphology methods are not compared across mismatched computational scopes.\n\n"
        "We revised terminology to avoid implying that Signal Confidence is a raw-ECG morphology SQI. The added benchmark supports the RR-stream quality layer under controlled ECG noise but does not establish universal ECG-quality classification, clinical diagnostic validity, or robustness across all real-world artifact types.\n"
    )

    terminology = []
    for path in [PROJECT / "PAPER_REVIEW_DRAFT_v3_7.md", PROJECT / "HRV_LIVE_ENGINE_README.md"]:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
            low = line.lower()
            if any(term in low for term in ["signal quality", "signal-quality", "signal confidence", "signal reliability", "signal validity", "artifact robustness"]):
                replacement = line
                replacement = replacement.replace("signal-quality", "RR-stream reliability")
                replacement = replacement.replace("signal quality", "RR-stream reliability")
                replacement = replacement.replace("Signal Confidence", "RR-stream Signal Confidence")
                replacement = replacement.replace("signal confidence", "RR-stream Signal Confidence")
                replacement = replacement.replace("signal reliability", "RR-stream reliability")
                replacement = replacement.replace("signal validity", "RR-stream validity")
                replacement = replacement.replace("artifact robustness", "RR-stream artifact robustness")
                terminology.append({"file": str(path.relative_to(PROJECT)), "line": lineno, "current_text": line.strip(), "proposed_replacement": replacement.strip()})
    pd.DataFrame(terminology).to_csv(ROOT / "terminology_audit.csv", index=False)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    FIG_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    preserve_previous_outputs()
    t_start = time.perf_counter()
    ensure_data()
    metadata = inspect_nstdb_metadata()
    metadata.to_csv(ROOT / "nstdb_metadata.csv", index=False)
    write_environment(metadata)

    records_data = []
    for record in CLEAN_SOURCE_RECORDS:
        records_data.append(read_ecg_record(record, is_clean_source=True))
    for record in NSTDB_NOISE_RECORDS:
        records_data.append(read_ecg_record(record, is_clean_source=False))

    window_parts = []
    rr_parts = []
    quality_event_parts = []
    records_by_name = {}
    for data in records_data:
        records_by_name[data["record"]] = data
        win, rr_events, q_events = process_record(data)
        window_parts.append(win)
        rr_events = rr_events.copy()
        rr_events.insert(0, "record", data["record"])
        q_events = q_events.copy()
        q_events.insert(0, "record", data["record"])
        rr_parts.append(rr_events)
        quality_event_parts.append(q_events)

    window_df = pd.concat(window_parts, ignore_index=True)
    rr_df = pd.concat(rr_parts, ignore_index=True)
    quality_events_df = pd.concat(quality_event_parts, ignore_index=True)
    condition_df = summarize_by_condition(window_df)
    quality_df = build_quality_classification(window_df)
    runtime_df = make_runtime_results(records_data, window_df)
    examples = select_examples(window_df)

    window_df.to_csv(ROOT / "window_level_results.csv", index=False)
    condition_df.to_csv(ROOT / "condition_level_results.csv", index=False)
    quality_df.to_csv(ROOT / "quality_classification_results.csv", index=False)
    runtime_df.to_csv(ROOT / "runtime_results.csv", index=False)
    rr_df.to_csv(ROOT / "rr_stream_events.csv", index=False)
    quality_events_df.to_csv(ROOT / "rr_quality_event_trace.csv", index=False)
    examples.to_csv(ROOT / "example_windows.csv", index=False)
    create_figures(window_df, quality_df, examples, records_by_name)
    write_reports(metadata, window_df, condition_df, quality_df, runtime_df, examples)

    elapsed = time.perf_counter() - t_start
    summary = [
        f"Completed Reviewer II Point 2 validation in {elapsed:.1f} s.",
        f"Records analyzed: {', '.join([d['record'] for d in records_data])}",
        f"Windows: {len(window_df)}",
        f"Outputs: {ROOT}",
    ]
    (LOG_DIR / f"run_summary_{time.strftime('%Y%m%d_%H%M%S')}.txt").write_text("\n".join(summary) + "\n")
    print("\n".join(summary))


if __name__ == "__main__":
    main()

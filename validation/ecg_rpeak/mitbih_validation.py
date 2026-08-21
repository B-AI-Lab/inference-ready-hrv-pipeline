#!/usr/bin/env python3
"""Public MIT-BIH helper functions for ECG-to-RR validation scripts.

This file is intentionally limited to public data loading, channel selection,
one-to-one beat matching, and metric calculation. The evidence-bearing ECG-to-RR
detector implementation lives in `validation/ecg_rpeak/run_ecg_to_rr_benchmark.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.signal import resample_poly

try:
    import wfdb
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: wfdb. Install requirements-validation.txt first.") from exc


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "mitdb"
FS_TARGET = 250
MATCH_TOL_S = 0.150
MITDB_VERSION = "1.0.0"
MITDB_DOI = "10.13026/C2F305"
MITDB_URL = "https://physionet.org/content/mitdb/1.0.0/"
MITDB_RECORDS = [
    "100", "101", "102", "103", "104", "105", "106", "107", "108", "109",
    "111", "112", "113", "114", "115", "116", "117", "118", "119", "121",
    "122", "123", "124", "200", "201", "202", "203", "205", "207", "208",
    "209", "210", "212", "213", "214", "215", "217", "219", "220", "221",
    "222", "223", "228", "230", "231", "232", "233", "234",
]
BEAT_SYMBOLS = {
    "N", "L", "R", "B", "A", "a", "J", "S", "V", "r", "F", "e", "j", "n",
    "E", "/", "f", "Q", "?",
}


def ensure_mitdb(records: Sequence[str] = MITDB_RECORDS) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    have_all = all((DATA_DIR / f"{record}.hea").exists() and (DATA_DIR / f"{record}.atr").exists() for record in records)
    if not have_all:
        wfdb.dl_database("mitdb", str(DATA_DIR), records=list(records), annotators=["atr"], keep_subdirs=False)


def select_channel(names: Sequence[str]) -> str:
    for preferred in ("MLII", "ML2", "II"):
        if preferred in names:
            return preferred
    for name in names:
        upper = name.upper()
        if any(token in upper for token in ("V", "ML", "II", "ECG")):
            return name
    return names[0]


def read_record(record: str) -> Dict[str, object]:
    rec = wfdb.rdrecord(str(DATA_DIR / record))
    ann = wfdb.rdann(str(DATA_DIR / record), "atr")
    fs_orig = float(rec.fs)
    names = list(rec.sig_name)
    channel = select_channel(names)
    idx = names.index(channel)
    sig_mv = rec.p_signal[:, idx].astype(float)
    ref_s = np.array([sample / fs_orig for sample, sym in zip(ann.sample, ann.symbol) if sym in BEAT_SYMBOLS], dtype=float)
    resampled = resample_poly(sig_mv, up=25, down=36)
    duration_orig = len(sig_mv) / fs_orig
    duration_resampled = len(resampled) / FS_TARGET
    return {
        "record": record,
        "fs_orig": fs_orig,
        "channel": channel,
        "signal_names": names,
        "sig_mv": sig_mv,
        "sig_250": resampled.astype(float),
        "ref_s": ref_s,
        "duration_h": duration_orig / 3600.0,
        "duration_orig_s": duration_orig,
        "duration_resampled_s": duration_resampled,
        "ann_symbols": sorted(set(ann.symbol)),
    }


def match_detections(ref_s: np.ndarray, det_s: np.ndarray, tol_s: float = MATCH_TOL_S) -> Tuple[int, int, int, np.ndarray]:
    pairs: List[Tuple[float, int, int]] = []
    det_s = np.sort(np.asarray(det_s, dtype=float))
    ref_s = np.asarray(ref_s, dtype=float)
    for i, r_time in enumerate(ref_s):
        lo = np.searchsorted(det_s, r_time - tol_s, side="left")
        hi = np.searchsorted(det_s, r_time + tol_s, side="right")
        for j in range(lo, hi):
            pairs.append((abs(float(det_s[j] - r_time)), i, j))
    pairs.sort(key=lambda item: item[0])
    used_ref = set()
    used_det = set()
    errors = []
    for err, ref_idx, det_idx in pairs:
        if ref_idx in used_ref or det_idx in used_det:
            continue
        used_ref.add(ref_idx)
        used_det.add(det_idx)
        errors.append(err)
    tp = len(errors)
    fp = len(det_s) - tp
    fn = len(ref_s) - tp
    return tp, fp, fn, np.array(errors, dtype=float)


def metrics(tp: int, fp: int, fn: int, duration_h: float, errors: np.ndarray) -> Dict[str, float]:
    sens = tp / (tp + fn) if (tp + fn) else np.nan
    ppv = tp / (tp + fp) if (tp + fp) else np.nan
    f1 = 0.0 if tp == 0 and (fp > 0 or fn > 0) else (2 * sens * ppv / (sens + ppv) if sens + ppv > 0 else np.nan)
    q25, q75 = np.percentile(errors * 1000.0, [25, 75]) if len(errors) else (np.nan, np.nan)
    return {
        "sensitivity": sens,
        "ppv": ppv,
        "f1": f1,
        "fp_per_hour": fp / duration_h if duration_h > 0 else np.nan,
        "fn_per_hour": fn / duration_h if duration_h > 0 else np.nan,
        "median_timing_error_ms": float(np.median(errors * 1000.0)) if len(errors) else np.nan,
        "iqr_timing_error_ms": float(q75 - q25) if len(errors) else np.nan,
        "p95_timing_error_ms": float(np.percentile(errors * 1000.0, 95)) if len(errors) else np.nan,
    }


if __name__ == "__main__":
    ensure_mitdb()
    print(f"MIT-BIH Arrhythmia Database v{MITDB_VERSION} available at {DATA_DIR}")

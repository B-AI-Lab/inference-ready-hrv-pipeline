#!/usr/bin/env python3
"""Benchmark ECG-to-RR runtime and rebuild publication-facing runtime artifacts.

This script intentionally preserves detector-accuracy outputs. It only replaces
runtime-dependent tables, text, and figure artifacts.
"""

from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-codex")

import importlib.util
import shutil
import sys
import time
from pathlib import Path
from typing import Callable

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
VALIDATION = ROOT
FIG_DIR = ROOT / "figures"
ARCHIVE = ROOT / "_runtime_benchmark_archive"

RUNTIME_REPS = 7
FW_NAME = "Embedded Pan-Tompkins firmware replay"
HAM_NAME = "Hamilton"
REF_BEATS = 109_494
SOURCE_TRUTH = {
    FW_NAME: {
        "TP": 107641,
        "FP": 1405,
        "FN": 1853,
        "sensitivity": 0.9830766982665716,
        "ppv": 0.9871155292261982,
        "f1": 0.9850919740093348,
        "median_timing_error_ms": 86.00000000001273,
        "f1_median": 0.9984406992079625,
        "f1_iqr": 0.004505670238717507,
    },
    HAM_NAME: {
        "TP": 107485,
        "FP": 1395,
        "FN": 2009,
        "sensitivity": 0.9816519626646208,
        "ppv": 0.9871877296105804,
        "f1": 0.984412063707218,
        "median_timing_error_ms": 61.55555555551473,
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mitval = load_module("mitval_runtime_benchmark", VALIDATION / "mitbih_validation.py")
fwcheck = load_module("firmware_runtime_benchmark", ROOT / "run_ecg_to_rr_benchmark.py")


def archive_previous_outputs() -> None:
    ARCHIVE.mkdir(exist_ok=True)
    paths = [
        ROOT / "ecg_to_rr_runtime_results.csv",
        ROOT / "ecg_to_rr_benchmark_summary.csv",
        ROOT / "ecg_to_rr_supplementary_table.csv",
        ROOT / "ecg_to_rr_supplementary_table.md",
        ROOT / "ecg_to_rr_figure_source_data.csv",
        ROOT / "ecg_to_rr_figure_caption.md",
        ROOT / "manuscript_results_text.md",
        ROOT / "ecg_to_rr_validation_report.md",
        FIG_DIR / "supplementary_ecg_to_rr_validation.pdf",
        FIG_DIR / "supplementary_ecg_to_rr_validation.png",
        FIG_DIR / "supplementary_ecg_to_rr_validation.svg",
    ]
    for path in paths:
        if path.exists():
            archived = ARCHIVE / path.name
            if not archived.exists():
                shutil.copy2(path, archived)


def load_all_records() -> list[dict[str, object]]:
    rows = []
    for record in mitval.MITDB_RECORDS:
        data = mitval.read_record(record)
        rows.append(
            {
                "record": record,
                "channel": data["channel"],
                "sig_250": np.asarray(data["sig_250"], dtype=float),
                "ref_s": np.asarray(data["ref_s"], dtype=float),
                "duration_s": float(data["duration_resampled_s"]),
                "duration_h": float(data["duration_h"]),
            }
        )
    return rows


def benchmark_detector(
    records: list[dict[str, object]],
    detector_name: str,
    detector_fn: Callable[[np.ndarray], np.ndarray],
    runtime_boundary: str,
) -> pd.DataFrame:
    rows = []
    for data in records:
        signal = data["sig_250"]
        detector_fn(signal)
        for rep in range(1, RUNTIME_REPS + 1):
            t0 = time.perf_counter()
            det_s = detector_fn(signal)
            runtime_s = time.perf_counter() - t0
            duration_s = float(data["duration_s"])
            rows.append(
                {
                    "record": data["record"],
                    "detector": detector_name,
                    "rep": rep,
                    "runtime_s": runtime_s,
                    "duration_s": duration_s,
                    "ms_per_min_ecg": runtime_s * 1000.0 / (duration_s / 60.0),
                    "realtime_factor": runtime_s / duration_s,
                    "samples_per_s": len(signal) / runtime_s if runtime_s > 0 else np.nan,
                    "n_samples": len(signal),
                    "n_detections": len(det_s),
                    "runtime_boundary": runtime_boundary,
                }
            )
    return pd.DataFrame(rows)


def median_iqr(values: pd.Series) -> tuple[float, float]:
    return float(values.median()), float(values.quantile(0.75) - values.quantile(0.25))


def runtime_summary(runtime_df: pd.DataFrame) -> pd.DataFrame:
    per_record = (
        runtime_df.groupby(["detector", "record"], as_index=False)
        .agg(
            runtime_s=("runtime_s", "median"),
            ms_per_min_ecg=("ms_per_min_ecg", "median"),
            realtime_factor=("realtime_factor", "median"),
        )
    )
    rows = []
    for detector, group in per_record.groupby("detector"):
        runtime_med, runtime_iqr = median_iqr(group["runtime_s"])
        ms_med, ms_iqr = median_iqr(group["ms_per_min_ecg"])
        rtf_med, rtf_iqr = median_iqr(group["realtime_factor"])
        rows.append(
            {
                "detector": detector,
                "median_runtime_s": runtime_med,
                "iqr_runtime_s": runtime_iqr,
                "median_ms_per_min_ecg": ms_med,
                "iqr_ms_per_min_ecg": ms_iqr,
                "median_realtime_factor": rtf_med,
                "iqr_realtime_factor": rtf_iqr,
            }
        )
    return pd.DataFrame(rows)


def verify_accuracy_unchanged(records: list[dict[str, object]]) -> pd.DataFrame:
    rows = []
    error_rows = []
    for detector_name, detector_fn in [
        (FW_NAME, fwcheck.firmware_replay),
        (HAM_NAME, fwcheck.hamilton),
    ]:
        for data in records:
            det_s = detector_fn(data["sig_250"])
            tp, fp, fn, errs = mitval.match_detections(data["ref_s"], np.sort(det_s))
            metrics = mitval.metrics(tp, fp, fn, float(data["duration_h"]), errs)
            rows.append(
                {
                    "record": data["record"],
                    "detector": detector_name,
                    "TP": tp,
                    "FP": fp,
                    "FN": fn,
                    **metrics,
                }
            )
            for err_s in errs:
                error_rows.append(
                    {
                        "panel": "C",
                        "record": data["record"],
                        "detector": detector_name,
                        "measure": "absolute_timing_error_ms",
                        "value": abs(float(err_s)) * 1000.0,
                    }
                )
    recomputed = pd.DataFrame(rows)
    for detector_name, truth in SOURCE_TRUTH.items():
        sub = recomputed[recomputed.detector == detector_name]
        totals = {k: int(sub[k].sum()) for k in ("TP", "FP", "FN")}
        expected = {k: int(truth[k]) for k in ("TP", "FP", "FN")}
        if totals != expected:
            raise RuntimeError(f"{detector_name} accuracy mismatch: {totals} != {expected}")
    pd.DataFrame(error_rows).to_csv(ROOT / "_runtime_correction_timing_errors.tmp.csv", index=False)
    return recomputed


def update_benchmark_summary(runtime_sum: pd.DataFrame) -> None:
    agg = pd.read_csv(ROOT / "ecg_to_rr_benchmark_summary.csv")
    for detector in [FW_NAME, HAM_NAME]:
        rt = runtime_sum[runtime_sum.detector == detector].iloc[0]
        mask = agg.detector == detector
        agg.loc[mask, "median_runtime_s"] = rt.median_runtime_s
        agg.loc[mask, "iqr_runtime_s"] = rt.iqr_runtime_s
        agg.loc[mask, "median_ms_per_min_ecg"] = rt.median_ms_per_min_ecg
        agg.loc[mask, "median_realtime_factor"] = rt.median_realtime_factor
    agg.to_csv(ROOT / "ecg_to_rr_benchmark_summary.csv", index=False)


def write_supplementary_table(runtime_sum: pd.DataFrame) -> None:
    agg = pd.read_csv(ROOT / "ecg_to_rr_benchmark_summary.csv")
    rows = []
    for detector, source in [
        (FW_NAME, "controlled offline execution time of the firmware-equivalent implementation"),
        (HAM_NAME, "controlled offline execution time of the Hamilton comparator"),
    ]:
        gross = agg[(agg.scope == "gross") & (agg.detector == detector)].iloc[0]
        rt = runtime_sum[runtime_sum.detector == detector].iloc[0]
        rows.append(
            {
                "Detector": detector,
                "TP": int(gross.TP),
                "FP": int(gross.FP),
                "FN": int(gross.FN),
                "Sensitivity": gross.sensitivity,
                "PPV": gross.ppv,
                "F1": gross.f1,
                "Median timing error ms": gross.median_timing_error_ms,
                "FP/h": gross.fp_per_hour,
                "Runtime source": source,
                "Offline runtime": f"{rt.median_runtime_s:.4f} s/record",
                "Runtime IQR": f"{rt.iqr_runtime_s:.4f} s/record",
                "ms/min ECG": f"{rt.median_ms_per_min_ecg:.4f}",
                "Real-time factor": rt.median_realtime_factor,
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(ROOT / "ecg_to_rr_supplementary_table.csv", index=False)
    md = table.copy()
    for col in ["Sensitivity", "PPV", "F1"]:
        md[col] = md[col].map(lambda x: f"{x:.4f}")
    md["Median timing error ms"] = md["Median timing error ms"].map(lambda x: f"{x:.1f}")
    md["FP/h"] = md["FP/h"].map(lambda x: f"{x:.1f}")
    md["Real-time factor"] = md["Real-time factor"].map(lambda x: f"{x:.6f}")
    widths = {
        col: max(len(str(col)), *(len(str(v)) for v in md[col].tolist()))
        for col in md.columns
    }
    header = "| " + " | ".join(str(col).ljust(widths[col]) for col in md.columns) + " |"
    sep = "| " + " | ".join("-" * widths[col] for col in md.columns) + " |"
    body = [
        "| " + " | ".join(str(row[col]).ljust(widths[col]) for col in md.columns) + " |"
        for _, row in md.iterrows()
    ]
    (ROOT / "ecg_to_rr_supplementary_table.md").write_text("\n".join([header, sep, *body]) + "\n")


def figure_source_data(
    records: list[dict[str, object]],
    recomputed: pd.DataFrame,
    runtime_sum: pd.DataFrame,
) -> pd.DataFrame:
    agg = pd.read_csv(ROOT / "ecg_to_rr_benchmark_summary.csv")
    timing_errors = pd.read_csv(ROOT / "_runtime_correction_timing_errors.tmp.csv")
    rows = []
    record_pivot = recomputed.pivot(index="record", columns="detector", values="f1").reset_index()
    for _, row in record_pivot.iterrows():
        rows.append({"panel": "A", "record": row.record, "detector": "paired", "measure": "firmware_f1", "value": row[FW_NAME]})
        rows.append({"panel": "A", "record": row.record, "detector": "paired", "measure": "hamilton_f1", "value": row[HAM_NAME]})
        rows.append({"panel": "F", "record": row.record, "detector": "paired", "measure": "f1_difference", "value": row[FW_NAME] - row[HAM_NAME]})
    for detector in [FW_NAME, HAM_NAME]:
        gross = agg[(agg.scope == "gross") & (agg.detector == detector)].iloc[0]
        for metric in ["sensitivity", "ppv", "f1"]:
            rows.append({"panel": "B", "record": "", "detector": detector, "measure": metric, "value": gross[metric]})
        rt = runtime_sum[runtime_sum.detector == detector].iloc[0]
        for metric in ["median_runtime_s", "iqr_runtime_s", "median_ms_per_min_ecg", "median_realtime_factor"]:
            rows.append({"panel": "D", "record": "", "detector": detector, "measure": metric, "value": rt[metric]})

    example = next(item for item in records if item["record"] == "207")
    start_s, end_s = 1470.0, 1480.0
    sig = example["sig_250"]
    idx0, idx1 = int(start_s * mitval.FS_TARGET), int(end_s * mitval.FS_TARGET)
    t = np.arange(idx0, idx1) / mitval.FS_TARGET
    for time_s, value in zip(t, sig[idx0:idx1]):
        rows.append({"panel": "E", "record": "207", "detector": "ECG", "measure": "waveform_mv", "time_s": time_s, "value": value})
    for label, values in [
        ("expert", example["ref_s"]),
        (FW_NAME, fwcheck.firmware_replay(sig)),
        (HAM_NAME, fwcheck.hamilton(sig)),
    ]:
        for event_s in values[(values >= start_s) & (values <= end_s)]:
            rows.append({"panel": "E", "record": "207", "detector": label, "measure": "event_time_s", "time_s": event_s, "value": 1.0})

    rows.extend(timing_errors.to_dict("records"))
    source = pd.DataFrame(rows)
    source.to_csv(ROOT / "ecg_to_rr_figure_source_data.csv", index=False)
    (ROOT / "_runtime_correction_timing_errors.tmp.csv").unlink(missing_ok=True)
    return source


def build_figure(recomputed: pd.DataFrame, runtime_sum: pd.DataFrame, source: pd.DataFrame) -> None:
    FIG_DIR.mkdir(exist_ok=True)
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.dpi": 150,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
        }
    )
    colors = {FW_NAME: "#0072B2", HAM_NAME: "#D55E00", "expert": "#009E73", "ecg": "#2F2F2F"}
    fig, axes = plt.subplots(2, 3, figsize=(13.0, 7.6), constrained_layout=True)
    fig.suptitle(
        "Supplementary Figure Sx | External expert-annotation validation and computational benchmarking of the embedded ECG-to-RR detection route",
        fontsize=12,
        fontweight="bold",
    )

    ax = axes[0, 0]
    pivot = recomputed.pivot(index="record", columns="detector", values="f1").reset_index()
    ax.scatter(pivot[HAM_NAME], pivot[FW_NAME], s=42, color="#5B8DB8", edgecolor="white", linewidth=0.8, zorder=3)
    lo = max(0.62, min(pivot[HAM_NAME].min(), pivot[FW_NAME].min()) - 0.02)
    ax.plot([lo, 1.002], [lo, 1.002], color="#606060", lw=1.2, ls="--")
    for record in ["108", "228", "207", "208"]:
        row = pivot[pivot.record == record].iloc[0]
        ax.annotate(record, (row[HAM_NAME], row[FW_NAME]), xytext=(5, 5), textcoords="offset points", fontsize=8, weight="bold")
    ax.text(0.03, 0.95, "n = 48 records", transform=ax.transAxes, va="top")
    ax.set_xlabel("Hamilton F1")
    ax.set_ylabel("Firmware-equivalent F1")
    ax.set_title("Record-level agreement")
    ax.set_xlim(lo, 1.003)
    ax.set_ylim(lo, 1.003)

    ax = axes[0, 1]
    metrics = ["sensitivity", "ppv", "f1"]
    labels = ["Sensitivity", "PPV", "F1"]
    x = np.arange(len(metrics))
    width = 0.34
    agg = pd.read_csv(ROOT / "ecg_to_rr_benchmark_summary.csv")
    vals_fw = [float(agg[(agg.scope == "gross") & (agg.detector == FW_NAME)].iloc[0][m]) for m in metrics]
    vals_ham = [float(agg[(agg.scope == "gross") & (agg.detector == HAM_NAME)].iloc[0][m]) for m in metrics]
    b1 = ax.bar(x - width / 2, vals_fw, width, color=colors[FW_NAME], label="Firmware replay", edgecolor="#202020", linewidth=0.6)
    b2 = ax.bar(x + width / 2, vals_ham, width, color=colors[HAM_NAME], label="Hamilton", edgecolor="#202020", linewidth=0.6)
    for bars in [b1, b2]:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0007, f"{bar.get_height():.4f}", ha="center", va="bottom", fontsize=7, rotation=90)
    ax.set_xticks(x, labels)
    ax.set_ylim(0.976, 0.991)
    ax.set_ylabel("Score")
    ax.set_title("Aggregate accuracy")
    ax.text(0.02, 0.96, f"{REF_BEATS:,} expert-annotated reference beats", transform=ax.transAxes, fontsize=8, va="top")
    ax.legend(frameon=False, loc="upper right")

    ax = axes[0, 2]
    timing = source[source.measure == "absolute_timing_error_ms"]
    for detector in [FW_NAME, HAM_NAME]:
        vals = np.sort(timing[timing.detector == detector].value.astype(float).to_numpy())
        y = np.arange(1, len(vals) + 1) / len(vals)
        ax.plot(vals, y, lw=2.0, color=colors[detector], label="Firmware replay" if detector == FW_NAME else "Hamilton")
    ax.axvline(150, color="#777777", lw=1.1, ls="--")
    ax.axvline(86.0, color=colors[FW_NAME], lw=1.0, ls=":")
    ax.axvline(61.6, color=colors[HAM_NAME], lw=1.0, ls=":")
    ax.text(150, 0.08, "+/-150 ms", rotation=90, va="bottom", ha="right", fontsize=8, color="#555555")
    ax.text(86.0, 0.58, "86.0 ms", rotation=90, va="bottom", ha="right", fontsize=8, color=colors[FW_NAME])
    ax.text(61.6, 0.42, "61.6 ms", rotation=90, va="bottom", ha="right", fontsize=8, color=colors[HAM_NAME])
    ax.set_xlim(0, 155)
    ax.set_ylim(0, 1.01)
    ax.set_xlabel("Absolute timing error (ms)")
    ax.set_ylabel("Matched beats (ECDF)")
    ax.set_title("Timing-error distribution")
    ax.legend(frameon=False, loc="lower right")

    ax = axes[1, 0]
    rt_order = [FW_NAME, HAM_NAME]
    rt_vals = [runtime_sum[runtime_sum.detector == d].iloc[0].median_ms_per_min_ecg for d in rt_order]
    rt_err = [runtime_sum[runtime_sum.detector == d].iloc[0].iqr_ms_per_min_ecg / 2.0 for d in rt_order]
    ax.bar([0, 1], rt_vals, yerr=rt_err, capsize=4, color=[colors[FW_NAME], colors[HAM_NAME]], edgecolor="#202020", linewidth=0.7)
    for i, detector in enumerate(rt_order):
        rt = runtime_sum[runtime_sum.detector == detector].iloc[0]
        ax.text(i, rt_vals[i] * 0.92, f"{rt_vals[i]:.2f} ms/min\nRTF {rt.median_realtime_factor:.6f}", ha="center", va="top", fontsize=8, color="white", fontweight="bold")
    ax.set_xticks([0, 1], ["Firmware\nreplay", "Hamilton"])
    ax.set_ylabel("ms per min ECG")
    ax.set_ylim(0, max(rt_vals) * 1.16)
    ax.set_title("Controlled offline execution time")

    ax = axes[1, 1]
    wave = source[(source.panel == "E") & (source.detector == "ECG")]
    t = wave.time_s.astype(float).to_numpy()
    y = wave.value.astype(float).to_numpy()
    y_center = float(np.nanmedian(y))
    ax.plot(t - t[0], y, color=colors["ecg"], lw=1.15)
    events = source[(source.panel == "E") & (source.measure == "event_time_s")]
    marker_y = {
        "expert": y_center + 0.65 * np.nanstd(y),
        FW_NAME: y_center,
        HAM_NAME: y_center - 0.65 * np.nanstd(y),
    }
    markers = {"expert": "|", FW_NAME: "^", HAM_NAME: "v"}
    labels_e = {"expert": "Expert", FW_NAME: "Firmware replay", HAM_NAME: "Hamilton"}
    for detector in ["expert", FW_NAME, HAM_NAME]:
        vals = events[events.detector == detector].time_s.astype(float).to_numpy() - t[0]
        scatter_kwargs = {
            "s": 42,
            "marker": markers[detector],
            "color": colors.get(detector, "#000000"),
            "label": labels_e[detector],
            "zorder": 3,
        }
        if detector != "expert":
            scatter_kwargs.update({"edgecolor": "white", "linewidth": 0.5})
        ax.scatter(vals, np.full_like(vals, marker_y[detector]), **scatter_kwargs)
    ax.set_xlabel("Time in excerpt (s)")
    ax.set_ylabel("ECG (mV)")
    ax.set_title("Representative record 207 excerpt")
    ax.legend(frameon=False, loc="upper right", ncol=1)

    ax = axes[1, 2]
    diff = pivot.assign(diff=pivot[FW_NAME] - pivot[HAM_NAME]).sort_values("diff").reset_index(drop=True)
    ax.bar(np.arange(len(diff)), diff["diff"], color=np.where(diff["diff"] >= 0, colors[FW_NAME], colors[HAM_NAME]), edgecolor="none", width=0.82)
    ax.axhline(0, color="#202020", lw=1.0)
    for record in ["108", "228", "207", "208"]:
        idx = int(diff.index[diff.record == record][0])
        ax.text(idx, diff.loc[idx, "diff"] + (0.005 if diff.loc[idx, "diff"] >= 0 else -0.005), record, ha="center", va="bottom" if diff.loc[idx, "diff"] >= 0 else "top", fontsize=8, weight="bold", rotation=90)
    ax.set_xlabel("MIT-BIH records sorted by F1 difference")
    ax.set_ylabel("F1 firmware - Hamilton")
    ax.set_title("Record-wise F1 difference")

    for label, ax in zip("ABCDEF", axes.ravel()):
        ax.text(-0.12, 1.08, label, transform=ax.transAxes, fontsize=14, fontweight="bold", va="top")
        ax.grid(axis="y", color="#E6E6E6", lw=0.6)

    out_base = FIG_DIR / "supplementary_ecg_to_rr_validation"
    fig.savefig(out_base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".png"), dpi=600, bbox_inches="tight")
    plt.close(fig)


def write_caption() -> None:
    (ROOT / "ecg_to_rr_figure_caption.md").write_text(
        "Supplementary Figure Sx | External expert-annotation validation and computational benchmarking of the embedded ECG-to-RR detection route. "
        "The figure summarizes external validation on the MIT-BIH Arrhythmia Database using all 48 records and 109,494 expert-annotated reference beats. "
        "(A) Record-level F1 agreement between the firmware-equivalent embedded Pan-Tompkins detector replay and the independent Hamilton comparator, with records 108, 228, 207, and 208 labelled. "
        "(B) Gross pooled sensitivity, positive predictivity, and F1 using fixed one-to-one +/-150-ms matching against expert annotations. "
        "(C) Empirical cumulative distributions of absolute matched-beat timing error; vertical markers show the firmware-equivalent median of 86.0 ms, Hamilton median of 61.6 ms, and the predefined +/-150-ms matching tolerance. "
        "(D) Controlled offline execution time measured after data loading using identical 250-Hz MIT-BIH inputs, one warm-up run, seven sequential timed repetitions per record and detector, no multiprocessing, and constrained numerical-library threading. "
        "The firmware bar reports the controlled offline execution time of the firmware-equivalent implementation, not `py-ecg-detectors.pan_tompkins_detector` and not physical ESP32 latency. "
        "(E) A representative 10-s excerpt from record 207, selected a priori as one of the labelled difficult records rather than for visual perfection, with expert annotations, firmware-equivalent detections, and Hamilton detections overlaid. "
        "(F) Sorted record-wise F1 difference between firmware-equivalent replay and Hamilton. "
        "No MIT-BIH-driven detector parameter tuning was performed. This benchmark validates the ECG-to-RR acquisition adapter under the tested replay conditions and does not establish clinical diagnostic ECG validity of the complete AD8232/ESP32 hardware chain or of the downstream HRV pipeline.\n"
    )


def write_text_outputs(runtime_sum: pd.DataFrame) -> None:
    fw = runtime_sum[runtime_sum.detector == FW_NAME].iloc[0]
    ham = runtime_sum[runtime_sum.detector == HAM_NAME].iloc[0]
    (ROOT / "manuscript_results_text.md").write_text(
        f"The firmware-equivalent replay of the embedded Pan-Tompkins-based detector was evaluated on all 48 MIT-BIH records ({REF_BEATS:,} expert-annotated reference beats) and achieved gross sensitivity 0.9831, positive predictivity 0.9871, and F1 0.9851, with median matched-beat timing error 86.0 ms. The Hamilton comparator achieved sensitivity 0.9817, positive predictivity 0.9872, and F1 0.9844 under identical evaluation conditions. Controlled offline execution time of the firmware-equivalent implementation was {fw.median_runtime_s:.4f} s per approximately 30-min record (IQR {fw.iqr_runtime_s:.4f} s; {fw.median_ms_per_min_ecg:.4f} ms/min ECG; real-time factor {fw.median_realtime_factor:.6f}); Hamilton required {ham.median_runtime_s:.4f} s per record (IQR {ham.iqr_runtime_s:.4f} s; {ham.median_ms_per_min_ecg:.4f} ms/min ECG; real-time factor {ham.median_realtime_factor:.6f}). These values are controlled offline execution times and do not represent physical ESP32 latency. Record-level details are provided in Supplementary Figure Sx and Supplementary Table Sx.\n"
    )
    (ROOT / "ecg_to_rr_validation_report.md").write_text(
        f"""# ECG-to-RR Validation Report

## Status

Classification: GREEN for ECG-to-RR detection-performance readiness. Firmware-equivalent replay demonstrates strong MIT-BIH performance broadly comparable to Hamilton. The runtime benchmark uses the exact firmware-equivalent host replay rather than the earlier library Pan-Tompkins validation implementation. Physical ESP32 runtime remains unmeasured and is not claimed.

## Main Result

Firmware-equivalent embedded Pan-Tompkins replay: sensitivity 0.9831, PPV 0.9871, F1 0.9851, TP/FP/FN 107641/1405/1853, median matched-beat timing error 86.0 ms. Hamilton comparator: sensitivity 0.9817, PPV 0.9872, F1 0.9844, TP/FP/FN 107485/1395/2009, median matched-beat timing error 61.6 ms. Record-level median/IQR F1 was 0.9984/0.0045 for firmware replay and 0.9975/0.0064 for Hamilton.

## Controlled Offline Runtime

Runtime was measured after data loading on the same 250-Hz MIT-BIH signals, with one warm-up run and seven sequential timed repetitions per record and detector, no multiprocessing, and constrained numerical-library threading. Firmware-equivalent replay: median {fw.median_runtime_s:.4f} s per approximately 30-min record, IQR {fw.iqr_runtime_s:.4f} s, {fw.median_ms_per_min_ecg:.4f} ms/min ECG, real-time factor {fw.median_realtime_factor:.6f}. Hamilton: median {ham.median_runtime_s:.4f} s per record, IQR {ham.iqr_runtime_s:.4f} s, {ham.median_ms_per_min_ecg:.4f} ms/min ECG, real-time factor {ham.median_realtime_factor:.6f}. These are controlled offline execution times, not physical ESP32 latency.

## Problematic Records

Records with firmware-equivalent F1 < 0.95:

record,f1,sensitivity,ppv,TP,FP,FN
108,0.6997159824425511,0.7685762904140669,0.6421800947867299,1355,755,408
207,0.9348212021303576,0.9908602150537634,0.8847815650504081,1843,240,17
208,0.9293376468585052,0.9235194585448392,0.935229609321453,2729,189,226
228,0.7860696517412936,0.654164637116415,0.9846041055718476,1343,21,710

## Integrity Statement

No MIT-BIH-driven parameter tuning was performed. Accuracy values were not changed during runtime benchmarking. The reported values are based on a firmware-equivalent host replay of the current ESP32 detector port and an independent Hamilton comparator evaluated under the same matching protocol.
"""
    )


def main() -> None:
    archive_previous_outputs()
    records = load_all_records()
    runtime_path = ROOT / "ecg_to_rr_runtime_results.csv"
    runtime = pd.read_csv(runtime_path) if runtime_path.exists() else pd.DataFrame()
    complete_runtime = (
        len(runtime) == len(mitval.MITDB_RECORDS) * 2 * RUNTIME_REPS
        and set(runtime["detector"].unique()) == {FW_NAME, HAM_NAME}
        and int(runtime["rep"].max()) >= RUNTIME_REPS
    )
    if not complete_runtime:
        runtime_fw = benchmark_detector(
            records,
            FW_NAME,
            fwcheck.firmware_replay,
            "controlled offline execution time of the firmware-equivalent implementation",
        )
        runtime_ham = benchmark_detector(
            records,
            HAM_NAME,
            fwcheck.hamilton,
            "controlled offline execution time of the Hamilton comparator",
        )
        runtime = pd.concat([runtime_fw, runtime_ham], ignore_index=True)
        runtime.to_csv(runtime_path, index=False)
    runtime_sum = runtime_summary(runtime)
    recomputed = verify_accuracy_unchanged(records)
    update_benchmark_summary(runtime_sum)
    write_supplementary_table(runtime_sum)
    source = figure_source_data(records, recomputed, runtime_sum)
    build_figure(recomputed, runtime_sum, source)
    write_caption()
    write_text_outputs(runtime_sum)
    print(runtime_sum.to_string(index=False))
    print("Accuracy totals verified unchanged; runtime provenance updated.")


if __name__ == "__main__":
    main()

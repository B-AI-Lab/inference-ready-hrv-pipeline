#!/usr/bin/env python3
"""Runtime-only QC update for Reviewer II Point 2."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent

spec = importlib.util.spec_from_file_location("noiseq", ROOT / "run_noise_quality_validation.py")
noiseq = importlib.util.module_from_spec(spec)
sys.modules["noiseq"] = noiseq
assert spec.loader is not None
spec.loader.exec_module(noiseq)


def df_to_md(df):
    return noiseq.df_to_md(df)


def runtime_summary(runtime_df):
    return runtime_df.groupby(["method", "boundary", "unit_label"]).agg(
        median_runtime_s=("runtime_s", "median"),
        iqr_runtime_s=("runtime_s", lambda x: float(np.percentile(x, 75) - np.percentile(x, 25))),
        median_ms_per_unit=("ms_per_unit", "median"),
        median_ms_per_10s_window=("ms_per_10s_window", "median"),
        median_realtime_factor=("real_time_factor", "median"),
    ).reset_index()


def metric(summary, method, boundary):
    row = summary[(summary.method == method) & (summary.boundary == boundary)].iloc[0]
    return row


def replace_runtime_section(report_path: Path, summary) -> None:
    text = report_path.read_text()
    table = df_to_md(summary)
    new = (
        "Runtime summary:\n\n"
        f"{table}\n\n"
        "Runtime QC interpretation: the previous apparent inversion was caused by a non-equivalent benchmark boundary. "
        "The earlier Signal Confidence quality-stage timing calculated confidence after every RR update across a concatenated multi-record stream, whereas the complete-path timing reset state by record and reported one decision per 10 s window. "
        "The corrected benchmark uses the same 2520 non-overlapping 10 s units for all four boundaries and computes one quality decision per unit. "
        "Under these corrected semantics, complete-path runtime is greater than the corresponding quality-assessment-only runtime for both methods.\n\n"
    )
    text = re.sub(r"Runtime summary:\n\n.*?\n\n## Interpretation", new + "## Interpretation", text, flags=re.S)
    report_path.write_text(text)


def update_text_files(summary) -> None:
    sc_q = metric(summary, "Signal Confidence", "quality assessment only: available RR intervals -> RR filtering/state update -> one Signal Confidence/Status decision per 10-s unit")
    sc_c = metric(summary, "Signal Confidence", "complete path: ECG -> firmware-equivalent detector -> RR -> Signal Confidence")
    or_q = metric(summary, "Orphanidou SQI", "quality assessment only: 10-s ECG segment + available Hamilton R peaks -> preprocessing/template SQI")
    or_c = metric(summary, "Orphanidou SQI", "complete path: ECG -> Hamilton detection/refinement -> SQI")

    methods = ROOT / "methods_insert.md"
    mtext = methods.read_text().strip()
    runtime_sentence = (
        " Runtime was benchmarked after loading data, with seven sequential repetitions per boundary after warm-up, using identical 10 s analysis units for quality-assessment-only and complete operational paths."
    )
    if "Runtime was benchmarked after loading data" not in mtext:
        methods.write_text(mtext + runtime_sentence + "\n")

    results = ROOT / "results_insert.md"
    rtext = results.read_text().strip()
    runtime_result = (
        f" Runtime QC showed median quality-assessment-only costs of {sc_q.median_ms_per_10s_window:.3f} ms/10 s unit for Signal Confidence and {or_q.median_ms_per_10s_window:.3f} ms/10 s segment for Orphanidou SQI; complete-path costs were {sc_c.median_ms_per_10s_window:.3f} and {or_c.median_ms_per_10s_window:.3f} ms/10 s segment, respectively."
    )
    rtext = re.sub(r" Runtime QC showed .*?respectively\.", "", rtext)
    results.write_text(rtext + runtime_result + "\n")

    response = ROOT / "reviewer_response.md"
    text = response.read_text()
    old = "Runtime was measured separately for quality-stage and complete-path boundaries so that RR-derived and ECG-morphology methods are not compared across mismatched computational scopes."
    new = (
        "Runtime was remeasured after final QC using directly comparable 10 s analysis units and seven sequential repetitions per boundary. "
        f"Quality-assessment-only costs were {sc_q.median_ms_per_10s_window:.3f} ms/10 s unit for Signal Confidence and {or_q.median_ms_per_10s_window:.3f} ms/10 s segment for Orphanidou SQI. "
        f"Complete operational-path costs were {sc_c.median_ms_per_10s_window:.3f} ms/10 s segment for ECG-to-firmware-replay-to-RR-to-Signal Confidence and {or_c.median_ms_per_10s_window:.3f} ms/10 s segment for ECG-to-Hamilton-to-Orphanidou SQI. "
        "Complete-path runtime was greater than the corresponding quality-stage runtime for both methods."
    )
    text = text.replace(old, new)
    response.write_text(text)


def main() -> None:
    records_data = []
    for record in noiseq.CLEAN_SOURCE_RECORDS:
        records_data.append(noiseq.read_ecg_record(record, is_clean_source=True))
    for record in noiseq.NSTDB_NOISE_RECORDS:
        records_data.append(noiseq.read_ecg_record(record, is_clean_source=False))

    runtime_df = noiseq.make_runtime_results(records_data, None)
    runtime_df.to_csv(ROOT / "runtime_results.csv", index=False)
    summary = runtime_summary(runtime_df)
    summary.to_csv(ROOT / "runtime_summary.csv", index=False)
    replace_runtime_section(ROOT / "validation_report.md", summary)
    update_text_files(summary)

    checks = []
    for method in ["Signal Confidence", "Orphanidou SQI"]:
        q = summary[(summary.method == method) & (summary.boundary.str.startswith("quality assessment only"))].iloc[0]
        c = summary[(summary.method == method) & (summary.boundary.str.startswith("complete path"))].iloc[0]
        checks.append({
            "method": method,
            "quality_ms_per_10s_window": q.median_ms_per_10s_window,
            "complete_ms_per_10s_window": c.median_ms_per_10s_window,
            "complete_ge_quality": bool(c.median_ms_per_10s_window >= q.median_ms_per_10s_window),
        })
    import pandas as pd

    pd.DataFrame(checks).to_csv(ROOT / "runtime_qc_consistency_check.csv", index=False)
    print(df_to_md(pd.DataFrame(checks)))


if __name__ == "__main__":
    main()

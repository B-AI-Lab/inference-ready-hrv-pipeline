#!/usr/bin/env python3
"""Download public PhysioNet validation datasets into script-expected paths."""

from __future__ import annotations

from pathlib import Path

try:
    import wfdb
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: wfdb. Install requirements-validation.txt first.") from exc


ROOT = Path(__file__).resolve().parents[1]

MITDB_RECORDS = [
    "100", "101", "102", "103", "104", "105", "106", "107", "108", "109",
    "111", "112", "113", "114", "115", "116", "117", "118", "119", "121",
    "122", "123", "124", "200", "201", "202", "203", "205", "207", "208",
    "209", "210", "212", "213", "214", "215", "217", "219", "220", "221",
    "222", "223", "228", "230", "231", "232", "233", "234",
]
NSTDB_RECORDS = [
    "118e24", "118e18", "118e12", "118e06", "118e00", "118e_6",
    "119e24", "119e18", "119e12", "119e06", "119e00", "119e_6",
    "bw", "em", "ma",
]


def main() -> None:
    mitdb_dir = ROOT / "reviewer2_rpeak_validation" / "data" / "mitdb"
    nstdb_dir = ROOT / "reviewer2_signal_quality_validation" / "data" / "nstdb"
    mitdb_dir.mkdir(parents=True, exist_ok=True)
    nstdb_dir.mkdir(parents=True, exist_ok=True)

    wfdb.dl_database("mitdb", str(mitdb_dir), records=MITDB_RECORDS, annotators=["atr"], keep_subdirs=False)
    wfdb.dl_database("nstdb", str(nstdb_dir), records=NSTDB_RECORDS, keep_subdirs=False)
    print(f"MIT-BIH Arrhythmia Database written to {mitdb_dir}")
    print(f"MIT-BIH Noise Stress Test Database written to {nstdb_dir}")


if __name__ == "__main__":
    main()


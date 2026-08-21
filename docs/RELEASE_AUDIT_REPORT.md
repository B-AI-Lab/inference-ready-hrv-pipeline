# Release Audit Report

## Scope

This report summarizes the public repository hygiene audit for the HRV inference-ready data pipeline. Scientific algorithms, validation metrics, and evidence-bearing numerical outputs are documented separately in [VALIDATION.md](VALIDATION.md) and [IMPLEMENTATION_CORRECTNESS.md](IMPLEMENTATION_CORRECTNESS.md).

## Included Public Material

- Production HRV processing engine and live bridge sources.
- HRV-only dashboard source for monitoring, event annotation, and export.
- ESP32 ECG-to-RR firmware source under `firmware/esp32_ecg_rr/`.
- External ECG-to-RR benchmark scripts, tables, figures, and runtime artifacts under `validation/ecg_rpeak/`.
- Controlled signal-quality benchmark scripts, tables, figures, and runtime artifacts under `validation/signal_quality/`.
- Downstream RR-interface regression under `validation/downstream/`.
- Public validation-data downloader and requirements files.
- Documentation for architecture, validation traceability, firmware parity, data/privacy, and release exclusions.

## Excluded Material

See [PUBLIC_RELEASE_EXCLUSIONS.md](PUBLIC_RELEASE_EXCLUSIONS.md). Raw PhysioNet datasets, participant-level recordings, local exports, caches, build products, development-only firmware sketches, and obsolete manuscript drafts are not part of the public repository.

## Manuscript-Code Consistency

The public validation outputs are consistent with the manuscript-facing externally validated results:

- Firmware-equivalent ECG-to-RR F1 0.9851.
- Hamilton comparator F1 0.9844.
- Firmware-equivalent controlled offline runtime 0.3146 s per approximately 30-min MIT-BIH record.
- Signal Confidence AUROC/AUPRC 0.754/0.545.
- Orphanidou AUROC/AUPRC 0.662/0.336.
- Signal Status balanced accuracy/MCC 0.727/0.446.
- Orphanidou balanced accuracy/MCC 0.632/0.341.

Participant-level feasibility data and private operational exports are not distributed.

## Firmware Parity Conclusion

The firmware source in `firmware/esp32_ecg_rr/main.cpp` and the host replay in `validation/ecg_rpeak/run_ecg_to_rr_benchmark.py` are source-level equivalent for the documented offline replay semantics. Direct compiled C++/ESP32 output parity on identical ECG input remains an unperformed hardware fixture.

## Respiratory Proxy Conclusion

The public code keeps one production physiological/spectral definition in `HRVConfig` in `hrv_live_processing_engine.py`. The production engine withholds LF/HF and respiration-proxy output when the detrended RR spectrum has negligible variability, and it reports a respiration proxy only when the dominant supported diagnostic-band peak is inside the reliable RR-derived proxy range.

The public documentation uses "RR-derived respiration proxy" and explicitly states that it is not measured airflow, thoracic movement, or ventilation.

## Remaining Author Decisions

- Add a public reproduction package for any additional manuscript analyses if those values should be independently reproducible from this repository.
- Add DOI, repository URL, release date, and version to `CITATION.cff` when assigned and verified.
- Review dashboard dependency security before archival release. `xlsx` currently has no npm audit fix available, so replacing or constraining spreadsheet export dependencies requires an explicit dependency decision.

## Readiness

The public repository is organized for external use and excludes the known risky legacy/private material. Scientific limitations remain documented in the README and validation documentation.

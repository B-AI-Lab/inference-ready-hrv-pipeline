# Release Audit Report

## Supersession Note

This repository-hygiene audit is superseded for scientific readiness by
`docs/IMPLEMENTATION_CORRECTNESS.md`. That later implementation audit identified
respiration-proxy and zero-power spectral boundary issues. A follow-up correction
added validity gating for negligible spectra, lower-bound leakage, and selected
upper-band alias cases. The output remains an experimental RR-derived spectral
proxy and should not be described as measured respiration or as a fully
anti-aliased respiratory-rate estimator.

## A. Changes Made

- Created a curated public release candidate under `hrv-pipeline-public/`.
- Added public-facing README, MIT license, citation metadata, requirements files, ignore rules, and validation data download helper.
- Copied production HRV engine and bridge sources.
- Copied the HRV-only dashboard subset and removed EEG/hemodynamic tab imports from the public-candidate dashboard shell.
- Copied Reviewer-2 final ECG-to-RR and RR-stream quality validation scripts, outputs, tables, and figures while excluding raw datasets and superseded archives.
- Added documentation for architecture, validation traceability, firmware parity, data/privacy, and release exclusions.

## B. Repository Exclusions

See `docs/PUBLIC_RELEASE_EXCLUSIONS.md`.

## C. Manuscript-Code Consistency

The Reviewer-2 final ECG-to-RR and RR-stream quality validation outputs in the release candidate are consistent with `MG_npjDM_rev_clean_of.docx` for the externally validated results:

- Firmware-equivalent ECG-to-RR F1 0.9851.
- Hamilton F1 0.9844.
- Firmware-equivalent controlled offline runtime 0.3146 s per approximately 30-min MIT-BIH record.
- Signal Confidence AUROC/AUPRC 0.754/0.545.
- Orphanidou AUROC/AUPRC 0.662/0.336.
- Signal Status balanced accuracy/MCC 0.727/0.446.
- Orphanidou balanced accuracy/MCC 0.632/0.341.

Downstream synthetic validation and latency values are described in the manuscript, but I did not identify a complete public reproduction package for those numerical tables in the current workspace. They are therefore not re-reported in `docs/VALIDATION.md` as independently reproducible repository results.

## D. Firmware Parity Conclusion

Classification: **source-level equivalent with caveat** for the Reviewer-2 final firmware source copied to `firmware/reviewer2_final/main.cpp` and the host replay in `reviewer2_rpeak_final/run_firmware_equivalence_check.py`. The later implementation-correctness audit clarifies that direct compiled C++/ESP32 output parity on identical ECG input remains an unperformed fixture.

The older root development firmware was excluded from the public candidate and is not used for manuscript evidence.

## E. Respiratory Proxy Conclusion

The public candidate keeps one production physiological/spectral definition in `HRVConfig` in `hrv_live_processing_engine.py`. The standalone `hrv_viz.py` inspector was excluded because it independently redefined spectral and respiration-proxy constants and was not part of manuscript reproduction.

The production engine now withholds LF/HF and respiration-proxy output when the detrended RR spectrum has negligible variability, and it reports a respiration proxy only when the dominant supported diagnostic-band peak is inside the reliable RR-derived proxy range. The public docs use "RR-derived respiration proxy" and explicitly state that it is not measured airflow, thoracic movement, or ventilation.

## F. Reviewer-2 Validation Provenance

See `docs/VALIDATION.md` for exact source/output/command mapping.

## G. Remaining Author Decisions

- Decide whether to add a public reproduction package for the manuscript's synthetic downstream validation and latency benchmarking values.
- Add final DOI, repository URL, release date, and version to `CITATION.cff` when assigned.
- Confirm institutional approval for MIT licensing before public release.
- Review dashboard dependency security before release. `npm audit --omit=dev --audit-level=high` reported advisories in build tooling dependencies and `xlsx`; `xlsx` currently has no npm audit fix available, so replacing or constraining spreadsheet export dependencies requires an explicit dependency decision.

## H. Public-Release Readiness

**READY AFTER MANUSCRIPT WORDING UPDATE**

The Reviewer-2 validation-facing release candidate is internally consistent and
excludes the known risky legacy/private material. The respiration-proxy
zero-power and audited 0.05/0.55-Hz boundary failures have been corrected for
the deterministic regression cases. Public release should wait until the
manuscript wording explicitly describes the proxy validity gate and avoids any
claim that the RR-derived proxy is a direct or fully anti-aliased respiration
measure.

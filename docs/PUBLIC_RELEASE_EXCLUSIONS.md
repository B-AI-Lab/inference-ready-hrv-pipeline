# Public Release Exclusions

These items are intentionally excluded from the public release candidate or ignored by `.gitignore`.

| Item | Decision | Reason |
|---|---|---|
| Root `src/main.cpp` and root `platformio.ini` from the development workspace | Excluded | Older display-oriented firmware path. It is not the Reviewer-2 final evidence-bearing detector route. |
| `hrv_viz.py` | Excluded | Standalone offline inspector, not part of manuscript reproduction; independently redefines spectral and respiration-proxy constants. |
| `hrv_benchmark_exports/` | Excluded | Unknown provenance; not required for public functionality or validation reproduction. |
| `hrv_validation_exports/` | Excluded | Unknown provenance; not required for public functionality or validation reproduction. |
| `.paper-review/`, older manuscript drafts, Word lock files | Excluded | Reviewer correspondence and obsolete drafts are not authoritative public documentation. |
| `.venv*`, `.pio/`, `node_modules/`, dashboard `dist/`, caches | Excluded | Local environments and generated build artifacts. |
| Raw MIT-BIH and NSTDB waveform directories | Excluded | Publicly downloadable datasets should not be vendored unnecessarily. |
| `reviewer2_rpeak_final/archive_pre_runtime_provenance_correction/` | Excluded | Preserved internal audit history with superseded runtime provenance. |
| `reviewer2_signal_quality_validation/archive_pre_method_correction/` | Excluded | Preserved internal audit history with superseded method/runtime outputs. |
| Dashboard EEG and hemodynamic modules | Excluded | Future-scope/experimental modules outside the HRV manuscript validation path. |

No uncertain material was deleted from the working repository. Exclusion here means "not copied into the public release candidate" or "ignored for future public commits."


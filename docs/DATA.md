# Data and Privacy

## Public Validation Data

The release candidate does not vendor PhysioNet waveform files. The Reviewer-2 validation scripts expect public datasets in local `data/` directories and can be populated with:

```bash
python3 scripts/download_public_validation_data.py
```

Datasets:

- MIT-BIH Arrhythmia Database v1.0.0, DOI `10.13026/C2F305`
- MIT-BIH Noise Stress Test Database v1.0.0, DOI `10.13026/C2HS3T`

## Real-World Participant Data

Individual-level physiological recordings from the emergency-simulation sessions are not included. The public repository must not imply that any local export folder contains the 10-participant / 5-dyad physician Polar H10 study unless provenance is independently established and sharing is compatible with consent and institutional data-protection requirements.

## Export Privacy

Live BLE exports may include subject IDs, display names, BLE MAC addresses, local timestamps, and free-text event labels. Treat generated exports as potentially identifiable operational records. Do not commit real recording exports to the public repository.

## Excluded Local Data

The development-workspace folders `hrv_benchmark_exports/` and `hrv_validation_exports/` were excluded from the public release candidate because their provenance was not established from scripts, metadata, or logs. They are not used for manuscript validation claims.


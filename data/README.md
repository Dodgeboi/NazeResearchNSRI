# Data

This directory contains the fresh public-evidence studies used in the current manuscript. Each study keeps raw simulation rows separate from processed summaries.

## `observed`

This is the non-simulation evidence layer. It contains:

- the public THREAT hospital/market ransomware event file from openICPSR V1;
- CISA's 2026-09-01 Known Exploited Vulnerabilities catalog;
- hashes, source URLs, version and license information;
- deterministic hospital-event and ransomware-linked-CVE summaries; and
- a bridge table that states whether each observational endpoint is comparable to an existing simulation output.

The bridge is deliberately non-calibrating. Emergency-department diversion, canceled or delayed care, hospital volume, binary modeled service downtime, and technical recovery are different constructs. The analysis records those differences instead of converting one into another without data.

## `public_validation`

The 15-minute validation phase contains:

- 500 paired primary scenarios;
- nine scale-by-posture cross-setting cells;
- 128 joint stress settings;
- time-step and recovery-horizon diagnostics; and
- the exploratory fine-step pilot.

The two files ending in `initial_design_error.csv` are retained intentionally. They record the original diagnostic mistake described in `study/DEVIATIONS.md` and are not used as corrected results.

## `fine_step_replication`

The frozen five-minute replication contains:

- 500 new paired primary scenarios; and
- 128 new joint stress settings with 10 scenarios per portfolio.

## Reading the files

One row represents one portfolio evaluated under one synthetic scenario. It does not represent a hospital, patient, or observed cyberattack.

The raw manifests record seeds, configurations, run counts, and file hashes. Processed analysis manifests identify the source files and analysis outputs. `derived_metric_audit.csv` independently reconstructs exported ratios from their numerators, denominators, and final-service flags.

Do not combine the 15-minute and five-minute rows into one effect estimate. They are separate study phases with different scenario banks and were used to assess numerical sensitivity.

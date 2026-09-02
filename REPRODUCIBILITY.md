# Reproducibility notes

## Environment

The exact package versions used for the committed runs are pinned in `requirements.txt`. Python 3.11 or newer is required. Install the package in editable mode after installing the pins.

## Randomness and pairing

Unpaired development runs use deterministic streams derived from a master seed and trial identifier. Paired studies separate topology, entry-point, and simulation streams and attach stochastic events to stable scenario, event-type, time-step, and node- or edge-level positions. This prevents a portfolio from receiving a different random value merely because its control path changed execution order.

## Frozen studies

The study protocols were written before their corresponding frozen runs. Manifests record seeds and file hashes. Any correction must preserve the superseded file, explain the deviation, and avoid reusing a scenario bank selected after seeing the result.

## Verification

The current repository is expected to produce:

- 59 passing unit and invariant tests;
- 12/12 behavioral validation checks; and
- zero failures when the derived metrics are reconstructed from fresh raw files.

The observed-data products can be rebuilt without running a simulation:

```bash
python scripts/analyze_observed_data.py
```

`data/observed/raw/source_manifest.json` records the source version and SHA-256 hash for each public snapshot. CISA's live feed changes over time, so reproduction must use the committed snapshot unless a refresh is explicitly treated as a new data release. The THREAT file is a normalized export of the public openICPSR preview; replacing it with the depositor's original download is a presubmission verification task, not an invisible overwrite.

Confidence intervals describe Monte Carlo uncertainty conditional on the model. They do not include uncertainty from missing mechanisms, incorrect assumptions, or transfer to real hospitals.

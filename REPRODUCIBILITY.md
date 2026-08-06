# Reproducibility notes

## Environment

The exact package versions used for the committed runs are pinned in `requirements.txt`. Python 3.11 or newer is required. Install the package in editable mode after installing the pins.

## Randomness and pairing

Unpaired development runs use deterministic streams derived from a master seed and trial identifier. Paired studies separate topology, entry-point, and simulation streams and attach stochastic events to stable scenario, event-type, time-step, and node- or edge-level positions. This prevents a portfolio from receiving a different random value merely because its control path changed execution order.

## Frozen studies

The study protocols were written before their corresponding frozen runs. Manifests record seeds and file hashes. Any correction must preserve the superseded file, explain the deviation, and avoid reusing a scenario bank selected after seeing the result.

## Verification

The current repository is expected to produce:

- 56 passing unit and invariant tests;
- 12/12 behavioral validation checks; and
- zero failures when the derived metrics are reconstructed from fresh raw files.

Confidence intervals describe Monte Carlo uncertainty conditional on the model. They do not include uncertainty from missing mechanisms, incorrect assumptions, or transfer to real hospitals.

# Multi-objective portfolio data

This directory contains the primary paired portfolio study.

- `raw/multiobjective_portfolio_optimization_results.csv`: 12,960 discovery executions; 30 common scenarios for each of 432 profile-candidates.
- `processed/multiobjective_holdout_protocol.json`: finalist rule, identities, seed, and sample size frozen before holdout generation.
- `raw/multiobjective_holdout_results.csv`: 8,550 fresh executions; 150 common scenarios for each of 57 profile-candidates.
- `processed/`: discovery summaries, frontiers, preferences, benchmarks, bootstrap stability, and earlier single-objective optimizer summaries.
- `holdout_processed/`: the same primary summaries recomputed only from holdout trials, using 1,000 paired bootstrap resamples.

All six objectives are minimized. Mean and CVaR90 weighted service-hours lost, modeled sustained-outage probability, and 72-hour non-recovery are conditional simulation outcomes. Implementation cost and operational burden are normalized scenario points declared in configuration; they are not real dollars, staff hours, or field measurements.

Observed THREAT and CISA records remain under `data/observed`. They are external construct checks and were not used to fit control effects or choose the portfolio frontier.

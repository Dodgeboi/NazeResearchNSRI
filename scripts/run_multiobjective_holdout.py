#!/usr/bin/env python3
"""Freeze discovery finalists, then run fresh paired holdout scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.config import load_config
from grrc.multiobjective import (
    MULTIOBJECTIVE_HOLDOUT_SEED,
    run_multiobjective_holdout,
    select_holdout_candidates,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/multiobjective_portfolio.yaml")
    parser.add_argument("--discovery", default="data/multiobjective/processed")
    parser.add_argument("--output",
                        default="data/multiobjective/raw/multiobjective_holdout_results.csv")
    parser.add_argument("--trials", type=int, default=150)
    parser.add_argument("--threshold", type=float, default=0.50)
    args = parser.parse_args()

    discovery = Path(args.discovery)
    stability = pd.read_csv(discovery / "portfolio_pareto_stability.csv")
    preferences = pd.read_csv(discovery / "portfolio_preference_scenarios.csv")
    benchmarks = pd.read_csv(discovery / "portfolio_benchmark_comparison.csv")
    finalists = select_holdout_candidates(
        stability, preferences, benchmarks, threshold=args.threshold)

    # Write the frozen rule and identities before any holdout simulation runs.
    manifest_path = discovery / "multiobjective_holdout_protocol.json"
    manifest_path.write_text(json.dumps({
        "status": "frozen before holdout generation",
        "selection_rule": (
            "discovery bootstrap Pareto inclusion >= threshold, union every "
            "declared preference choice and benchmark comparator"),
        "threshold": args.threshold,
        "trials_per_candidate": args.trials,
        "holdout_master_seed": MULTIOBJECTIVE_HOLDOUT_SEED,
        "candidate_counts": {key: len(value)
                             for key, value in finalists.items()},
        "finalists": finalists,
    }, indent=2), encoding="utf-8")
    run_multiobjective_holdout(
        load_config(args.config), finalists, args.output,
        trials_per_candidate=args.trials)


if __name__ == "__main__":
    main()

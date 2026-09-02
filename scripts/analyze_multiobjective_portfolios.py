#!/usr/bin/env python3
"""Analyze paired optimizer results without generating new simulations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.config import load_config, load_defense_costs
from grrc.multiobjective import (
    aggregate_objectives,
    benchmark_portfolios,
    bootstrap_pareto_stability,
    load_operational_burdens,
    pareto_frontier,
    preference_scenarios,
)
from grrc.utilities import ensure_dirs, write_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/multiobjective_portfolio.yaml")
    parser.add_argument("--raw", required=True,
                        help="Paired optimizer per-trial CSV")
    parser.add_argument("--out", default="data/multiobjective/processed")
    parser.add_argument("--bootstrap", type=int, default=500)
    args = parser.parse_args()

    config_path = Path(args.config)
    cfg = load_config(config_path)
    costs = load_defense_costs("configs/defense_costs.yaml")
    burdens = load_operational_burdens("configs/defense_burdens.yaml")
    raw = pd.read_csv(args.raw)
    output = Path(args.out)
    ensure_dirs(output)

    summary = aggregate_objectives(raw, cfg, costs, burdens)
    frontier = pareto_frontier(summary)
    preferences = preference_scenarios(frontier, cfg)
    benchmarks = benchmark_portfolios(summary, cfg)
    stability = bootstrap_pareto_stability(
        raw, cfg, costs, burdens, n_boot=args.bootstrap, seed=cfg.seed)

    files = {
        "objective_summary": output / "portfolio_objective_summary.csv",
        "pareto_frontier": output / "portfolio_pareto_frontier.csv",
        "preference_scenarios": output / "portfolio_preference_scenarios.csv",
        "pareto_stability": output / "portfolio_pareto_stability.csv",
        "benchmark_comparison": output / "portfolio_benchmark_comparison.csv",
    }
    for frame, path in zip(
            (summary, frontier, preferences, stability, benchmarks),
            files.values()):
        write_csv(frame, path)
    manifest = {
        "design": "six-objective Pareto analysis of paired scenario replays",
        "raw_results": str(Path(args.raw)),
        "config": str(config_path),
        "bootstrap_samples": args.bootstrap,
        "costs": "normalized scenario points; not dollars",
        "operational_burdens": (
            "normalized scenario points; not measured staffing burden"),
        "outputs": {name: str(path) for name, path in files.items()},
    }
    (output / "multiobjective_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

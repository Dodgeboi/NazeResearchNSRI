#!/usr/bin/env python3
"""Analyze one stage of the multi-objective study from committed raw trials.

Replaces ``analyze_multiobjective_portfolios.py``, which produced a manifest
with no hash of any input or output and recorded paths using the host's
separator, so a manifest written on Windows could not be resolved on the
declared CI runner (audit ISSUE-014, ISSUE-015).

What this adds beyond the frontier itself:

* **Monte Carlo standard error for every stochastic objective**, plus a count
  of candidate pairs the scenario bank cannot reliably order. A frontier
  reported without its simulation error invites a reader to treat a noisy
  point estimate as exact.
* **The full sustained-outage k ladder**, so a reader who prefers a different
  service count reads it off the same table instead of taking the authors'
  primary k on faith.
* **A hashed manifest** binding config, cost and burden tables, raw input,
  code commit and environment to every output file.
* For a confirmatory stage, **the full-space versus finalist-only
  comparison**: how many candidates appear efficient only because the
  candidate that dominates them was never evaluated.

Usage
-----
    python scripts/analyze_portfolio_stage.py --stage discovery
    python scripts/analyze_portfolio_stage.py --stage confirmation
"""

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
    frontier_resolution_warning,
    load_operational_burdens,
    monte_carlo_error,
    pareto_frontier,
    preference_scenarios,
    restricted_frontier_comparison,
)
from grrc.provenance import (build_manifest, load_frozen_protocol,
                             write_manifest)
from grrc.utilities import ensure_dirs, write_csv

STAGE_DEFAULTS = {
    "discovery": {
        "raw": "data/multiobjective/discovery/discovery_results.csv",
        "out": "data/multiobjective/discovery",
        "bootstrap": 500,
    },
    "confirmation": {
        "raw": "data/multiobjective/confirmatory/"
               "multiobjective_confirmatory_results.csv",
        "out": "data/multiobjective/confirmatory",
        "bootstrap": 1000,
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=sorted(STAGE_DEFAULTS),
                        required=True)
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument("--raw", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--bootstrap", type=int, default=None)
    parser.add_argument("--protocol", default=None,
                        help="frozen protocol name (confirmation only)")
    args = parser.parse_args()

    defaults = STAGE_DEFAULTS[args.stage]
    raw_path = Path(args.raw or defaults["raw"])
    output = Path(args.out or defaults["out"])
    n_boot = args.bootstrap or defaults["bootstrap"]

    cfg = load_config(args.config)
    costs = load_defense_costs("configs/defense_costs.yaml")
    burdens = load_operational_burdens("configs/defense_burdens.yaml")
    raw = pd.read_csv(raw_path)
    ensure_dirs(output)

    protocol = None
    finalists: dict[str, list[str]] = {}
    if args.stage == "confirmation":
        if not args.protocol:
            raise SystemExit(
                "--protocol is required for a confirmatory analysis; the "
                "outputs must be bound to the design that authorized them")
        protocol = load_frozen_protocol(args.protocol)
        finalists = protocol["body"]["frozen_finalist_labels"]["identities"]
        stamped = raw.get("protocol_sha256")
        if stamped is not None and not (stamped == protocol["sha256"]).all():
            raise SystemExit(
                "raw results were produced under a different protocol than "
                f"'{args.protocol}'; refusing to analyze them as confirmatory")

    summary = aggregate_objectives(raw, cfg, costs, burdens)
    frontier = pareto_frontier(summary)
    preferences = preference_scenarios(frontier, cfg)
    benchmarks = benchmark_portfolios(summary, cfg)
    stability = bootstrap_pareto_stability(
        raw, cfg, costs, burdens, n_boot=n_boot, seed=cfg.seed)
    errors = monte_carlo_error(raw, cfg)
    resolution = frontier_resolution_warning(summary, errors)

    frames = {
        "portfolio_objective_summary.csv": summary,
        "portfolio_pareto_frontier.csv": frontier,
        "portfolio_preference_scenarios.csv": preferences,
        "portfolio_pareto_stability.csv": stability,
        "portfolio_benchmark_comparison.csv": benchmarks,
        "portfolio_monte_carlo_error.csv": errors,
        "portfolio_frontier_resolution.csv": resolution,
    }
    if args.stage == "confirmation":
        frames["portfolio_full_space_vs_finalist.csv"] = (
            restricted_frontier_comparison(summary, finalists))

    written = []
    for name, frame in frames.items():
        path = output / name
        write_csv(frame, path)
        written.append(path)

    counts = {
        "evaluated_candidates_by_profile":
            raw.groupby("profile")["portfolio"].nunique().to_dict(),
        "scenarios_by_profile":
            raw.groupby("profile")["scenario_id"].nunique().to_dict(),
        "non_dominated_by_profile":
            frontier.groupby("profile")["pareto_efficient"].sum().to_dict(),
        "total_executions": int(len(raw)),
    }
    if args.stage == "confirmation":
        comparison = frames["portfolio_full_space_vs_finalist.csv"]
        counts["finalist_only_artifacts_by_profile"] = (
            comparison.groupby("profile")["finalist_only_artifact"]
            .sum().to_dict())
        counts["finalist_only_frontier_size_by_profile"] = (
            comparison.groupby("profile")["pareto_finalist_only"]
            .sum().to_dict())

    manifest = build_manifest(
        run_id=f"{args.stage}-analysis",
        stage="analysis",
        description=f"Six-objective analysis of the {args.stage} bank. "
                    "Cost and burden are normalized scenario points, not "
                    "dollars or measured staffing burden.",
        inputs=[args.config, "configs/defense_costs.yaml",
                "configs/defense_burdens.yaml", raw_path]
               + ([Path(protocol["path"])] if protocol else []),
        outputs=written,
        parameters={
            "analyzed_stage": args.stage,
            "bootstrap_samples": n_boot,
            "sustained_outage_primary_k":
                cfg.simulation.sustained_outage_min_services,
            "counts": counts,
        },
        protocol=({key: protocol[key]
                   for key in ("name", "path", "sha256", "frozen_at")}
                  if protocol else None),
    )
    manifest_path = write_manifest(
        manifest, output / f"{args.stage}_analysis_manifest.json")

    print(json.dumps(counts, indent=2))
    print(f"\nwrote {len(written)} tables to {output}")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()

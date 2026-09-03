#!/usr/bin/env python3
"""Freeze the confirmatory protocol as a content-addressed artifact.

Run this **before** any confirmatory simulation exists. It writes
``study/protocols/<name>.protocol.json``, whose own SHA-256 is stored inside
it, and refuses to overwrite an existing protocol. The confirmatory runner
will not start without a protocol that verifies, and it records the
protocol's digest in the raw results and in the run manifest.

Why this exists: the pre-rebuild holdout protocol was written by its own
runner on every invocation, contained no hash, commit, or timestamp, and
asserted ``"status": "frozen before holdout generation"`` about itself
(audit ISSUE-013). Nothing in the repository or its history distinguished a
genuine prospective freeze from a file written afterwards, so the
manuscript's claim that no candidate was added or removed after outcomes were
observed could not be checked by a reader. This makes the claim checkable.

Usage
-----
    python scripts/freeze_confirmatory_protocol.py \
        --name multiobjective_confirmatory_v1 \
        --trials 150
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.config import load_config
from grrc.endpoints import (ENDPOINTS, PARETO_OBJECTIVES,
                            SUSTAINED_OUTAGE_K_LADDER)
from grrc.multiobjective import (CONFIRMATORY_SEED,
                                 confirmatory_candidate_counts,
                                 select_holdout_candidates)
from grrc.provenance import freeze_protocol, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="multiobjective_confirmatory_v1")
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument("--discovery", default="data/multiobjective/discovery",
                        help="discovery outputs the finalist rule reads")
    parser.add_argument(
        "--trials", default="resource_constrained=350,"
                            "intermediate_capacity=250,high_capacity=800",
        help="per-profile scenario counts, or a single integer. The defaults "
             "come from the pilot precision analysis; see its report.")
    parser.add_argument("--threshold", type=float, default=0.50)
    parser.add_argument("--precision-report",
                        default="data/multiobjective/discovery/"
                                "precision_analysis.json",
                        help="pilot precision analysis justifying --trials")
    args = parser.parse_args()

    cfg = load_config(args.config)
    counts = confirmatory_candidate_counts(cfg)

    if "=" in str(args.trials):
        trials = {part.split("=")[0]: int(part.split("=")[1])
                  for part in str(args.trials).split(",")}
    else:
        trials = {name: int(args.trials) for name in cfg.optimization.profiles}
    missing = set(cfg.optimization.profiles) - set(trials)
    if missing:
        raise SystemExit(f"--trials is missing profiles: {sorted(missing)}")
    total_executions = sum(counts[name] * trials[name] for name in counts)

    # The finalist rule is frozen too, but it no longer decides *what gets
    # evaluated* — the confirmatory run covers the whole resolved space. It
    # decides only which candidates are labeled as discovery finalists, so
    # that the finalist-only frontier can be reported as a restricted view of
    # the same data and compared with the true frontier.
    discovery = Path(args.discovery)
    finalists = select_holdout_candidates(
        pd.read_csv(discovery / "portfolio_pareto_stability.csv"),
        pd.read_csv(discovery / "portfolio_preference_scenarios.csv"),
        pd.read_csv(discovery / "portfolio_benchmark_comparison.csv"),
        threshold=args.threshold)

    precision = None
    precision_path = Path(args.precision_report)
    if precision_path.exists():
        precision = json.loads(precision_path.read_text(encoding="utf-8"))

    body = {
        "study": "multi-objective hospital ransomware defense portfolios",
        "stage": "confirmation",
        "written_before_any_confirmatory_simulation": True,

        "estimands": [
            "For each capacity profile, the set of resolved candidate "
            "portfolios that are non-dominated on the six declared "
            "objectives, evaluated on a fresh paired scenario bank.",
            "The proportion of discovery-frontier candidates that remain "
            "non-dominated when the full resolved space is evaluated.",
            "The number of candidates that appear non-dominated within the "
            "frozen finalist subset but are dominated in the full space.",
        ],

        "candidate_space": {
            "rule": "every behaviorally distinct resolved candidate in each "
                    "profile, deduplicated under the study config",
            "counts_by_profile": counts,
            "total_profile_candidates": sum(counts.values()),
            "note": "This is the whole point of the confirmatory design. The "
                    "prior study evaluated 57 discovery-selected finalists "
                    "and reported the result as a frontier; a candidate that "
                    "was mediocre in discovery could not appear.",
        },

        "frozen_finalist_labels": {
            "purpose": "reporting only; does not restrict what is evaluated",
            "rule": "discovery bootstrap Pareto inclusion >= threshold, union "
                    "every declared preference choice and benchmark "
                    "comparator",
            "threshold": args.threshold,
            "counts_by_profile": {k: len(v) for k, v in finalists.items()},
            "identities": finalists,
        },

        "design": {
            "trials_per_candidate": trials,
            "total_executions": total_executions,
            "trials_rationale": (
                "Per-profile scenario counts, each set above the paired "
                "requirement the pilot precision analysis computed for that "
                "profile's most demanding objective. Pairing is within a "
                "profile, so nothing requires a common count, and the "
                "required count varies by more than a factor of two across "
                "profiles. Where a count still falls below a requirement, "
                "the affected objective is reported as under-resolved rather "
                "than presented as established."),
            "pairing": "common random numbers; all candidates in a profile "
                       "replay one scenario bank (topology, entry point, "
                       "patch draws, and event-level random fields)",
            "master_seed": CONFIRMATORY_SEED,
            "entry_point_cycle": list(cfg.experiment.entry_points),
            "config_sha256": sha256_file(args.config),
            "defense_costs_sha256": sha256_file("configs/defense_costs.yaml"),
            "defense_burdens_sha256": sha256_file(
                "configs/defense_burdens.yaml"),
        },

        "objectives": {
            name: {
                "direction": ENDPOINTS[name].direction,
                "definition": ENDPOINTS[name].definition,
                "identification": ENDPOINTS[name].identification,
            } for name in PARETO_OBJECTIVES
        },

        "endpoints": {
            "sustained_outage_primary_k":
                cfg.simulation.sustained_outage_min_services,
            "sustained_outage_service_steps":
                cfg.simulation.sustained_outage_service_steps,
            "sustained_outage_reported_k_ladder":
                list(SUSTAINED_OUTAGE_K_LADDER),
            "horizon_steps": cfg.simulation.max_steps,
            "step_minutes": cfg.simulation.step_minutes,
        },

        "analysis_plan": {
            "dominance": "no other candidate is no worse on all six "
                         "objectives and strictly better on at least one",
            "tie_tolerance": "exact float comparison; objectives are not "
                             "rounded before dominance is evaluated",
            "stability": "1000 paired scenario bootstraps, resampling whole "
                         "scenario identifiers so cross-portfolio "
                         "correlation is preserved",
            "monte_carlo_error": "reported for every objective as a standard "
                                 "error over the paired scenario bank",
            "preference_scenarios": "declared weight sets applied after the "
                                    "frontier is built, never before",
            "reported_candidate_counts": "stated at every stage: enumerated, "
                                         "resolved, evaluated, non-dominated",
        },

        "prespecified_sensitivity": [
            "sustained-outage k over 1..4, reported in every results table",
            "cost scaling over the declared scale factors",
            "finalist-only versus full-space frontier comparison",
        ],

        "precision_justification": precision or {
            "status": "no pilot precision analysis found at "
                      f"{args.precision_report}",
            "note": "trials_per_candidate is then a declared round number, "
                    "which the manuscript must say plainly.",
        },

        "stopping_rule": "the confirmatory bank is run once, in full. "
                         "Individual cells are never rerun. If the run fails "
                         "part way, it is restarted from the beginning under "
                         "the same seed and the failure is recorded in "
                         "study/DEVIATIONS.md.",
    }

    identity = freeze_protocol(args.name, body)
    print(f"froze protocol '{identity['name']}'")
    print(f"  path        {identity['path']}")
    print(f"  sha256      {identity['sha256']}")
    print(f"  frozen at   {identity['frozen_at']}")
    for name in sorted(counts):
        print(f"  {name:24s} {counts[name]:4d} candidates x "
              f"{trials[name]:4d} scenarios = "
              f"{counts[name] * trials[name]:,} executions")
    print(f"  {'total':24s} {total_executions:,} executions")


if __name__ == "__main__":
    main()

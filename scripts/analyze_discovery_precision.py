#!/usr/bin/env python3
"""Pilot precision analysis: justify the confirmatory scenario count.

The handoff requires that the number of simulations be justified by a
precision target rather than by a round number. This script reads the
discovery bank and answers one question per objective: **how many paired
scenarios per candidate are needed for the Monte Carlo standard error to be
small relative to the spread the frontier has to resolve?**

Method
------
For each profile and objective, using the paired discovery bank:

1. Estimate the per-scenario standard deviation of the objective, pooled
   across candidates. For the two probability endpoints this is the binomial
   ``sqrt(p(1-p))`` evaluated at the pooled rate, which is conservative
   because it is maximized near 0.5.
2. Take the *resolution target* to be a fraction of the interquartile range
   of candidate means within the profile. Two candidates closer together than
   the Monte Carlo error cannot be reliably ordered, so the target is the
   separation the frontier actually needs to distinguish.
3. Solve ``n >= (sd / target)^2`` for the required scenario count.

Because the design is paired, the *difference* between two candidates on a
shared scenario bank is far better estimated than either mean alone. The
script therefore reports both the unpaired requirement and the paired one,
computed from the observed within-scenario correlation between candidates.
The paired figure is the one that governs a frontier comparison; the unpaired
figure governs a standalone reported mean.

The output is written as JSON and embedded verbatim in the frozen
confirmatory protocol, so the scenario count is on the record as a
justified quantity before any confirmatory data exist.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.config import load_config, load_defense_costs
from grrc.endpoints import ENDPOINTS, PARETO_OBJECTIVES, sustained_outage_column
from grrc.multiobjective import aggregate_objectives, load_operational_burdens

#: Objectives that vary by scenario. Cost and burden are deterministic
#: functions of the portfolio, so they carry no Monte Carlo error at all.
STOCHASTIC_OBJECTIVES = tuple(
    name for name in PARETO_OBJECTIVES
    if ENDPOINTS[name].identification != "normalized-scenario-unit")

#: Fraction of the candidate-mean interquartile range that the Monte Carlo
#: standard error must not exceed. Declared here, before the numbers are
#: seen, so the target is not chosen to flatter the answer.
RESOLUTION_FRACTION = 0.10


def trial_column(objective: str, cfg) -> str:
    """Raw per-trial column underlying an aggregated objective."""
    return {
        "mean_hours_lost": "weighted_service_hours_lost",
        "tail_hours_lost_cvar90": "weighted_service_hours_lost",
        "sustained_outage_probability": sustained_outage_column(
            cfg.simulation.sustained_outage_min_services),
        "nonrecovery_probability": "recovered_within_horizon",
    }[objective]


def analyze(raw: pd.DataFrame, summary: pd.DataFrame, cfg) -> dict:
    report: dict = {
        "method": __doc__.split("Method")[0].strip(),
        "resolution_fraction_of_iqr": RESOLUTION_FRACTION,
        "scenarios_per_candidate_in_pilot": int(
            raw.groupby("profile")["scenario_id"].nunique().min()),
        "profiles": {},
    }
    for profile, group in raw.groupby("profile", sort=True):
        prof_summary = summary[summary["profile"] == profile]
        names = sorted(group["portfolio"].unique())
        scenarios = np.sort(group["scenario_id"].unique())
        entry: dict = {
            "candidates": len(names),
            "pilot_scenarios": len(scenarios),
            "objectives": {},
        }
        for objective in STOCHASTIC_OBJECTIVES:
            column = trial_column(objective, cfg)
            matrix = (group.pivot_table(index="portfolio",
                                        columns="scenario_id",
                                        values=column, aggfunc="mean")
                      .reindex(index=names, columns=scenarios)
                      .to_numpy(float))
            if np.isnan(matrix).any():
                raise ValueError(
                    f"{profile}/{objective}: paired matrix has missing cells")

            # Per-scenario spread, pooled across candidates.
            per_candidate_sd = matrix.std(axis=1, ddof=1)
            sd = float(np.sqrt((per_candidate_sd ** 2).mean()))

            candidate_means = prof_summary[objective].to_numpy(float)
            iqr = float(np.subtract(*np.percentile(candidate_means, [75, 25])))
            target = RESOLUTION_FRACTION * iqr

            # Paired: variance of the difference between two candidates on a
            # shared bank, averaged over candidate pairs via the mean
            # within-scenario correlation.
            centered = matrix - matrix.mean(axis=1, keepdims=True)
            scale = per_candidate_sd.copy()
            scale[scale == 0] = np.nan
            standardized = centered / scale[:, None]
            with np.errstate(invalid="ignore"):
                correlation = np.nanmean(
                    (standardized @ standardized.T) / (matrix.shape[1] - 1))
            correlation = float(np.clip(np.nan_to_num(correlation), -1.0, 1.0))
            paired_sd = float(sd * np.sqrt(max(0.0, 2.0 * (1.0 - correlation))))

            def required(spread: float) -> int | None:
                if target <= 0 or spread <= 0:
                    return None
                return int(np.ceil((spread / target) ** 2))

            entry["objectives"][objective] = {
                "per_scenario_sd": sd,
                "candidate_mean_iqr": iqr,
                "resolution_target": target,
                "mean_within_scenario_correlation": correlation,
                "paired_difference_sd": paired_sd,
                "required_scenarios_unpaired": required(sd),
                "required_scenarios_paired": required(paired_sd),
                "achieved_mc_se_at_pilot_n": (
                    sd / np.sqrt(len(scenarios)) if len(scenarios) else None),
            }
        report["profiles"][profile] = entry

    # The binding requirement across every profile and objective.
    requirements = [
        obj["required_scenarios_paired"]
        for prof in report["profiles"].values()
        for obj in prof["objectives"].values()
        if obj["required_scenarios_paired"] is not None]
    unpaired = [
        obj["required_scenarios_unpaired"]
        for prof in report["profiles"].values()
        for obj in prof["objectives"].values()
        if obj["required_scenarios_unpaired"] is not None]
    report["binding_requirement"] = {
        "paired_max": max(requirements) if requirements else None,
        "unpaired_max": max(unpaired) if unpaired else None,
        "interpretation": (
            "The paired figure governs frontier comparisons, which are what "
            "the study reports; the unpaired figure governs any standalone "
            "mean quoted on its own. Where the chosen scenario count is "
            "below a requirement, the affected objective is under-resolved "
            "and the manuscript must say so rather than presenting its "
            "differences as established."),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw", default="data/multiobjective/discovery/discovery_results.csv")
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument(
        "--output",
        default="data/multiobjective/discovery/precision_analysis.json")
    args = parser.parse_args()

    cfg = load_config(args.config)
    costs = load_defense_costs("configs/defense_costs.yaml")
    burdens = load_operational_burdens("configs/defense_burdens.yaml")
    raw = pd.read_csv(args.raw)
    summary = aggregate_objectives(raw, cfg, costs, burdens)

    report = analyze(raw, summary, cfg)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"pilot scenarios per candidate: "
          f"{report['scenarios_per_candidate_in_pilot']}")
    for profile, entry in report["profiles"].items():
        print(f"\n{profile}  ({entry['candidates']} candidates)")
        for name, stats in entry["objectives"].items():
            print(f"  {name:32s} sd={stats['per_scenario_sd']:9.3f} "
                  f"corr={stats['mean_within_scenario_correlation']:+.3f} "
                  f"n_paired={stats['required_scenarios_paired']} "
                  f"n_unpaired={stats['required_scenarios_unpaired']}")
    print(f"\nbinding paired requirement: "
          f"{report['binding_requirement']['paired_max']}")
    print(f"binding unpaired requirement: "
          f"{report['binding_requirement']['unpaired_max']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

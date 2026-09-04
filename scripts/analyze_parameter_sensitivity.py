#!/usr/bin/env python3
"""Variance-based sensitivity to the unidentified coefficients.

Because every trial records the parameter vector its scenario drew, a global
sensitivity analysis costs no extra simulation at all: the confirmatory bank
is already a Monte Carlo sample over the declared ranges, and the question
"which unidentified coefficient moves the answer" is a question about
variance decomposition within data that already exist.

Two quantities are reported per objective.

**First-order effect.** The share of an objective's variance explained by one
parameter alone, estimated by binning scenarios on that parameter's drawn
value and comparing the between-bin variance of the objective's
scenario-level mean against its total variance. This is a standard
correlation-ratio estimator of the first-order Sobol index, and it needs no
special sampling design — which matters, because the design here was fixed
before this analysis existed.

**Rank stability.** More decision-relevant than variance: does the *frontier*
change across the parameter's range? Candidates are ranked by each objective
within the low and high thirds of the parameter, and the two rankings are
compared by Spearman correlation. A parameter can move every objective
substantially while leaving the ordering of portfolios untouched, in which
case the decision is robust to it even though the numbers are not.

The distinction matters for how a result should be read. A parameter with a
large first-order effect and a rank correlation near one tells the reader
"the level is uncertain, the choice is not". One with a low rank correlation
tells them the opposite, and that is the one to report loudly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.config import load_config
from grrc.endpoints import sustained_outage_column
from grrc.provenance import build_manifest, write_manifest

#: Objectives that vary with the parameters. Cost and burden are
#: deterministic functions of the portfolio and cannot move.
OBJECTIVE_COLUMNS = {
    "mean_hours_lost": "weighted_service_hours_lost",
    "nonrecovery_probability": "recovered_within_horizon",
}

#: Bins used for the correlation-ratio estimator. Enough to resolve a
#: monotone effect, few enough that each bin holds many scenarios.
N_BINS = 8


def first_order_effect(scenario_values: np.ndarray,
                       parameter: np.ndarray) -> float:
    """Correlation ratio of an objective on one parameter, in [0, 1]."""
    total_variance = float(np.var(scenario_values))
    if total_variance <= 0:
        return 0.0
    edges = np.quantile(parameter, np.linspace(0, 1, N_BINS + 1))
    edges[-1] += 1e-12
    bins = np.clip(np.digitize(parameter, edges[1:-1]), 0, N_BINS - 1)
    grand = scenario_values.mean()
    between = 0.0
    for b in range(N_BINS):
        mask = bins == b
        if not mask.any():
            continue
        between += mask.sum() * (scenario_values[mask].mean() - grand) ** 2
    between /= len(scenario_values)
    return float(np.clip(between / total_variance, 0.0, 1.0))


def rank_stability(frame: pd.DataFrame, objective_column: str,
                   parameter_column: str) -> float:
    """Spearman correlation of candidate rankings between low and high thirds."""
    low_cut, high_cut = frame[parameter_column].quantile([1 / 3, 2 / 3])
    low = frame[frame[parameter_column] <= low_cut]
    high = frame[frame[parameter_column] >= high_cut]
    if low.empty or high.empty:
        return float("nan")
    low_rank = low.groupby("portfolio")[objective_column].mean().rank()
    high_rank = high.groupby("portfolio")[objective_column].mean().rank()
    shared = low_rank.index.intersection(high_rank.index)
    if len(shared) < 3:
        return float("nan")
    return float(low_rank[shared].corr(high_rank[shared], method="spearman"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        default="data/multiobjective/confirmatory/"
                "multiobjective_confirmatory_results.csv")
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument(
        "--out", default="data/multiobjective/confirmatory")
    args = parser.parse_args()

    cfg = load_config(args.config)
    raw = pd.read_csv(args.raw)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    parameters = sorted(c for c in raw.columns if c.startswith("param_"))
    if not parameters:
        raise SystemExit(
            f"{args.raw} records no parameter draws; parameter uncertainty "
            "was disabled for that run, so there is nothing to decompose")

    objectives = dict(OBJECTIVE_COLUMNS)
    objectives["sustained_outage_probability"] = sustained_outage_column(
        cfg.simulation.sustained_outage_min_services)

    rows: list[dict[str, object]] = []
    for profile, group in raw.groupby("profile", sort=True):
        for objective, column in objectives.items():
            values = group[column].astype(float)
            if objective == "nonrecovery_probability":
                values = 1.0 - values
            work = group.assign(_objective=values)
            # Scenario-level means: the parameter vector is constant within a
            # scenario, so the scenario is the unit of parameter variation.
            scenario_mean = work.groupby("scenario_id")["_objective"].mean()
            for parameter in parameters:
                per_scenario = work.groupby("scenario_id")[parameter].first()
                aligned = scenario_mean.reindex(per_scenario.index)
                rows.append({
                    "profile": profile,
                    "objective": objective,
                    "parameter": parameter.removeprefix("param_"),
                    "first_order_effect": first_order_effect(
                        aligned.to_numpy(float),
                        per_scenario.to_numpy(float)),
                    "rank_stability_spearman": rank_stability(
                        work, "_objective", parameter),
                    "scenarios": int(len(per_scenario)),
                })

    frame = pd.DataFrame(rows)
    path = out / "parameter_sensitivity.csv"
    frame.to_csv(path, index=False)

    dominant = (frame.sort_values("first_order_effect", ascending=False)
                .groupby(["profile", "objective"]).head(1))
    summary = {
        "parameters_sampled": len(parameters),
        "method": "correlation-ratio first-order effect on scenario means; "
                  "Spearman rank stability between the low and high thirds "
                  "of each parameter",
        "dominant_parameter_by_profile_objective": [
            {"profile": r.profile, "objective": r.objective,
             "parameter": r.parameter,
             "first_order_effect": round(r.first_order_effect, 4),
             "rank_stability": (None if np.isnan(r.rank_stability_spearman)
                                else round(r.rank_stability_spearman, 4))}
            for r in dominant.itertuples()],
        "worst_rank_stability": (
            None if frame["rank_stability_spearman"].isna().all()
            else round(float(frame["rank_stability_spearman"].min()), 4)),
        "interpretation": (
            "A large first-order effect with rank stability near 1 means the "
            "level of an objective is uncertain while the ordering of "
            "portfolios is not, so the decision is robust to that parameter "
            "even though the number is not. Low rank stability means the "
            "opposite, and is the case that must be reported loudly."),
    }
    summary_path = out / "parameter_sensitivity_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    manifest = build_manifest(
        run_id="parameter-sensitivity", stage="analysis",
        description="Variance-based sensitivity to the unidentified "
                    "coefficients, decomposed from the confirmatory bank's "
                    "own recorded parameter draws.",
        inputs=[args.config, args.raw], outputs=[path, summary_path],
        parameters={"parameters_sampled": len(parameters), "bins": N_BINS})
    write_manifest(manifest, out / "parameter_sensitivity_manifest.json")

    print(json.dumps(summary, indent=2))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()

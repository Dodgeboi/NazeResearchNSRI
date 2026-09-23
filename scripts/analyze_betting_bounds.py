#!/usr/bin/env python3
"""Execute BETTING_BOUNDS_PLAN.md against the unchanged confirmation bank.

Adds a finite-sample betting confidence bound (Waudby-Smith and Ramdas, 2023)
as a fourth one-sided simultaneous margin family, and recomputes the three
frozen families on the identical contrasts and error allocation so all four are
reported side by side. This does not replace the release 3.2.0 final comparison.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.betting import betting_margins
from grrc.comparison import comparison_margins
from grrc.config import load_config, load_defense_costs
from grrc.defenses import enumerate_portfolios
from grrc.interpretation import make_bank, stratum_indices
from grrc.joint_stability import (portfolio_features, tariff_pair_minima,
                                  sufficient_population_retention)
from grrc.multiobjective import load_operational_burdens
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ["resource_constrained", "intermediate_capacity", "high_capacity"]
# The betting family is finite-sample valid, like the two concentration bounds;
# the paired t remains an approximation.
METHODS = ["hoeffding", "empirical_bernstein", "paired_t_approx", "betting"]
FINITE_SAMPLE = {"hoeffding", "empirical_bernstein", "betting"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/betting_bounds"
    out.mkdir(exist_ok=True)
    cfgpath = ROOT / "configs/multiobjective_portfolio.yaml"
    costpath, burdenpath = [ROOT / f"configs/defense_{s}.yaml" for s in ["costs", "burdens"]]
    rawpath = ROOT / "data/multiobjective/confirmatory/multiobjective_confirmatory_results.csv"
    summarypath = rawpath.parent / "portfolio_objective_summary.csv"
    columns = ["profile", "portfolio", "scenario_id", "paired", "entry_point",
               "weighted_service_hours_lost", "recovered_within_horizon"] + [
        f"sustained_clinical_outage_k{k}" for k in range(1, 5)]
    raw, summary = pd.read_csv(rawpath, usecols=columns), pd.read_csv(summarypath)
    cfg = load_config(cfgpath)
    costs, burdens = load_defense_costs(costpath), load_operational_burdens(burdenpath)
    portfolios = {p.name: p for p in enumerate_portfolios()}
    banks = [make_bank(raw, summary, p, []) for p in PROFILES]
    family = 3 * sum(len(b.names) * (len(b.names) - 1) for b in banks)
    if family != 276048:
        raise AssertionError("planned 276,048 ordered contrasts required")
    bound = cfg.simulation.max_steps * cfg.simulation.step_minutes / 60 * sum(
        cfg.service_weights.as_dict().values())
    results = {name: [] for name in ["bound_margins", "baseline_comparisons",
                                     "bound_retention", "bound_candidates"]}
    for bank in banks:
        groups = stratum_indices(bank)
        if [len(g) for g in groups] != [80] * 5:
            raise AssertionError("planned five strata of 80 required")
        features = np.array([portfolio_features(portfolios[n], cfg.profiles[bank.profile])
                             for n in bank.names])
        prices = {r: tariff_pair_minima(features, costs, burdens, r, True) for r in [0, .5]}
        baseline = np.flatnonzero((bank.static == 0).all(1))
        if len(baseline) != 1:
            raise AssertionError("one free baseline required")
        baseline = int(baseline[0])
        offdiag = ~np.eye(len(bank.names), dtype=bool)
        means, widths = [], {m: [] for m in METHODS}
        for objective, a, b, limit in [
                ("mean_loss", bank.loss, bank.loss, bound),
                ("outage_k4_minus_k1", bank.outage[:, :, 3], bank.outage[:, :, 0], 1),
                ("nonrecovery", bank.nonrecovery, bank.nonrecovery, 1)]:
            mean, concentration = comparison_margins(a, b, groups, observation_bound=limit,
                                                     family_size=family)
            betting_mean, betting_width = betting_margins(a, b, observation_bound=limit,
                                                          family_size=family)
            if not np.allclose(mean, betting_mean):
                raise AssertionError("paired means must agree across families")
            margins = {**concentration, "betting": betting_width}
            means.append(mean)
            for method in METHODS:
                w = margins[method]
                if (w < -1e-9).any():
                    raise AssertionError("one-sided margins must be nonnegative")
                widths[method].append(w)
                results["bound_margins"].append(dict(
                    profile=bank.profile, method=method, objective=objective,
                    family_size=family, alpha=.05, minimum=float(w[offdiag].min()),
                    median=float(np.median(w[offdiag])), maximum=float(w[offdiag].max())))
                if objective == "mean_loss":
                    lower = mean - w
                    if (lower[offdiag] > mean[offdiag] + 1e-9).any():
                        raise AssertionError("lower bound must not exceed the point mean")
                    for candidate, name in enumerate(bank.names):
                        if candidate == baseline:
                            continue
                        results["baseline_comparisons"].append(dict(
                            profile=bank.profile, method=method, portfolio=name,
                            baseline=bank.names[baseline],
                            mean_benefit=mean[baseline, candidate],
                            margin=w[baseline, candidate],
                            lower_benefit=mean[baseline, candidate] - w[baseline, candidate],
                            family_size=family, alpha=.05))
        means = np.stack(means, axis=-1)
        for method in METHODS:
            lower = means - np.stack(widths[method], axis=-1)
            for radius, price in prices.items():
                mask = sufficient_population_retention(lower, price)
                results["bound_retention"].append(dict(
                    profile=bank.profile, method=method, radius=radius, alpha=.05,
                    retained=int(mask.sum()),
                    purchased_retained=int(mask.sum() - mask[baseline]), family_size=family,
                    interpretation="finite_sample" if method in FINITE_SAMPLE else "approximate"))
                for candidate, name in enumerate(bank.names):
                    results["bound_candidates"].append(dict(
                        profile=bank.profile, method=method, radius=radius, portfolio=name,
                        retained=bool(mask[candidate]), free_baseline=candidate == baseline))
        print(bank.profile, "four-family bounds and retention complete", flush=True)
    outputs = []
    for name, rows in results.items():
        path = out / (name + ".csv")
        write_csv(pd.DataFrame(rows), path)
        outputs.append(path)
    inputs = [Path(__file__), cfgpath, costpath, burdenpath, rawpath, summarypath,
              ROOT / "study/BETTING_BOUNDS_PLAN.md"] + [
        ROOT / ("src/grrc/" + name + ".py") for name in
        ["betting", "comparison", "config", "defenses", "interpretation",
         "joint_stability", "multiobjective", "provenance", "utilities"]]
    manifest = build_manifest(
        run_id="betting-bounds", stage="analysis",
        description="Finite-sample betting confidence bound compared to the three frozen "
                    "one-sided simultaneous margin families on the same contrast bank.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(alpha=.05, family_size=family, loss_bound=bound, methods=METHODS,
                        price_radii=[0, .5], price_region="positive_gaps",
                        betting_fraction_grid="geomspace(1e-3, 0.9, 15)", bisection_steps=30,
                        scope="retrospective; finite-sample validity is the only claimed "
                              "property; widths versus other families are reported, not assumed"))
    write_manifest(manifest, out / "betting_bounds_manifest.json")
    print(pd.DataFrame(results["bound_retention"]).to_string(index=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Execute FINAL_COMPARISON_PLAN.md against the unchanged confirmation bank."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.comparison import comparison_margins, conditional_indices
from grrc.config import load_config, load_defense_costs
from grrc.defenses import enumerate_portfolios
from grrc.frontier_certificates import certify_frontier
from grrc.interpretation import make_bank, stratum_indices
from grrc.joint_stability import (portfolio_features, tariff_pair_minima,
    guaranteed_with_shared_tariffs, sufficient_population_retention)
from grrc.multiobjective import load_operational_burdens, pareto_mask
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ["resource_constrained", "intermediate_capacity", "high_capacity"]
METHODS = ["hoeffding", "empirical_bernstein", "paired_t_approx"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/final_comparison"
    out.mkdir(exist_ok=True)
    cfgpath = ROOT / "configs/multiobjective_portfolio.yaml"
    costpath, burdenpath = [ROOT / f"configs/defense_{s}.yaml" for s in ["costs", "burdens"]]
    rawpath = ROOT / "data/multiobjective/confirmatory/multiobjective_confirmatory_results.csv"
    summarypath = rawpath.parent / "portfolio_objective_summary.csv"
    parameters = sorted(c for c in pd.read_csv(rawpath, nrows=0) if c.startswith("param_"))
    if len(parameters) != 10:
        raise AssertionError("planned ten recorded coefficients required")
    columns = ["profile", "portfolio", "scenario_id", "paired", "entry_point",
        "weighted_service_hours_lost", "recovered_within_horizon"] + [
        f"sustained_clinical_outage_k{k}" for k in range(1, 5)] + parameters
    raw, summary = pd.read_csv(rawpath, usecols=columns), pd.read_csv(summarypath)
    cfg = load_config(cfgpath)
    costs, burdens = load_defense_costs(costpath), load_operational_burdens(burdenpath)
    portfolios = {p.name: p for p in enumerate_portfolios()}
    banks = [make_bank(raw, summary, p, []) for p in PROFILES]
    family = 3 * sum(len(b.names) * (len(b.names)-1) for b in banks)
    bound = cfg.simulation.max_steps * cfg.simulation.step_minutes / 60 * sum(cfg.service_weights.as_dict().values())
    results = {name: [] for name in ["bound_retention", "bound_margins", "baseline_comparisons",
        "bound_candidates", "coefficient_regimes", "regime_candidates", "regime_membership", "matched_subsets"]}
    for pindex, bank in enumerate(banks):
        groups = stratum_indices(bank)
        if [len(g) for g in groups] != [80]*5:
            raise AssertionError("planned five strata of 80 required")
        features = np.array([portfolio_features(portfolios[n], cfg.profiles[bank.profile]) for n in bank.names])
        prices = {r: tariff_pair_minima(features, costs, burdens, r, True) for r in [0, .5]}
        reference = pareto_mask(bank.objectives())
        low = bank.objectives()
        upper = low.copy(); upper[:, 2] = bank.outage[:, :, 0].mean(0)
        endpoint_ref = certify_frontier(low, upper).guaranteed
        baseline = np.flatnonzero((bank.static == 0).all(1))
        if len(baseline) != 1:
            raise AssertionError("one free baseline required")
        baseline = int(baseline[0])
        means, widths = [], {m: [] for m in METHODS}
        for objective, a, b, limit in [("mean_loss", bank.loss, bank.loss, bound),
            ("outage_k4_minus_k1", bank.outage[:, :, 3], bank.outage[:, :, 0], 1),
            ("nonrecovery", bank.nonrecovery, bank.nonrecovery, 1)]:
            mean, margins = comparison_margins(a, b, groups, observation_bound=limit, family_size=family)
            means.append(mean)
            offdiag = ~np.eye(len(bank.names), dtype=bool)
            for method in METHODS:
                w = margins[method]
                widths[method].append(w)
                results["bound_margins"].append(dict(profile=bank.profile, method=method,
                    objective=objective, family_size=family, alpha=.05,
                    minimum=float(w[offdiag].min()), median=float(np.median(w[offdiag])),
                    maximum=float(w[offdiag].max())))
                if objective == "mean_loss":
                    for candidate, name in enumerate(bank.names):
                        if candidate == baseline: continue
                        results["baseline_comparisons"].append(dict(profile=bank.profile, method=method,
                            portfolio=name, baseline=bank.names[baseline], mean_benefit=mean[baseline, candidate],
                            margin=w[baseline, candidate], lower_benefit=mean[baseline, candidate]-w[baseline, candidate],
                            family_size=family, alpha=.05))
        means = np.stack(means, axis=-1)
        for method in METHODS:
            lower = means - np.stack(widths[method], axis=-1)
            for radius, price in prices.items():
                mask = sufficient_population_retention(lower, price)
                results["bound_retention"].append(dict(profile=bank.profile, method=method, radius=radius,
                    alpha=.05, retained=int(mask.sum()), purchased_retained=int(mask.sum()-mask[baseline]),
                    family_size=family, interpretation="approximate" if method == "paired_t_approx" else "finite_sample"))
                for candidate, name in enumerate(bank.names):
                    results["bound_candidates"].append(dict(profile=bank.profile, method=method, radius=radius,
                        portfolio=name, retained=bool(mask[candidate]), free_baseline=candidate == baseline))
        parameter_groups = raw.loc[raw.profile == bank.profile].groupby("scenario_id")[parameters]
        if not parameter_groups.nunique(dropna=False).eq(1).all().all():
            raise AssertionError("parameter vector must be shared across all candidates")
        parameter_bank = parameter_groups.first().reindex(bank.scenarios)
        if not np.isfinite(parameter_bank.to_numpy(float)).all():
            raise AssertionError("finite aligned coefficient vectors required")

        def evaluate(selection):
            objective = bank.objectives(draw=selection)
            frontier = pareto_mask(objective)
            upper = objective.copy(); upper[:, 2] = bank.outage[selection, :, 0].mean(0)
            certificate = certify_frontier(objective, upper).guaranteed
            joint = guaranteed_with_shared_tariffs(objective[:, :4], upper[:, :4], prices[.5])
            metrics = dict(scenarios=len(selection), frontier=int(frontier.sum()),
                jaccard=float((frontier & reference).sum() / (frontier | reference).sum()),
                removed=int((reference & ~frontier).sum()), added=int((frontier & ~reference).sum()),
                original_frontier=int(reference.sum()), endpoint_guaranteed=int(certificate.sum()),
                original_endpoint_retained=int((certificate & endpoint_ref).sum()),
                joint_guaranteed=int(joint.sum()), original_joint_retained=int((joint & endpoint_ref).sum()))
            return metrics, objective, frontier, certificate, joint

        for parameter in parameters:
            for side in ["low", "high"]:
                selection = conditional_indices(parameter_bank[parameter].to_numpy(), groups, side == "high")
                metrics, objectives, front, cert, joint = evaluate(selection)
                key = dict(profile=bank.profile, parameter=parameter.removeprefix("param_"), side=side)
                results["coefficient_regimes"].append(dict(**key, **metrics))
                for i in selection:
                    results["regime_membership"].append(dict(**key, scenario_id=int(bank.scenarios[i]),
                        entry_point=bank.strata[i], parameter_value=parameter_bank.iloc[i][parameter]))
                for i, name in enumerate(bank.names):
                    results["regime_candidates"].append(dict(**key, portfolio=name, frontier=bool(front[i]),
                        endpoint_guaranteed=bool(cert[i]), joint_guaranteed=bool(joint[i]),
                        **dict(zip(["mean_loss", "tail_loss", "outage_k4", "nonrecovery", "cost", "burden"], objectives[i]))))
        rng = np.random.default_rng(2026090700+pindex)
        for draw in range(1000):
            selection = np.concatenate([rng.choice(g, 26, replace=False) for g in groups])
            metrics, *_ = evaluate(selection)
            results["matched_subsets"].append(dict(profile=bank.profile, draw=draw, **metrics))
        print(bank.profile, "bounds, 20 coefficient regimes, 1000 matched subsets complete", flush=True)
    controls = pd.DataFrame(results["matched_subsets"])
    for row in results["coefficient_regimes"]:
        group = controls.loc[controls.profile == row["profile"]]
        row["matched_jaccard_q025"] = float(group.jaccard.quantile(.025))
        row["matched_jaccard_median"] = float(group.jaccard.median())
        row["matched_jaccard_q975"] = float(group.jaccard.quantile(.975))
        row["matched_fraction_at_most_regime_jaccard"] = float((group.jaccard <= row["jaccard"]).mean())
    outputs = []
    for name, rows in results.items():
        path = out / (name + ".csv")
        write_csv(pd.DataFrame(rows), path); outputs.append(path)
    inputs = [Path(__file__), cfgpath, costpath, burdenpath, rawpath, summarypath,
        ROOT / "study/FINAL_COMPARISON_PLAN.md"] + [ROOT / ("src/grrc/" + name + ".py") for name in
        ["comparison", "config", "defenses", "frontier_certificates", "interpretation", "joint_stability",
         "multiobjective", "provenance", "utilities"]]
    manifest = build_manifest(run_id="final-comparison", stage="analysis",
        description="Same-family bound comparison and coefficient-conditioned frontier retention with matched-size references.",
        inputs=inputs, outputs=outputs, source_state=state, parameters=dict(alpha=.05, family_size=family,
            loss_bound=bound, methods=METHODS, price_radii=[0, .5], price_region="positive_gaps",
            coefficients=parameters, per_stratum_selection=26, matched_subsets=1000,
            seed=2026090700, scope="retrospective; conditional regimes are not interventions; paired t is approximate"))
    write_manifest(manifest, out / "comparison_manifest.json")
    print(pd.DataFrame(results["bound_retention"]).to_string(index=False))
    print(pd.DataFrame(results["coefficient_regimes"]).groupby("profile").jaccard.agg(["min", "median", "max"]).to_string())


if __name__ == "__main__":
    main()

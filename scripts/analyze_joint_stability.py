#!/usr/bin/env python3
"""Run the recorded joint tariff, endpoint, and sampling analysis."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.config import load_config, load_defense_costs
from grrc.defenses import enumerate_portfolios
from grrc.interpretation import make_bank, stratum_indices
from grrc.joint_stability import (portfolio_features, tariff_pair_minima,
    guaranteed_with_shared_tariffs, hoeffding_lower_differences,
    sufficient_population_retention)
from grrc.multiobjective import load_operational_burdens
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ["resource_constrained", "intermediate_capacity", "high_capacity"]
RADII = [0, .10, .25, .50, .75]
SETTINGS = [(family, radius) for family in ["monotone", "positive_gaps"] for radius in RADII]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--draws", type=int, default=1000)
    args = parser.parse_args()
    if args.draws < 2:
        raise SystemExit("at least two resamples required")
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT/"data/joint_stability"
    out.mkdir(exist_ok=True)
    inputs = [Path(__file__), ROOT/"src/grrc/joint_stability.py",
        ROOT/"src/grrc/interpretation.py", ROOT/"src/grrc/defenses.py",
        ROOT/"src/grrc/multiobjective.py", ROOT/"src/grrc/config.py",
        ROOT/"src/grrc/provenance.py", ROOT/"src/grrc/utilities.py",
        ROOT/"study/JOINT_STABILITY_PLAN.md", ROOT/"study/JOINT_STABILITY_EXTENSION.md"]
    configpath = ROOT/"configs/multiobjective_portfolio.yaml"
    costpath = ROOT/"configs/defense_costs.yaml"
    burdenpath = ROOT/"configs/defense_burdens.yaml"
    rawpath = ROOT/"data/multiobjective/confirmatory/multiobjective_confirmatory_results.csv"
    summarypath = rawpath.parent/"portfolio_objective_summary.csv"
    originalpath = ROOT/"data/frontier_certificates/hospital_candidates.csv"
    inputs += [configpath, costpath, burdenpath, rawpath, summarypath, originalpath]
    cfg = load_config(configpath)
    costs, burdens = load_defense_costs(costpath), load_operational_burdens(burdenpath)
    columns = ["profile", "portfolio", "scenario_id", "paired", "entry_point",
        "weighted_service_hours_lost", "recovered_within_horizon"] + [
        f"sustained_clinical_outage_k{k}" for k in range(1, 5)]
    raw, summary = pd.read_csv(rawpath, usecols=columns), pd.read_csv(summarypath)
    banks = [make_bank(raw, summary, p, []) for p in PROFILES]
    original = pd.read_csv(originalpath)
    portfolios = {p.name: p for p in enumerate_portfolios()}
    family = 3 * sum(len(b.names)*(len(b.names)-1) for b in banks)
    # The original endpoint is the weighted sum of unavailable service time.
    loss_bound = cfg.simulation.max_steps * cfg.simulation.step_minutes / 60 * sum(
        cfg.service_weights.as_dict().values())
    point_rows, boot_rows, candidate_rows, population_rows = [], [], [], []
    for p, bank in enumerate(banks):
        features = np.array([portfolio_features(portfolios[n], cfg.profiles[bank.profile])
                             for n in bank.names])
        prices = [tariff_pair_minima(features, costs, burdens, r, family == "positive_gaps")
                  for family, r in SETTINGS]
        ref = original.loc[original.profile == bank.profile].set_index("portfolio").loc[
            bank.names, "guaranteed"].to_numpy(bool)
        low = bank.objectives(k=4)[:, :4]
        upper = low.copy()
        upper[:, 2] = bank.outage[:, :, 0].mean(0)
        point = [guaranteed_with_shared_tariffs(low, upper, t) for t in prices]
        if any(not np.array_equal(point[i], ref) for i in [0, len(RADII)]):
            raise AssertionError("zero-radius result differs from original endpoint certificate")
        if any((point[i+1] & ~point[i]).any() for start in [0, len(RADII)]
               for i in range(start, start+len(RADII)-1)):
            raise AssertionError("nested tariff sets increased guaranteed retention")
        if any((point[i] & ~point[i+len(RADII)]).any() for i in range(len(RADII))):
            raise AssertionError("positive-gap region lost a broader-region certificate")
        for (family_name, radius), mask in zip(SETTINGS, point):
            point_rows.append(dict(profile=bank.profile, price_region=family_name, radius=radius,
                guaranteed=int(mask.sum()), original_endpoint_guaranteed=int(ref.sum()),
                original_retained=int((mask & ref).sum())))
        rng = np.random.default_rng(2026090610+p)
        groups = stratum_indices(bank)
        counts = np.zeros((len(SETTINGS), len(bank.names)), dtype=int)
        for draw in range(args.draws):
            selection = np.concatenate([rng.choice(g, len(g), replace=True) for g in groups])
            low = bank.objectives(draw=selection, k=4)[:, :4]
            upper = low.copy()
            upper[:, 2] = bank.outage[selection, :, 0].mean(0)
            previous = None
            masks = []
            for j, ((family_name, radius), t) in enumerate(zip(SETTINGS, prices)):
                if radius == 0: previous = None
                mask = guaranteed_with_shared_tariffs(low, upper, t)
                if previous is not None and (mask & ~previous).any():
                    raise AssertionError("resample violated radius nesting")
                previous = mask
                masks.append(mask)
                counts[j] += mask
                boot_rows.append(dict(profile=bank.profile, price_region=family_name, radius=radius, draw=draw,
                    guaranteed=int(mask.sum()), original_retained=int((mask & ref).sum())))
            if any((masks[i] & ~masks[i+len(RADII)]).any() for i in range(len(RADII))):
                raise AssertionError("nested price region failed in resample")
            if (draw+1) % 250 == 0:
                print(bank.profile, draw+1, "resamples", flush=True)
        for j, (family_name, radius) in enumerate(SETTINGS):
            for c, name in enumerate(bank.names):
                candidate_rows.append(dict(profile=bank.profile, portfolio=name, price_region=family_name, radius=radius,
                    point_guaranteed=bool(point[j][c]), original_endpoint_guaranteed=bool(ref[c]),
                    bootstrap_guaranteed_count=int(counts[j, c]),
                    bootstrap_guaranteed_frequency=float(counts[j, c]/args.draws)))
        for alpha in [.10, .05, .01]:
            lower, width = hoeffding_lower_differences(bank.loss, bank.outage[:, :, 3],
                bank.outage[:, :, 0], bank.nonrecovery, loss_bound=loss_bound,
                family_size=family, alpha=alpha)
            for (family_name, radius), t in zip(SETTINGS, prices):
                mask = sufficient_population_retention(lower, t)
                population_rows.append(dict(profile=bank.profile, price_region=family_name, radius=radius, alpha=alpha,
                    guaranteed=int(mask.sum()), original_retained=int((mask & ref).sum()),
                    candidates=";".join(np.array(bank.names)[mask]), family_size=family,
                    loss_bound=loss_bound, loss_difference_halfwidth=float(width[0]),
                    binary_difference_halfwidth=float(width[1])))
    outputs = []
    for name, rows in [("point_retention", point_rows), ("bootstrap_draws", boot_rows),
                       ("candidate_retention", candidate_rows),
                       ("population_retention", population_rows)]:
        path = out/(name+".csv")
        write_csv(pd.DataFrame(rows), path); outputs.append(path)
    boot = pd.DataFrame(boot_rows)
    summarized = []
    for (profile, region, radius), group in boot.groupby(["profile", "price_region", "radius"], sort=False):
        c = pd.DataFrame(candidate_rows)
        c = c[(c.profile == profile) & (c.price_region == region) & (c.radius == radius)]
        row = dict(profile=profile, price_region=region, radius=radius, draws=args.draws,
            original_candidates_at_least_95pct=int(((c.bootstrap_guaranteed_frequency >= .95)
                & c.original_endpoint_guaranteed).sum()),
            original_candidates_every_draw=int(((c.bootstrap_guaranteed_count == args.draws)
                & c.original_endpoint_guaranteed).sum()))
        for col in ["guaranteed", "original_retained"]:
            row.update({col+"_"+label: float(group[col].quantile(q))
                        for label, q in [("q025", .025), ("median", .5), ("q975", .975)]})
        summarized.append(row)
    path = out/"bootstrap_summary.csv"
    write_csv(pd.DataFrame(summarized), path); outputs.append(path)
    manifest = build_manifest(run_id="joint-stability", stage="analysis",
        description="Shared tariffs, paired outcome resampling, and simultaneous bounded-mean screen.",
        inputs=inputs, outputs=outputs, source_state=state, parameters=dict(
            radii=RADII, price_regions=["monotone", "positive_gaps"], draws=args.draws, seed=2026090610, alphas=[.10, .05, .01],
            ordered_mean_family_size=family, loss_bound=loss_bound,
            price_rounding_decimal_places=12,
            bootstrap_scope="conditional resampling frequencies, not confidence guarantees",
            population_scope="sufficient retention in the declared scenario population; arbitrary tail coordinate"))
    write_manifest(manifest, out/"joint_manifest.json")
    print(pd.DataFrame(point_rows).to_string(index=False))
    print(pd.DataFrame(summarized).to_string(index=False))
    print(pd.DataFrame(population_rows).query("alpha == .05").drop(
        columns=["candidates"]).to_string(index=False))


if __name__ == "__main__":
    main()

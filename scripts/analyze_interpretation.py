#!/usr/bin/env python3
"""Reproduce the retrospective audit without rerunning the simulator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.config import load_config, load_defense_costs
from grrc.defenses import enumerate_portfolios, portfolio_cost
from grrc.interpretation import (make_bank, bootstrap_bank, baseline_contrasts,
    endpoint_frontiers, objective_ablation, resolution_diagnostic, frontier_counts)
from grrc.multiobjective import (OBJECTIVES, load_operational_burdens,
    portfolio_operational_burden, pareto_mask)
from grrc.provenance import (build_manifest, git_state, write_manifest,
                             canonical_json, sha256_file)
from grrc.utilities import write_csv, REPO_ROOT

PROFILES = ["resource_constrained", "intermediate_capacity", "high_capacity"]
SOURCE_FILES = [
    "scripts/analyze_interpretation.py", "src/grrc/interpretation.py",
    "src/grrc/multiobjective.py", "src/grrc/defenses.py", "src/grrc/endpoints.py",
    "src/grrc/provenance.py", "src/grrc/utilities.py", "src/grrc/config.py",
    "study/INTERPRETATION_ANALYSIS_PLAN.md",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--weight-draws", type=int, default=500)
    parser.add_argument("--seed", type=int, default=2026090601)
    parser.add_argument("--output", type=Path, default=Path("data/interpretation"))
    parser.add_argument("--allow-dirty", action="store_true",
                        help="development only; final generation requires a clean source tree")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit the source and inputs before final generation (tree is dirty).")
    if args.bootstrap < 2 or args.weight_draws < 1:
        raise SystemExit("bootstrap >= 2 and weight-draws >= 1 required")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    inputs: list[Path] = [Path(p) for p in SOURCE_FILES]
    outputs: list[Path] = []

    def save(name: str, frame: pd.DataFrame) -> None:
        path = out / (name + ".csv")
        write_csv(frame, path)
        outputs.append(path)

    cfgpath = Path("configs/multiobjective_portfolio.yaml")
    costpath = Path("configs/defense_costs.yaml")
    burdenpath = Path("configs/defense_burdens.yaml")
    protocolpath = Path("study/protocols/multiobjective_confirmatory_v2.protocol.json")
    cfg = load_config(cfgpath)
    costs = load_defense_costs(costpath)
    burdens = load_operational_burdens(burdenpath)
    protocol = json.loads(protocolpath.read_text(encoding="utf-8"))
    finalists = protocol["body"]["frozen_finalist_labels"]["identities"]
    inputs += [cfgpath, costpath, burdenpath, protocolpath]
    columns = ["profile", "portfolio", "scenario_id", "paired",
               "weighted_service_hours_lost", "recovered_within_horizon"] + [
        f"sustained_clinical_outage_k{k}" for k in range(1, 5)]
    stage_rows, distribution, pooling = [], [], []
    banks = []
    raw_identifiers = {}
    for stage, folder, filename in [
        ("discovery", "discovery", "discovery_results.csv"),
        ("confirmation", "confirmatory", "multiobjective_confirmatory_results.csv"),
    ]:
        rawpath = Path(f"data/multiobjective/{folder}/{filename}")
        summarypath = rawpath.parent / "portfolio_objective_summary.csv"
        raw = pd.read_csv(rawpath, usecols=columns)
        summary = pd.read_csv(summarypath)
        inputs += [rawpath, summarypath]
        raw_identifiers[stage] = {"rows": len(raw), "sha256": sha256_file(rawpath)}
        between_by_profile = []
        for profile in PROFILES:
            bank = make_bank(raw, summary, profile, finalists[profile])
            frame = raw.loc[raw.profile == profile]
            count = frame[[f"sustained_clinical_outage_k{k}" for k in range(1, 5)]].sum(axis=1)
            kmeans = bank.outage.mean(axis=(0, 1))
            between = float(((count > 0) & (count < 4)).mean())
            between_by_profile.append(between)
            stage_rows.append({"stage": stage, "profile": profile,
                "trials": len(frame), "candidates": len(bank.names),
                "scenarios": len(bank.scenarios), "stage_weight": len(frame) / len(raw),
                **{f"k{k}_probability": kmeans[k - 1] for k in range(1, 5)},
                "k1_minus_k4_pp": 100 * (kmeans[0] - kmeans[3]),
                "between_share": between})
            for k in range(5):
                distribution.append({"stage": stage, "profile": profile,
                                     "qualifying_services": k, "trials": int((count == k).sum()),
                                     "share": float((count == k).mean())})
            if stage == "confirmation":
                banks.append(bank)
                recomputed = bank.objectives()
                original = summary.loc[summary.profile == profile].set_index("portfolio").loc[bank.names, list(OBJECTIVES)].to_numpy(float)
                if not np.allclose(recomputed, original, rtol=1e-8, atol=1e-7):
                    raise ValueError("recorded summary does not rederive from raw trials")
        counts = raw[[f"sustained_clinical_outage_k{k}" for k in range(1, 5)]].sum(axis=1)
        pooling.append({"stage": stage, "pooled_between_share": ((counts > 0) & (counts < 4)).mean(),
                        "equal_profile_between_share": np.mean(between_by_profile),
                        "maximum_profile_between_share": max(between_by_profile)})
    save("endpoint_by_stage_profile", pd.DataFrame(stage_rows))
    save("qualifying_service_distribution", pd.DataFrame(distribution))
    save("pooling_comparison", pd.DataFrame(pooling))

    bootstrap_rows, contrasts, endpoints, ablations, resolutions, gap_rows = [], [], [], [], [], []
    point_rows = []
    family = sum(len(bank.names) - 1 for bank in banks)
    for i, bank in enumerate(banks):
        print(f"Bootstrap {bank.profile}: {args.bootstrap} paired scenario draws", flush=True)
        samples, tails, gaps = bootstrap_bank(bank, n_boot=args.bootstrap, seed=args.seed + i)
        bootstrap_rows.append(samples)
        contrasts.append(baseline_contrasts(bank, family))
        endpoints.append(endpoint_frontiers(bank))
        ablations.append(objective_ablation(bank))
        resolutions.append(resolution_diagnostic(bank, tails))
        gap_rows.append({"profile": bank.profile, "mean_gap_pp": 100 * gaps.mean(),
                         "bootstrap_lower_pp": 100 * np.quantile(gaps, .025),
                         "bootstrap_upper_pp": 100 * np.quantile(gaps, .975)})
        point_rows.append({"profile": bank.profile,
                           **frontier_counts(bank.objectives(), bank.finalist)})
    draws = pd.concat(bootstrap_rows, ignore_index=True)
    save("frontier_bootstrap_draws", draws)
    save("frontier_point_counts", pd.DataFrame(point_rows))
    save("baseline_contrasts", pd.concat(contrasts, ignore_index=True))
    save("endpoint_frontier_sensitivity", pd.concat(endpoints, ignore_index=True))
    save("objective_ablation", pd.concat(ablations, ignore_index=True))
    save("paired_resolution", pd.DataFrame(resolutions))
    save("endpoint_gap_bootstrap", pd.DataFrame(gap_rows))
    summaries = []
    total = draws.groupby("draw").sum(numeric_only=True).reset_index()
    total["profile"] = "all_profiles"
    for profile, group in pd.concat([draws, total], ignore_index=True).groupby("profile"):
        for metric in ("full_frontier", "restricted_frontier", "omitted_efficient", "restricted_artifacts"):
            values = group[metric].to_numpy(float)
            summaries.append({"profile": profile, "metric": metric, "n_boot": len(values),
                "mean": values.mean(), "median": np.median(values),
                "p025": np.quantile(values, .025), "p975": np.quantile(values, .975),
                "minimum": values.min(), "maximum": values.max(),
                "positive_share": (values > 0).mean()})
    save("frontier_bootstrap_summary", pd.DataFrame(summaries))

    print(f"Component-weight sensitivity: {args.weight_draws} draws", flush=True)
    rng = np.random.default_rng(2026090602)
    portfolios = {p.name: p for p in enumerate_portfolios()}
    base_matrices = {bank.profile: bank.objectives() for bank in banks}
    weight_rows, weight_parameters = [], []
    rejected = 0
    for draw in range(args.weight_draws):
        while True:
            sampled_costs = {key: value * rng.uniform(.5, 1.5) for key, value in costs.items()}
            sampled_burdens = {key: value * rng.uniform(.5, 1.5) for key, value in burdens.items()}
            if all(w["least_privilege_segmentation"] >= w["basic_segmentation"] and
                   w["protected_backups"] >= w["periodic_backups"] for w in (sampled_costs, sampled_burdens)):
                break
            rejected += 1
        weight_parameters.append({"draw": draw,
            **{"cost_" + key: value for key, value in sampled_costs.items()},
            **{"burden_" + key: value for key, value in sampled_burdens.items()}})
        for bank in banks:
            profile = cfg.profiles[bank.profile]
            matrix = base_matrices[bank.profile]
            reference = pareto_mask(matrix)
            changed = matrix.copy()
            changed[:, 4] = [portfolio_cost(portfolios[name], profile, sampled_costs) for name in bank.names]
            changed[:, 5] = [portfolio_operational_burden(portfolios[name], profile, sampled_burdens) for name in bank.names]
            frontier = pareto_mask(changed)
            affordable = changed[:, 4] <= profile.budget
            uniform = matrix.copy()
            uniform[:, 4:] *= 1.5
            if not np.array_equal(pareto_mask(uniform), reference):
                raise AssertionError("positive unit scaling changed Pareto membership")
            weight_rows.append({"profile": bank.profile, "draw": draw,
                "frontier_size": int(frontier.sum()), "added": int((frontier & ~reference).sum()),
                "removed": int((reference & ~frontier).sum()),
                "jaccard": (frontier & reference).sum() / (frontier | reference).sum(),
                "affordable_candidates": int(affordable.sum()),
                "best_affordable_mean_hours_lost": changed[affordable, 0].min()})
    save("component_weight_sensitivity", pd.DataFrame(weight_rows))
    save("component_weight_draws", pd.DataFrame(weight_parameters))
    parameters = {"retrospective": True, "bootstrap": args.bootstrap, "seed": args.seed,
        "weight_draws": args.weight_draws, "weight_seed": 2026090602,
        "rejected_nonmonotone_tariffs": rejected, "contrast_family_size": family,
        "source_state_captured": "before any analysis outputs were written",
        "raw_banks": raw_identifiers,
        "limitations": ["single synthetic model", "fixed discovery labels in conditional bootstrap",
                        "analyst-declared stress weights", "not independent replication"]}
    manifest = build_manifest(run_id="retrospective-interpretation-audit", stage="analysis",
        description="Paired retrospective interpretation diagnostics; unchanged simulator and original raw banks.",
        inputs=inputs, outputs=outputs, parameters=parameters, source_state=state)
    write_manifest(manifest, out / "analysis_manifest.json")
    print(json.dumps(parameters, indent=2), flush=True)


if __name__ == "__main__":
    main()

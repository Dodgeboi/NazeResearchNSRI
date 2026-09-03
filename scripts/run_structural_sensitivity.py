#!/usr/bin/env python3
"""Structural sensitivity: does assumption S1 change the answer?

The primary model gates restoration on complete containment — no node begins
restoring until every compromised node is isolated. Real incident response
restores in parallel with containment and prioritises clinical systems, so
this assumption couples the detection and isolation controls to the recovery
endpoint through a modeling choice rather than a mechanism. It was
undocumented before the rebuild (audit ISSUE-007).

Uncertainty about a structure is not uncertainty about a parameter, and a
confidence interval will not express it. The only honest treatment is to run
the alternative and report whether the conclusions move. This script does
that, on the same paired scenario bank, for the candidates that actually
carry the study's conclusions: confirmatory frontier members plus every
benchmark comparator and preference selection.

What is reported is **not** whether the numbers change — they will — but
whether the *decision* changes: which candidates are non-dominated, and how
much frontier membership is preserved.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from grrc.config import load_config, load_defense_costs
from grrc.defenses import enumerate_portfolios
from grrc.experiments import run_specs
from grrc.models import TrialSpec
from grrc.multiobjective import (OBJECTIVES, aggregate_objectives,
                                 load_operational_burdens, pareto_frontier)
from grrc.provenance import build_manifest, snapshot_inputs, write_manifest
from grrc.utilities import ensure_dirs, write_csv

#: Distinct from every other bank, so a structural-variant scenario can never
#: be confused with a discovery or confirmatory one.
STRUCTURAL_SEED = 7731409
STRUCTURAL_ID_OFFSET = 95_000_000


def candidates_carrying_conclusions(stage: Path) -> dict[str, list[str]]:
    """Frontier members, benchmarks, and preference picks, per profile."""
    frontier = pd.read_csv(stage / "portfolio_pareto_frontier.csv")
    benchmarks = pd.read_csv(stage / "portfolio_benchmark_comparison.csv")
    preferences = pd.read_csv(stage / "portfolio_preference_scenarios.csv")

    selected: dict[str, set[str]] = {}
    efficient = frontier[frontier["pareto_efficient"] == 1]
    for frame in (efficient, benchmarks, preferences):
        for profile, group in frame.groupby("profile"):
            selected.setdefault(str(profile), set()).update(
                group["portfolio"].astype(str))
    return {profile: sorted(names) for profile, names in selected.items()}


def build_specs(cfg, selection: dict[str, list[str]], trials: int):
    portfolio_map = {p.name: p for p in enumerate_portfolios()}
    specs: list[TrialSpec] = []
    portfolios: dict = {}
    trial_id = STRUCTURAL_ID_OFFSET
    cursor = STRUCTURAL_ID_OFFSET
    entries = cfg.experiment.entry_points
    for profile in cfg.optimization.profiles:
        names = selection.get(profile, [])
        if not names:
            continue
        portfolios.update({name: portfolio_map[name] for name in names})
        block = cursor
        cursor += trials
        for replicate in range(trials):
            entry = entries[replicate % len(entries)]
            for name in names:
                specs.append(TrialSpec(
                    trial_id=trial_id, experiment="structural_sensitivity",
                    facility=cfg.optimization.facility, profile=profile,
                    portfolio=name, entry_point=entry,
                    master_seed=STRUCTURAL_SEED,
                    scenario_id=block + replicate, paired=True))
                trial_id += 1
    return specs, portfolios


def frontier_of(raw: pd.DataFrame, cfg, costs, burdens) -> pd.DataFrame:
    return pareto_frontier(aggregate_objectives(raw, cfg, costs, burdens))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument("--stage-dir",
                        default="data/multiobjective/confirmatory")
    parser.add_argument("--out",
                        default="data/multiobjective/structural_sensitivity")
    parser.add_argument("--trials", type=int, default=150)
    args = parser.parse_args()

    cfg = load_config(args.config)
    costs = load_defense_costs("configs/defense_costs.yaml")
    burdens = load_operational_burdens("configs/defense_burdens.yaml")
    stage = Path(args.stage_dir)
    out = Path(args.out)
    ensure_dirs(out)

    selection = candidates_carrying_conclusions(stage)
    total = sum(len(names) for names in selection.values()) * args.trials
    print("structural sensitivity on S1 (containment-gated restoration)")
    for profile, names in sorted(selection.items()):
        print(f"  {profile:24s} {len(names):3d} candidates")
    print(f"  {total:,} executions per structural arm, two arms")

    specs, portfolios = build_specs(cfg, selection, args.trials)
    written: list[Path] = []
    arms: dict[str, pd.DataFrame] = {}
    for arm, gated in (("gated_primary", True),
                       ("parallel_alternative", False)):
        cfg.simulation.restore_requires_containment = gated
        raw = run_specs(cfg, specs, portfolios=portfolios,
                        desc=f"structural:{arm}")
        raw["structural_arm"] = arm
        raw["restore_requires_containment"] = int(gated)
        path = out / f"structural_{arm}.csv"
        write_csv(raw, path)
        written.append(path)
        arms[arm] = raw

    # Compare the decision, not the numbers.
    frontiers = {arm: frontier_of(raw, cfg, costs, burdens)
                 for arm, raw in arms.items()}
    comparison_rows = []
    for profile in sorted(selection):
        sets = {}
        for arm, frame in frontiers.items():
            group = frame[frame["profile"] == profile]
            sets[arm] = set(
                group.loc[group["pareto_efficient"] == 1, "portfolio"])
        primary = sets["gated_primary"]
        alternative = sets["parallel_alternative"]
        union = primary | alternative
        comparison_rows.append({
            "profile": profile,
            "candidates_tested": len(selection[profile]),
            "non_dominated_gated": len(primary),
            "non_dominated_parallel": len(alternative),
            "preserved": len(primary & alternative),
            "only_under_gated": len(primary - alternative),
            "only_under_parallel": len(alternative - primary),
            "jaccard_agreement": (
                len(primary & alternative) / len(union) if union else 1.0),
        })
    comparison = pd.DataFrame(comparison_rows)
    comparison_path = out / "structural_frontier_agreement.csv"
    write_csv(comparison, comparison_path)
    written.append(comparison_path)

    # Objective-level movement, so a reader sees magnitude as well as
    # membership.
    movement = []
    for arm, frame in frontiers.items():
        for profile, group in frame.groupby("profile"):
            row = {"structural_arm": arm, "profile": profile}
            row.update({f"mean_{name}": float(group[name].mean())
                        for name in OBJECTIVES})
            movement.append(row)
    movement_path = out / "structural_objective_movement.csv"
    write_csv(pd.DataFrame(movement), movement_path)
    written.append(movement_path)

    snapshots = snapshot_inputs(
        [args.config, "configs/defense_costs.yaml",
         "configs/defense_burdens.yaml"], out / "config_snapshot")
    manifest = build_manifest(
        run_id="structural-sensitivity-s1", stage="validation",
        description="Structural sensitivity for assumption S1: restoration "
                    "gated on complete containment versus proceeding in "
                    "parallel with it. Reports whether frontier membership "
                    "is preserved, not merely whether the numbers move.",
        inputs=snapshots, outputs=written,
        parameters={"trials_per_candidate": args.trials,
                    "master_seed": STRUCTURAL_SEED,
                    "candidates_by_profile":
                        {k: len(v) for k, v in selection.items()},
                    "total_executions_per_arm": total})
    write_manifest(manifest, out / "structural_sensitivity_manifest.json")

    print("\nfrontier agreement between structural arms:")
    print(comparison.to_string(index=False))
    print(f"\nwrote {len(written)} files to {out}")


if __name__ == "__main__":
    main()

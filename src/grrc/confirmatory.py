"""Paired confirmatory experiment and held-out optimizer evaluation.

The 2026 standard study is retained as an exploratory analysis. This module
constructs fresh scenarios whose topology, entry point, node attributes and
event-level random fields are reused across defenses. It also evaluates
optimizer finalists on seeds not used for discovery.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, load_defense_costs
from .defenses import (DefensePortfolio, enumerate_portfolios, get_portfolio,
                       portfolio_cost)
from .experiments import run_specs
from .models import TrialSpec
from .optimization import distinct_portfolios_for_profile, summarize_portfolios
from .utilities import ensure_dirs, resolve_path, setup_logging, write_csv

CONFIRMATORY_SEEDS = (20260718, 20260719, 20260720, 20260721, 20260722)
CONFIRMATORY_ID_OFFSET = 20_000_000
CONFIRMATORY_SWEEP_SCENARIO_OFFSET = 2_000_000
HOLDOUT_ID_OFFSET = 30_000_000
HOLDOUT_SCENARIO_OFFSET = 3_000_000


def _seed_for_rep(rep: int) -> int:
    return CONFIRMATORY_SEEDS[rep % len(CONFIRMATORY_SEEDS)]


def build_paired_main_specs(cfg: Config) -> list[TrialSpec]:
    """Build a facility x profile x entry scenario bank reused by portfolios."""
    specs: list[TrialSpec] = []
    tid = CONFIRMATORY_ID_OFFSET
    sid = 0
    for facility in cfg.experiment.facilities:
        for profile in cfg.experiment.profiles:
            for entry in cfg.experiment.entry_points:
                for rep in range(cfg.experiment.trials_per_cell):
                    seed = _seed_for_rep(rep)
                    for portfolio in cfg.experiment.portfolios:
                        get_portfolio(portfolio)
                        specs.append(TrialSpec(
                            trial_id=tid, experiment="confirmatory_main",
                            facility=facility, profile=profile,
                            portfolio=portfolio, entry_point=entry,
                            master_seed=seed, scenario_id=sid, paired=True))
                        tid += 1
                    sid += 1
    return specs


def build_paired_sweep_specs(cfg: Config) -> list[TrialSpec]:
    """Build one balanced scenario bank shared by all patch-delay cells."""
    specs: list[TrialSpec] = []
    tid = CONFIRMATORY_ID_OFFSET + 5_000_000
    entries = cfg.experiment.entry_points
    for rep in range(cfg.sweep.trials_per_cell):
        sid = CONFIRMATORY_SWEEP_SCENARIO_OFFSET + rep
        entry = entries[rep % len(entries)]
        seed = _seed_for_rep(rep)
        for patch in cfg.sweep.patch_levels:
            for delay in cfg.sweep.detection_delays:
                specs.append(TrialSpec(
                    trial_id=tid, experiment="confirmatory_sweep",
                    facility=cfg.sweep.facility, profile=cfg.sweep.profile,
                    portfolio="baseline_flat", entry_point=entry,
                    master_seed=seed, patch_override=patch,
                    detection_override=delay, scenario_id=sid, paired=True))
                tid += 1
    return specs


def _add_catalog_costs(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    costs = load_defense_costs(resolve_path("configs/defense_costs.yaml"))
    df = df.copy()
    df["portfolio_cost"] = [
        portfolio_cost(get_portfolio(name), cfg.profiles[profile], costs)
        for name, profile in zip(df["portfolio"], df["profile"])
    ]
    return df


def run_confirmatory(cfg: Config) -> dict[str, Path]:
    """Run paired main and sweep experiments and write raw evidence."""
    log = setup_logging(resolve_path(cfg.output.logs_dir), "grrc.confirmatory")
    raw_dir = resolve_path(cfg.output.raw_dir)
    ensure_dirs(raw_dir)
    started = time.time()

    main_specs = build_paired_main_specs(cfg)
    log.info("paired confirmatory main: %d trials", len(main_specs))
    main = _add_catalog_costs(
        run_specs(cfg, main_specs, desc="confirmatory:main"), cfg)
    main_path = raw_dir / "confirmatory_main_results.csv"
    write_csv(main, main_path)

    sweep_specs = build_paired_sweep_specs(cfg)
    log.info("paired confirmatory sweep: %d trials", len(sweep_specs))
    sweep = run_specs(cfg, sweep_specs, desc="confirmatory:sweep")
    sweep["portfolio_cost"] = np.nan
    sweep_path = raw_dir / "confirmatory_sweep_results.csv"
    write_csv(sweep, sweep_path)

    manifest = {
        "design": "paired common-random-number confirmatory follow-up",
        "seeds": list(CONFIRMATORY_SEEDS),
        "n_unique_main_scenarios": int(main["scenario_id"].nunique()),
        "n_main_trials": len(main),
        "n_unique_sweep_scenarios": int(sweep["scenario_id"].nunique()),
        "n_sweep_trials": len(sweep),
        "elapsed_seconds": round(time.time() - started, 1),
        "config": "configs/confirmatory.yaml",
    }
    manifest_path = raw_dir / "confirmatory_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"main": main_path, "sweep": sweep_path,
            "manifest": manifest_path}


def optimizer_finalists(discovery: pd.DataFrame, cfg: Config,
                        top_n: int = 5) -> dict[str, list[str]]:
    """Return the union of top discovery candidates across budgets."""
    costs = load_defense_costs(resolve_path("configs/defense_costs.yaml"))
    portfolio_map = {p.name: p for p in enumerate_portfolios()}
    summary = summarize_portfolios(discovery, cfg, costs)
    finalists: dict[str, list[str]] = {}
    for profile in cfg.optimization.profiles:
        names: set[str] = set()
        sub = summary[summary["profile"] == profile]
        for budget in cfg.optimization.budgets:
            feasible = sub[sub["base_cost"] <= budget]
            names.update(feasible.nsmallest(top_n, "mean_hours_lost")[
                "portfolio"].tolist())
        # Include the zero-cost reference even if it is not a top finalist.
        zero = sub[sub["base_cost"] == 0.0]
        if not zero.empty:
            names.add(str(zero.iloc[0]["portfolio"]))
        finalists[profile] = sorted(n for n in names if n in portfolio_map)
    return finalists


def run_optimizer_holdout(cfg: Config, discovery_csv: str | Path,
                          trials_per_candidate: int = 150) -> dict[str, Path]:
    """Evaluate discovery finalists with fresh paired scenarios and seeds."""
    discovery = pd.read_csv(discovery_csv)
    finalists = optimizer_finalists(discovery, cfg)
    portfolio_map = {p.name: p for p in enumerate_portfolios()}
    portfolios: dict[str, DefensePortfolio] = {}
    specs: list[TrialSpec] = []
    tid = HOLDOUT_ID_OFFSET
    entries = cfg.experiment.entry_points
    for profile_index, profile in enumerate(cfg.optimization.profiles):
        for rep in range(trials_per_candidate):
            sid = (HOLDOUT_SCENARIO_OFFSET
                   + profile_index * trials_per_candidate + rep)
            seed = CONFIRMATORY_SEEDS[rep % len(CONFIRMATORY_SEEDS)] + 100
            entry = entries[rep % len(entries)]
            for name in finalists[profile]:
                portfolios[name] = portfolio_map[name]
                specs.append(TrialSpec(
                    trial_id=tid, experiment="optimizer_holdout",
                    facility=cfg.optimization.facility, profile=profile,
                    portfolio=name, entry_point=entry, master_seed=seed,
                    scenario_id=sid, paired=True))
                tid += 1

    raw = run_specs(cfg, specs, portfolios=portfolios,
                    desc="confirmatory:optimizer-holdout")
    raw_dir = resolve_path(cfg.output.raw_dir)
    proc_dir = resolve_path(cfg.output.processed_dir)
    ensure_dirs(raw_dir, proc_dir)
    raw_path = raw_dir / "confirmatory_optimizer_holdout.csv"
    write_csv(raw, raw_path)
    costs = load_defense_costs(resolve_path("configs/defense_costs.yaml"))
    summary = summarize_portfolios(raw, cfg, costs)
    summary_path = proc_dir / "confirmatory_optimizer_holdout_summary.csv"
    write_csv(summary, summary_path)
    finalist_path = proc_dir / "confirmatory_optimizer_finalists.json"
    finalist_path.write_text(json.dumps(finalists, indent=2), encoding="utf-8")
    return {"raw": raw_path, "summary": summary_path,
            "finalists": finalist_path}

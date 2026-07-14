"""Budget-constrained defense-portfolio optimization + cost sensitivity.

Approach: the simulator's outcomes do not depend on what a defense
*costs*, only on what it *does*. So each of the 144 candidate portfolios
is evaluated ONCE per capacity profile with Monte Carlo trials; budgets
and cost-scaling scenarios then just re-filter and re-rank the same
measured performance. This makes the +/-50% cost sensitivity analysis
essentially free.

All costs are normalized model points (configs/defense_costs.yaml),
explicitly NOT dollar estimates.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, load_defense_costs
from .defenses import (DefensePortfolio, enumerate_portfolios,
                       portfolio_cost, describe_portfolio)
from .enums import BackupStrategy, SegmentationLevel
from .experiments import OPT_ID_OFFSET, run_specs
from .models import TrialSpec
from .statistics import bootstrap_ci
from .utilities import ensure_dirs, resolve_path, setup_logging

#: Metric minimized as 'expected service disruption'.
DISRUPTION_METRIC = "weighted_service_hours_lost"


def _portfolio_components(p: DefensePortfolio) -> dict[str, int]:
    """Binary indicators of which controls a portfolio contains."""
    return {
        "has_basic_segmentation":
            int(p.segmentation == SegmentationLevel.BASIC),
        "has_least_privilege":
            int(p.segmentation == SegmentationLevel.LEAST_PRIVILEGE),
        "has_patch_upgrade": int(p.patch_boost_levels > 0),
        "patch_boost_levels": p.patch_boost_levels,
        "has_detection_improvement": int(p.detection_improvement),
        "has_rapid_isolation": int(p.rapid_isolation),
        "has_protected_backups":
            int(p.backup_override == BackupStrategy.ISOLATED),
        "has_identity_controls": int(p.identity_controls),
    }


CONTROL_COLUMNS = [
    "has_basic_segmentation", "has_least_privilege", "has_patch_upgrade",
    "has_detection_improvement", "has_rapid_isolation",
    "has_protected_backups", "has_identity_controls",
]


def evaluate_candidate_portfolios(cfg: Config) -> pd.DataFrame:
    """Monte Carlo evaluation of every candidate portfolio per profile.

    Returns the raw per-trial DataFrame (also exported by ``optimize``).
    """
    opt = cfg.optimization
    portfolios = {p.name: p for p in enumerate_portfolios()}
    entries = cfg.experiment.entry_points
    specs: list[TrialSpec] = []
    tid = OPT_ID_OFFSET
    for profile in opt.profiles:
        for name in portfolios:
            for k in range(opt.trials_per_portfolio):
                specs.append(TrialSpec(
                    trial_id=tid, experiment="optimization",
                    facility=opt.facility, profile=profile,
                    portfolio=name, entry_point=entries[k % len(entries)],
                    master_seed=cfg.seed))
                tid += 1
    return run_specs(cfg, specs, portfolios=portfolios,
                     desc=f"{cfg.mode}:optimize")


def summarize_portfolios(raw: pd.DataFrame, cfg: Config,
                         costs: dict[str, float]) -> pd.DataFrame:
    """Aggregate trials into one row per (profile, portfolio)."""
    portfolios = {p.name: p for p in enumerate_portfolios()}
    rows = []
    for (profile, name), grp in raw.groupby(["profile", "portfolio"]):
        p = portfolios[name]
        hours = grp[DISRUPTION_METRIC].to_numpy()
        lo, hi = bootstrap_ci(hours, seed=cfg.seed)
        rows.append({
            "profile": profile,
            "portfolio": name,
            "description": describe_portfolio(p),
            "base_cost": portfolio_cost(p, cfg.profiles[profile], costs),
            "n_trials": len(grp),
            "mean_hours_lost": float(hours.mean()),
            "hours_lost_ci_lo": lo,
            "hours_lost_ci_hi": hi,
            "median_hours_lost": float(np.median(hours)),
            "p90_hours_lost": float(np.percentile(hours, 90)),
            "catastrophic_prob": float(grp["catastrophic"].mean()),
            "mean_pct_compromised": float(grp["pct_compromised"].mean()),
            "backup_compromise_prob":
                float(grp["backup_compromised"].mean()),
            **_portfolio_components(p),
        })
    return pd.DataFrame(rows)


def _zero_cost_baseline(summary: pd.DataFrame, profile: str) -> pd.Series:
    """The measured zero-cost portfolio (flat, no upgrades) for a profile."""
    sub = summary[(summary["profile"] == profile)
                  & (summary["base_cost"] == 0.0)]
    if sub.empty:  # cost scaling never makes a 0-cost portfolio non-zero
        raise RuntimeError(f"no zero-cost baseline found for '{profile}'")
    return sub.iloc[0]


def select_best(summary: pd.DataFrame, profile: str, budget: float,
                scale: float, baseline_hours: float) -> list[dict]:
    """Pick best portfolios under one budget/cost-scale for 4 criteria."""
    sub = summary[summary["profile"] == profile].copy()
    sub["cost"] = sub["base_cost"] * scale
    feasible = sub[sub["cost"] <= budget].copy()
    if feasible.empty:
        return []
    feasible["hours_preserved"] = (baseline_hours
                                   - feasible["mean_hours_lost"])
    with np.errstate(divide="ignore", invalid="ignore"):
        feasible["hours_preserved_per_point"] = np.where(
            feasible["cost"] > 0,
            feasible["hours_preserved"] / feasible["cost"], np.nan)
    span = (feasible["mean_hours_lost"].max()
            - feasible["mean_hours_lost"].min()) or 1.0
    norm_hours = (feasible["mean_hours_lost"]
                  - feasible["mean_hours_lost"].min()) / span
    cspan = (feasible["catastrophic_prob"].max()
             - feasible["catastrophic_prob"].min()) or 1.0
    norm_cat = (feasible["catastrophic_prob"]
                - feasible["catastrophic_prob"].min()) / cspan
    feasible["balanced_score"] = 0.5 * norm_hours + 0.5 * norm_cat

    picks = {
        "min_expected_disruption":
            feasible.sort_values(["mean_hours_lost", "cost"]).iloc[0],
        "min_catastrophic_prob":
            feasible.sort_values(
                ["catastrophic_prob", "mean_hours_lost"]).iloc[0],
        "max_hours_preserved_per_point":
            feasible.sort_values(
                "hours_preserved_per_point", ascending=False).iloc[0]
            if feasible["hours_preserved_per_point"].notna().any()
            else feasible.sort_values("mean_hours_lost").iloc[0],
        "best_balanced":
            feasible.sort_values(["balanced_score", "cost"]).iloc[0],
    }
    rows = []
    for criterion, row in picks.items():
        rows.append({
            "profile": profile, "budget": budget, "cost_scale": scale,
            "criterion": criterion, "portfolio": row["portfolio"],
            "description": row["description"], "cost": float(row["cost"]),
            "mean_hours_lost": float(row["mean_hours_lost"]),
            "catastrophic_prob": float(row["catastrophic_prob"]),
            "hours_preserved_per_point":
                float(row["hours_preserved_per_point"])
                if np.isfinite(row["hours_preserved_per_point"]) else np.nan,
            **{c: int(row[c]) for c in CONTROL_COLUMNS},
        })
    return rows


def pareto_frontier(summary: pd.DataFrame, profile: str) -> pd.DataFrame:
    """Non-dominated (cost, mean hours lost) portfolios for one profile."""
    sub = (summary[summary["profile"] == profile]
           .sort_values(["base_cost", "mean_hours_lost"]))
    frontier = []
    best = np.inf
    for _, row in sub.iterrows():
        if row["mean_hours_lost"] < best - 1e-12:
            best = row["mean_hours_lost"]
            frontier.append({
                "profile": profile, "portfolio": row["portfolio"],
                "description": row["description"],
                "cost": float(row["base_cost"]),
                "mean_hours_lost": float(row["mean_hours_lost"]),
                "catastrophic_prob": float(row["catastrophic_prob"]),
            })
    return pd.DataFrame(frontier)


def minimum_budget_table(summary: pd.DataFrame, cfg: Config,
                         max_budget: int = 25) -> pd.DataFrame:
    """Smallest integer budget whose best portfolio meets the
    catastrophic-probability target, per profile (base costs)."""
    target = cfg.optimization.catastrophic_target
    rows = []
    for profile in cfg.optimization.profiles:
        sub = summary[summary["profile"] == profile]
        found = None
        for budget in range(0, max_budget + 1):
            feasible = sub[sub["base_cost"] <= budget]
            if feasible.empty:
                continue
            if feasible["catastrophic_prob"].min() <= target:
                found = budget
                break
        rows.append({
            "profile": profile,
            "catastrophic_target": target,
            "min_budget": found if found is not None else np.nan,
            "reachable": int(found is not None),
        })
    return pd.DataFrame(rows)


def optimize(cfg: Config,
             defense_costs_path: str | Path | None = None) -> dict[str, Path]:
    """Full optimization pipeline; writes raw + processed CSVs."""
    log = setup_logging(resolve_path(cfg.output.logs_dir), "grrc.optimize")
    raw_dir = resolve_path(cfg.output.raw_dir)
    proc_dir = resolve_path(cfg.output.processed_dir)
    ensure_dirs(raw_dir, proc_dir)
    costs = load_defense_costs(
        defense_costs_path or resolve_path("configs/defense_costs.yaml"))

    log.info("evaluating %d candidate portfolios x %d profiles "
             "(%d trials each)", 144, len(cfg.optimization.profiles),
             cfg.optimization.trials_per_portfolio)
    raw = evaluate_candidate_portfolios(cfg)
    raw_path = raw_dir / f"{cfg.mode}_optimization_results.csv"
    raw.to_csv(raw_path, index=False)

    summary = summarize_portfolios(raw, cfg, costs)
    summary_path = proc_dir / f"{cfg.mode}_portfolio_summary.csv"
    summary.to_csv(summary_path, index=False)

    best_rows: list[dict] = []
    for profile in cfg.optimization.profiles:
        baseline_hours = float(
            _zero_cost_baseline(summary, profile)["mean_hours_lost"])
        for scale in cfg.optimization.cost_scale_factors:
            for budget in cfg.optimization.budgets:
                best_rows.extend(select_best(
                    summary, profile, budget, scale, baseline_hours))
    best = pd.DataFrame(best_rows)
    best_path = proc_dir / f"{cfg.mode}_best_portfolios.csv"
    best.to_csv(best_path, index=False)

    pareto = pd.concat([pareto_frontier(summary, p)
                        for p in cfg.optimization.profiles],
                       ignore_index=True)
    pareto_path = proc_dir / f"{cfg.mode}_pareto_frontier.csv"
    pareto.to_csv(pareto_path, index=False)

    # Defense-inclusion stability across cost scenarios (min-disruption
    # criterion): how often does each control appear in the winner?
    stab = (best[best["criterion"] == "min_expected_disruption"]
            .groupby("profile")[CONTROL_COLUMNS].mean().reset_index())
    stab_path = proc_dir / f"{cfg.mode}_cost_sensitivity.csv"
    stab.to_csv(stab_path, index=False)

    min_budget = minimum_budget_table(summary, cfg)
    min_budget_path = proc_dir / f"{cfg.mode}_minimum_budget.csv"
    min_budget.to_csv(min_budget_path, index=False)

    manifest = {
        "mode": cfg.mode, "master_seed": cfg.seed,
        "n_trials": len(raw),
        "profiles": cfg.optimization.profiles,
        "budgets": cfg.optimization.budgets,
        "cost_scale_factors": cfg.optimization.cost_scale_factors,
    }
    (raw_dir / f"{cfg.mode}_optimization_manifest.json").write_text(
        json.dumps(manifest, indent=2))

    log.info("optimization complete: %d trials, outputs in %s",
             len(raw), proc_dir)
    return {"raw": raw_path, "summary": summary_path, "best": best_path,
            "pareto": pareto_path, "cost_sensitivity": stab_path,
            "min_budget": min_budget_path}

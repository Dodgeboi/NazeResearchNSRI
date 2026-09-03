"""Transparent multi-objective portfolio decision analysis.

The simulator cannot identify a universally best defense portfolio.  This
module therefore keeps six undesirable outcomes separate and reports the
non-dominated (Pareto-efficient) set.  Cost and operational burden are
normalized scenario points, not empirical procurement or staffing estimates.
Preference scenarios are decision aids applied *after* the frontier is built;
they are not evidence that a selected portfolio is optimal for a hospital.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .config import Config
from .defenses import (DefensePortfolio, PATCH_LADDER, _ladder_index,
                       backup_increment_points, enumerate_portfolios,
                       portfolio_cost, segmentation_increment_points)
from .endpoints import (PARETO_OBJECTIVES,
                        SUSTAINED_OUTAGE_K_LADDER,
                        sustained_outage_column)
from .enums import BackupStrategy, SegmentationLevel
from .experiments import run_specs
from .models import TrialSpec
from .utilities import ensure_dirs, write_csv


#: The six minimized objectives, read from the endpoint registry so the
#: optimizer cannot keep a private list that drifts from the manuscript.
OBJECTIVES: tuple[str, ...] = PARETO_OBJECTIVES

PREFERENCE_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {name: 1 / len(OBJECTIVES) for name in OBJECTIVES},
    "continuity_first": {
        "mean_hours_lost": 0.30,
        "tail_hours_lost_cvar90": 0.25,
        "sustained_outage_probability": 0.20,
        "nonrecovery_probability": 0.15,
        "implementation_cost_points": 0.05,
        "operational_burden_points": 0.05,
    },
    "tail_risk_averse": {
        "mean_hours_lost": 0.10,
        "tail_hours_lost_cvar90": 0.35,
        "sustained_outage_probability": 0.30,
        "nonrecovery_probability": 0.15,
        "implementation_cost_points": 0.05,
        "operational_burden_points": 0.05,
    },
    "resource_constrained": {
        "mean_hours_lost": 0.15,
        "tail_hours_lost_cvar90": 0.10,
        "sustained_outage_probability": 0.10,
        "nonrecovery_probability": 0.10,
        "implementation_cost_points": 0.30,
        "operational_burden_points": 0.25,
    },
}

MULTIOBJECTIVE_HOLDOUT_SEED = 6837001
MULTIOBJECTIVE_HOLDOUT_ID_OFFSET = 80_000_000


def load_operational_burdens(path: str | Path) -> dict[str, float]:
    """Load and validate normalized burden weights."""
    with open(path, "r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}
    burdens = raw.get("burdens", raw)
    required = {
        "basic_segmentation", "least_privilege_segmentation",
        "patch_level_upgrade", "detection_improvement",
        "rapid_isolation", "periodic_backups", "protected_backups",
        "identity_controls",
    }
    missing = required - set(burdens)
    if missing:
        raise ValueError(f"burden file missing keys: {sorted(missing)}")
    for name, value in burdens.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"burden '{name}' must be a number >= 0")
    return {name: float(value) for name, value in burdens.items()}


def portfolio_operational_burden(
        portfolio: DefensePortfolio, profile, burdens: Mapping[str, float]
        ) -> float:
    """Return normalized workflow/implementation burden scenario points."""
    total = 0.0
    total += segmentation_increment_points(profile, portfolio, dict(burdens))
    total += backup_increment_points(profile, portfolio, dict(burdens))

    target_patch = None
    if portfolio.patch_coverage_override is not None:
        target_patch = portfolio.patch_coverage_override
    elif portfolio.patch_boost_levels:
        start = _ladder_index(PATCH_LADDER, profile.patch_coverage)
        target_patch = PATCH_LADDER[min(
            start + portfolio.patch_boost_levels, len(PATCH_LADDER) - 1)]
    if target_patch is not None and target_patch > profile.patch_coverage:
        levels = (_ladder_index(PATCH_LADDER, target_patch)
                  - _ladder_index(PATCH_LADDER, profile.patch_coverage))
        total += max(0, levels) * burdens["patch_level_upgrade"]
    if portfolio.detection_improvement:
        total += burdens["detection_improvement"]
    if portfolio.rapid_isolation:
        total += burdens["rapid_isolation"]
    if portfolio.identity_controls:
        total += burdens["identity_controls"]
    return float(total)


def conditional_value_at_risk(values: Sequence[float], alpha: float = 0.90
                              ) -> float:
    """Mean of observations at or above the empirical ``alpha`` quantile."""
    data = np.asarray(values, dtype=float)
    if data.size == 0:
        raise ValueError("CVaR requires at least one observation")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0,1)")
    cutoff = float(np.quantile(data, alpha))
    return float(data[data >= cutoff].mean())


def aggregate_objectives(raw: pd.DataFrame, cfg: Config,
                         costs: Mapping[str, float],
                         burdens: Mapping[str, float],
                         *, cvar_alpha: float = 0.90) -> pd.DataFrame:
    """Aggregate trial rows into six-objective candidate summaries."""
    outage_column = sustained_outage_column(
        cfg.simulation.sustained_outage_min_services)
    required = {
        "profile", "portfolio", "weighted_service_hours_lost",
        "recovered_within_horizon", "step_minutes",
        "n_nodes", "defensive_isolation_node_steps", outage_column,
    }
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"raw results missing columns: {sorted(missing)}")
    portfolio_map = {p.name: p for p in enumerate_portfolios()}
    rows: list[dict[str, object]] = []
    for (profile_name, portfolio_name), group in raw.groupby(
            ["profile", "portfolio"], sort=True):
        if profile_name not in cfg.profiles:
            raise ValueError(f"unknown profile in results: {profile_name}")
        if portfolio_name not in portfolio_map:
            raise ValueError(
                f"multi-objective analysis requires an enumerated portfolio; "
                f"unknown: {portfolio_name}")
        portfolio = portfolio_map[portfolio_name]
        profile = cfg.profiles[profile_name]
        loss = group["weighted_service_hours_lost"].to_numpy(float)
        defensive_hours_per_node = (
            group["defensive_isolation_node_steps"].to_numpy(float)
            * group["step_minutes"].to_numpy(float) / 60.0
            / group["n_nodes"].to_numpy(float))
        rows.append({
            "profile": profile_name,
            "portfolio": portfolio_name,
            "n_scenarios": int(len(group)),
            "mean_hours_lost": float(loss.mean()),
            "tail_hours_lost_cvar90": conditional_value_at_risk(
                loss, cvar_alpha),
            "sustained_outage_probability": float(
                group[outage_column].mean()),
            # Prespecified sensitivity: every k is reported alongside the
            # primary one, so a reader who prefers a different service count
            # can read their own number off the same table without rerunning
            # anything.
            **{f"sustained_outage_probability_k{k}": float(
                   group[sustained_outage_column(k)].mean())
               for k in SUSTAINED_OUTAGE_K_LADDER
               if sustained_outage_column(k) in group.columns},
            "nonrecovery_probability": float(
                1.0 - group["recovered_within_horizon"].mean()),
            "implementation_cost_points": portfolio_cost(
                portfolio, profile, dict(costs)),
            "operational_burden_points": portfolio_operational_burden(
                portfolio, profile, burdens),
            "mean_defensive_isolation_hours_per_node": float(
                defensive_hours_per_node.mean()),
        })
    return pd.DataFrame(rows)


def pareto_mask(values: np.ndarray) -> np.ndarray:
    """Return mask of non-dominated rows for minimization objectives."""
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("values must be a two-dimensional matrix")
    if not np.isfinite(matrix).all():
        raise ValueError("objective matrix must contain only finite values")
    efficient = np.ones(matrix.shape[0], dtype=bool)
    for i, candidate in enumerate(matrix):
        dominated = np.any(
            np.all(matrix <= candidate, axis=1)
            & np.any(matrix < candidate, axis=1))
        efficient[i] = not dominated
    return efficient


def pareto_frontier(summary: pd.DataFrame,
                    objectives: Sequence[str] = OBJECTIVES) -> pd.DataFrame:
    """Mark the Pareto-efficient candidates independently by profile."""
    missing = set(objectives) - set(summary.columns)
    if missing:
        raise ValueError(f"summary missing objectives: {sorted(missing)}")
    frames: list[pd.DataFrame] = []
    for _, group in summary.groupby("profile", sort=True):
        frame = group.copy()
        frame["pareto_efficient"] = pareto_mask(
            frame[list(objectives)].to_numpy(float)).astype(int)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else summary.copy()


def _minmax(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    normalized = pd.DataFrame(index=frame.index)
    for column in columns:
        values = frame[column].to_numpy(float)
        span = float(values.max() - values.min())
        normalized[column] = ((values - values.min()) / span
                              if span > 0 else np.zeros_like(values))
    return normalized


def preference_scenarios(
        frontier: pd.DataFrame, cfg: Config,
        weights: Mapping[str, Mapping[str, float]] = PREFERENCE_WEIGHTS,
        objectives: Sequence[str] = OBJECTIVES) -> pd.DataFrame:
    """Choose one frontier point per declared preference scenario.

    The augmented weighted Chebyshev score minimizes the worst weighted
    normalized shortfall and adds a small tie-breaking sum.  All weights are
    declared in the output so a decision can be recomputed or challenged.
    """
    rows: list[dict[str, object]] = []
    for profile, group in frontier.groupby("profile", sort=True):
        if profile not in cfg.profiles:
            raise ValueError(f"unknown profile: {profile}")
        budget = float(cfg.profiles[profile].budget)
        candidates = group[
            (group["pareto_efficient"] == 1)
            & (group["implementation_cost_points"] <= budget)].copy()
        if candidates.empty:
            continue
        normalized = _minmax(candidates, objectives)
        for scenario, mapping in weights.items():
            if set(mapping) != set(objectives):
                raise ValueError(
                    f"preference '{scenario}' must weight every objective")
            weight = np.array([mapping[name] for name in objectives], float)
            if np.any(weight < 0) or not np.isclose(weight.sum(), 1.0):
                raise ValueError(
                    f"preference '{scenario}' weights must be nonnegative "
                    "and sum to one")
            weighted = normalized[list(objectives)].to_numpy(float) * weight
            score = weighted.max(axis=1) + 0.01 * weighted.sum(axis=1)
            chosen_position = int(np.argmin(score))
            chosen = candidates.iloc[chosen_position]
            row = {
                "profile": profile,
                "preference_scenario": scenario,
                "portfolio": chosen["portfolio"],
                "budget_points": budget,
                "within_budget": 1,
                "augmented_chebyshev_score": float(score[chosen_position]),
            }
            row.update({name: float(chosen[name]) for name in objectives})
            row.update({f"weight_{name}": float(mapping[name])
                        for name in objectives})
            rows.append(row)
    return pd.DataFrame(rows)


def benchmark_portfolios(summary: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Extract transparent comparator strategies from enumerated candidates.

    The comparators are not asserted to be real hospital standards.  They are
    reproducible decision rules: a no-upgrade flat reference, the study's
    layered heuristic (basic segmentation + faster detection/isolation +
    isolated backups), a maximum-control stack, and a simple disruption saved
    per cost-point rule within each profile's declared budget.
    """
    rows: list[dict[str, object]] = []
    for profile_name, group in summary.groupby("profile", sort=True):
        if profile_name not in cfg.profiles:
            raise ValueError(f"unknown profile: {profile_name}")
        profile = cfg.profiles[profile_name]
        names = {
            "flat_reference": (
                "seg-flat|patch+0|det0|iso0|bak-connected|idm0"),
            "layered_heuristic": (
                "seg-basic|patch+0|det1|iso1|bak-isolated|idm0"),
        }
        maximum = group.sort_values(
            ["implementation_cost_points", "operational_burden_points",
             "mean_hours_lost"], ascending=[False, False, True]).iloc[0]
        selected: list[tuple[str, pd.Series]] = [
            (label, group[group["portfolio"] == name].iloc[0])
            for label, name in names.items()
            if not group[group["portfolio"] == name].empty
        ]
        selected.append(("maximum_control_stack", maximum))

        flat = group[group["portfolio"] == names["flat_reference"]]
        if not flat.empty:
            baseline_loss = float(flat.iloc[0]["mean_hours_lost"])
            feasible = group[
                group["implementation_cost_points"] <= profile.budget].copy()
            feasible = feasible[feasible["implementation_cost_points"] > 0]
            if not feasible.empty:
                feasible["hours_saved_per_cost_point"] = (
                    baseline_loss - feasible["mean_hours_lost"]
                ) / feasible["implementation_cost_points"]
                efficient = feasible.sort_values(
                    ["hours_saved_per_cost_point", "mean_hours_lost"],
                    ascending=[False, True]).iloc[0]
                selected.append(("budget_efficiency_heuristic", efficient))

        for label, candidate in selected:
            row = {
                "profile": profile_name,
                "benchmark_strategy": label,
                "portfolio": candidate["portfolio"],
                "profile_budget_points": float(profile.budget),
                "within_profile_budget": int(
                    candidate["implementation_cost_points"] <= profile.budget),
            }
            row.update({name: float(candidate[name]) for name in OBJECTIVES})
            rows.append(row)
    return pd.DataFrame(rows)


def select_holdout_candidates(stability: pd.DataFrame,
                              preferences: pd.DataFrame,
                              benchmarks: pd.DataFrame, *,
                              threshold: float = 0.50
                              ) -> dict[str, list[str]]:
    """Freeze finalist identities from discovery-only decision rules."""
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0,1]")
    required_stability = {
        "profile", "portfolio", "pareto_inclusion_probability"}
    if required_stability - set(stability):
        raise ValueError("stability table is missing required columns")
    finalists: dict[str, set[str]] = {}
    stable = stability[
        stability["pareto_inclusion_probability"] >= threshold]
    for profile, group in stable.groupby("profile"):
        finalists.setdefault(str(profile), set()).update(
            group["portfolio"].astype(str))
    for frame in (preferences, benchmarks):
        if {"profile", "portfolio"} - set(frame):
            raise ValueError("decision table is missing profile/portfolio")
        for profile, group in frame.groupby("profile"):
            finalists.setdefault(str(profile), set()).update(
                group["portfolio"].astype(str))
    return {profile: sorted(names) for profile, names in finalists.items()}


def build_holdout_specs(cfg: Config,
                        finalists: Mapping[str, Sequence[str]],
                        trials_per_candidate: int = 150
                        ) -> tuple[list[TrialSpec], dict[str, DefensePortfolio]]:
    """Build a fresh paired scenario bank for frozen discovery finalists."""
    if trials_per_candidate < 1:
        raise ValueError("trials_per_candidate must be >= 1")
    portfolio_map = {p.name: p for p in enumerate_portfolios()}
    selected: dict[str, DefensePortfolio] = {}
    specs: list[TrialSpec] = []
    trial_id = MULTIOBJECTIVE_HOLDOUT_ID_OFFSET
    entries = cfg.experiment.entry_points
    for profile_index, profile in enumerate(cfg.optimization.profiles):
        names = list(finalists.get(profile, ()))
        if not names:
            raise ValueError(f"no holdout finalists for profile '{profile}'")
        unknown = set(names) - set(portfolio_map)
        if unknown:
            raise ValueError(f"unknown holdout portfolios: {sorted(unknown)}")
        selected.update({name: portfolio_map[name] for name in names})
        for replicate in range(trials_per_candidate):
            scenario_id = (MULTIOBJECTIVE_HOLDOUT_ID_OFFSET
                           + profile_index * trials_per_candidate + replicate)
            entry = entries[replicate % len(entries)]
            for name in names:
                specs.append(TrialSpec(
                    trial_id=trial_id,
                    experiment="multiobjective_holdout",
                    facility=cfg.optimization.facility,
                    profile=profile,
                    portfolio=name,
                    entry_point=entry,
                    master_seed=MULTIOBJECTIVE_HOLDOUT_SEED,
                    scenario_id=scenario_id,
                    paired=True,
                ))
                trial_id += 1
    return specs, selected


def run_multiobjective_holdout(
        cfg: Config, finalists: Mapping[str, Sequence[str]],
        output_path: str | Path, trials_per_candidate: int = 150
        ) -> Path:
    """Run and save the prespecified paired finalist holdout."""
    specs, portfolios = build_holdout_specs(
        cfg, finalists, trials_per_candidate=trials_per_candidate)
    raw = run_specs(cfg, specs, portfolios=portfolios,
                    desc="multiobjective:holdout")
    path = Path(output_path)
    ensure_dirs(path.parent)
    write_csv(raw, path)
    return path


def bootstrap_pareto_stability(raw: pd.DataFrame, cfg: Config,
                               costs: Mapping[str, float],
                               burdens: Mapping[str, float], *,
                               n_boot: int = 500,
                               seed: int = 20260718) -> pd.DataFrame:
    """Estimate Pareto-inclusion frequency using paired scenario resampling."""
    outage_column = sustained_outage_column(
        cfg.simulation.sustained_outage_min_services)
    required = {"profile", "portfolio", "scenario_id", "paired", outage_column}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"raw results missing pairing fields: {sorted(missing)}")
    if not (raw["paired"] == 1).all() or raw["scenario_id"].isna().any():
        raise ValueError("Pareto stability requires paired scenario results")
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for profile, group in raw.groupby("profile", sort=True):
        scenario_ids = np.sort(group["scenario_id"].unique())
        names = sorted(group["portfolio"].unique())
        expected = len(scenario_ids)
        observed = group.groupby("portfolio")["scenario_id"].nunique()
        if len(observed) != len(names) or not (observed == expected).all():
            raise ValueError("every portfolio must share the complete scenario bank")
        if group.duplicated(["portfolio", "scenario_id"]).any():
            raise ValueError("each portfolio/scenario pair must occur once")

        order = pd.MultiIndex.from_product(
            [names, scenario_ids], names=["portfolio", "scenario_id"])
        indexed = group.set_index(["portfolio", "scenario_id"]).reindex(order)
        if indexed.isna().all(axis=1).any():
            raise ValueError("paired scenario matrix contains missing cells")
        shape = (len(names), expected)
        loss = indexed["weighted_service_hours_lost"].to_numpy(float).reshape(shape)
        outage = indexed[outage_column].to_numpy(float).reshape(shape)
        recovered = indexed["recovered_within_horizon"].to_numpy(float).reshape(shape)
        static = (aggregate_objectives(group, cfg, costs, burdens)
                  .set_index("portfolio").loc[names])
        implementation_cost = static[
            "implementation_cost_points"].to_numpy(float)
        operational_burden = static[
            "operational_burden_points"].to_numpy(float)
        counts = np.zeros(len(names), dtype=int)

        for _ in range(n_boot):
            draw = rng.integers(0, expected, size=expected)
            sampled_loss = loss[:, draw]
            quantile = np.quantile(sampled_loss, 0.90, axis=1)
            cvar = np.array([
                values[values >= cutoff].mean()
                for values, cutoff in zip(sampled_loss, quantile)
            ])
            objective_matrix = np.column_stack((
                sampled_loss.mean(axis=1),
                cvar,
                outage[:, draw].mean(axis=1),
                1.0 - recovered[:, draw].mean(axis=1),
                implementation_cost,
                operational_burden,
            ))
            counts += pareto_mask(objective_matrix)
        rows.extend({
            "profile": profile,
            "portfolio": name,
            "pareto_inclusion_probability": int(count) / n_boot,
            "n_bootstrap_samples": n_boot,
        } for name, count in zip(names, counts))
    return pd.DataFrame(rows)

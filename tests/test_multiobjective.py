"""Tests for paired discovery and multi-objective decision analysis."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from grrc.config import default_config
from grrc.defenses import enumerate_portfolios
from grrc.multiobjective import (
    OBJECTIVES,
    aggregate_objectives,
    benchmark_portfolios,
    bootstrap_pareto_stability,
    build_holdout_specs,
    conditional_value_at_risk,
    load_operational_burdens,
    pareto_frontier,
    pareto_mask,
    portfolio_operational_burden,
    preference_scenarios,
    select_holdout_candidates,
)
from grrc.optimization import build_candidate_specs


ROOT = Path(__file__).resolve().parents[1]
COSTS = {
    "basic_segmentation": 3,
    "least_privilege_segmentation": 5,
    "patch_level_upgrade": 2,
    "detection_improvement": 3,
    "rapid_isolation": 5,
    "protected_backups": 2,
    "identity_controls": 4,
}


@pytest.fixture
def burdens():
    return load_operational_burdens(
        ROOT / "configs" / "defense_burdens.yaml")


def _raw_two_portfolios() -> pd.DataFrame:
    names = [p.name for p in list(enumerate_portfolios())[:2]]
    rows = []
    losses = {names[0]: (10.0, 20.0, 30.0),
              names[1]: (5.0, 10.0, 15.0)}
    for scenario, scenario_id in enumerate((100, 101, 102)):
        for name in names:
            loss = losses[name][scenario]
            rows.append({
                "profile": "resource_constrained",
                "portfolio": name,
                "scenario_id": scenario_id,
                "paired": 1,
                "weighted_service_hours_lost": loss,
                "catastrophic": int(loss >= 20),
                "recovered_within_horizon": int(loss < 30),
                "step_minutes": 5,
                "n_nodes": 100,
                "defensive_isolation_node_steps": scenario,
            })
    return pd.DataFrame(rows)


def test_optimizer_discovery_specs_share_scenario_bank():
    cfg = default_config()
    cfg.optimization.profiles = ["resource_constrained"]
    cfg.optimization.trials_per_portfolio = 3
    specs, portfolios = build_candidate_specs(cfg)
    assert specs
    assert all(spec.paired and spec.scenario_id is not None for spec in specs)
    by_portfolio = {
        name: {spec.scenario_id for spec in specs if spec.portfolio == name}
        for name in portfolios
    }
    scenario_banks = list(by_portfolio.values())
    assert len(scenario_banks[0]) == 3
    assert all(bank == scenario_banks[0] for bank in scenario_banks[1:])


def test_conditional_value_at_risk():
    assert conditional_value_at_risk([1, 2, 3, 4, 5], 0.8) == 5
    with pytest.raises(ValueError):
        conditional_value_at_risk([], 0.9)


def test_burden_file_and_full_candidate(burdens):
    cfg = default_config()
    full = list(enumerate_portfolios())[-1]
    burden = portfolio_operational_burden(
        full, cfg.profiles["resource_constrained"], burdens)
    assert burden > 0
    assert burdens["patch_level_upgrade"] == 3


def test_aggregate_objectives_has_six_declared_dimensions(burdens):
    cfg = default_config()
    summary = aggregate_objectives(
        _raw_two_portfolios(), cfg, COSTS, burdens)
    assert len(summary) == 2
    assert set(OBJECTIVES) <= set(summary)
    best = summary.sort_values("mean_hours_lost").iloc[0]
    assert best["mean_hours_lost"] == 10
    assert best["tail_hours_lost_cvar90"] == 15


def test_pareto_mask_and_profile_frontier():
    values = np.array([
        [1.0, 3.0],
        [2.0, 2.0],
        [3.0, 1.0],
        [3.0, 3.0],
    ])
    assert pareto_mask(values).tolist() == [True, True, True, False]
    frame = pd.DataFrame({
        "profile": ["p"] * 4,
        "portfolio": list("abcd"),
        **{name: values[:, i % 2] for i, name in enumerate(OBJECTIVES)},
    })
    marked = pareto_frontier(frame)
    assert marked.loc[marked.portfolio == "d", "pareto_efficient"].item() == 0


def test_preference_scenarios_only_select_frontier_points():
    rows = []
    for name, first, second, efficient in (
            ("low_cost", 8.0, 1.0, 1),
            ("low_loss", 1.0, 8.0, 1),
            ("dominated", 9.0, 9.0, 0)):
        row = {"profile": "resource_constrained", "portfolio": name,
               "pareto_efficient": efficient}
        for i, objective in enumerate(OBJECTIVES):
            row[objective] = first if i < 4 else second
        rows.append(row)
    choices = preference_scenarios(pd.DataFrame(rows), default_config())
    assert not choices.empty
    assert "dominated" not in set(choices.portfolio)
    assert set(choices.preference_scenario) == {
        "balanced", "continuity_first", "tail_risk_averse",
        "resource_constrained"}


def test_pareto_stability_requires_paired_results(burdens):
    cfg = default_config()
    raw = _raw_two_portfolios()
    raw["paired"] = 0
    with pytest.raises(ValueError, match="paired"):
        bootstrap_pareto_stability(
            raw, cfg, COSTS, burdens, n_boot=3)


def test_pareto_stability_returns_probabilities(burdens):
    cfg = default_config()
    result = bootstrap_pareto_stability(
        _raw_two_portfolios(), cfg, COSTS, burdens, n_boot=5, seed=7)
    assert len(result) == 2
    assert result["pareto_inclusion_probability"].between(0, 1).all()
    assert (result["n_bootstrap_samples"] == 5).all()


def test_benchmark_rules_are_named_and_budget_auditable(burdens):
    cfg = default_config()
    summary = aggregate_objectives(
        _raw_two_portfolios(), cfg, COSTS, burdens)
    # The two-row fixture contains the flat reference but not every comparator.
    result = benchmark_portfolios(summary, cfg)
    assert "flat_reference" in set(result["benchmark_strategy"])
    assert set(OBJECTIVES) <= set(result.columns)
    assert result["within_profile_budget"].isin([0, 1]).all()


def test_holdout_selection_is_union_of_prespecified_rules():
    stability = pd.DataFrame({
        "profile": ["resource_constrained"] * 2,
        "portfolio": ["stable", "unstable"],
        "pareto_inclusion_probability": [0.8, 0.2],
    })
    preferences = pd.DataFrame({
        "profile": ["resource_constrained"], "portfolio": ["preference"]})
    benchmarks = pd.DataFrame({
        "profile": ["resource_constrained"], "portfolio": ["benchmark"]})
    result = select_holdout_candidates(
        stability, preferences, benchmarks, threshold=0.5)
    assert result["resource_constrained"] == [
        "benchmark", "preference", "stable"]


def test_holdout_specs_are_fresh_and_paired():
    cfg = default_config()
    cfg.optimization.profiles = ["resource_constrained"]
    names = [p.name for p in list(enumerate_portfolios())[:2]]
    specs, portfolios = build_holdout_specs(
        cfg, {"resource_constrained": names}, trials_per_candidate=4)
    assert set(portfolios) == set(names)
    assert len(specs) == 8
    assert all(spec.paired for spec in specs)
    banks = {
        name: {spec.scenario_id for spec in specs if spec.portfolio == name}
        for name in names}
    assert banks[names[0]] == banks[names[1]]
    assert len(banks[names[0]]) == 4

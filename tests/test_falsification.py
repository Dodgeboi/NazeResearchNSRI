"""Falsification and sanity checks required by the rebuild handoff.

These are not tests that the model is *right*. They are tests that it is not
obviously broken: limiting cases behave the way the mechanism says they must,
invariances that should hold do hold, and the pathological configurations
that would silently corrupt a result raise instead.

Where a check fails for a reason that is a genuine modeling defect rather
than a test error, it is marked ``xfail`` with the audit issue it tracks, so
the defect stays visible in every test run instead of living only in a
document.
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from grrc.config import load_config
from grrc.defenses import enumerate_portfolios
from grrc.enums import Service
from grrc.endpoints import max_streak_column
from grrc.models import TrialSpec
from grrc.multiobjective import pareto_mask, restricted_frontier_comparison
from grrc.simulation import run_trial

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "multiobjective_portfolio.yaml"
PORTFOLIOS = {p.name: p for p in enumerate_portfolios()}
FLAT = "seg-flat|patch+0|det0|iso0|bak-connected|idm0"


@pytest.fixture(scope="module")
def base_cfg():
    cfg = load_config(CONFIG)
    cfg.simulation.max_steps = 120  # 10 modeled hours; keeps the suite fast
    return cfg


def make_spec(trial_id: int = 1, portfolio: str = FLAT,
              profile: str = "resource_constrained",
              entry: str = "workstation", scenario: int = 4242) -> TrialSpec:
    return TrialSpec(
        trial_id=trial_id, experiment="falsification",
        facility="regional_hospital", profile=profile, portfolio=portfolio,
        entry_point=entry, master_seed=99, scenario_id=scenario, paired=True)


def run(cfg, spec: TrialSpec) -> dict:
    return run_trial(cfg, spec, portfolio=PORTFOLIOS[spec.portfolio])


# ---------------------------------------------------------------------------
# Limiting behavior of the propagation mechanism
# ---------------------------------------------------------------------------

def test_zero_transmission_produces_no_secondary_compromise(base_cfg):
    """With the spread rate at zero, only the entry node is ever compromised."""
    cfg = copy.deepcopy(base_cfg)
    cfg.simulation.base_spread_rate = 0.0
    row = run(cfg, make_spec())
    assert row["lateral_movements"] == 0
    assert row["total_compromised"] == 1
    assert row["zones_reached"] <= 1


def test_full_patch_effectiveness_with_full_coverage_stops_propagation(base_cfg):
    """Removing every susceptible path removes propagation through them.

    This is the mechanism check, not a claim about patching: if a patched node
    has factor ``1 - patch_effectiveness`` and effectiveness is 1.0 with
    complete coverage, no edge can succeed.
    """
    cfg = copy.deepcopy(base_cfg)
    cfg.simulation.patch_effectiveness = 1.0
    cfg.profiles["resource_constrained"].patch_coverage = 1.0
    cfg.profiles["resource_constrained"].legacy_fraction = 0.0
    row = run(cfg, make_spec())
    assert row["lateral_movements"] == 0


def test_zero_false_positive_rate_isolates_no_healthy_node(base_cfg):
    cfg = copy.deepcopy(base_cfg)
    cfg.simulation.false_positive_rate = 0.0
    cfg.simulation.base_spread_rate = 0.0
    row = run(cfg, make_spec())
    assert row["defensive_isolation_node_steps"] == 0


def test_extreme_parameters_produce_interpretable_limits(base_cfg):
    """Saturating the spread rate must not produce NaN, negative, or absurd
    values — the failure mode that silently poisons an aggregate."""
    cfg = copy.deepcopy(base_cfg)
    cfg.simulation.base_spread_rate = 1.0
    row = run(cfg, make_spec())
    assert 0 <= row["ever_compromised_fraction"] <= 1
    assert row["weighted_service_hours_lost"] >= 0
    assert np.isfinite(row["weighted_service_hours_lost"])
    for service in Service:
        assert 0 <= row[max_streak_column(service)] <= row["steps_simulated"]


# ---------------------------------------------------------------------------
# Backup architecture
# ---------------------------------------------------------------------------

def test_isolated_backup_cannot_be_reached_through_the_network(base_cfg):
    """Traversal into an isolated backup zone is zero by construction."""
    cfg = copy.deepcopy(base_cfg)
    cfg.simulation.base_spread_rate = 1.0
    spec = make_spec(portfolio="seg-flat|patch+0|det0|iso0|bak-isolated|idm0")
    row = run(cfg, spec)
    assert row["backup_compromised"] == 0


@pytest.mark.xfail(
    reason="audit ISSUE-006: backup_traversal['isolated'] is exactly 0.0, so "
           "isolated backups cannot fail by ANY modeled mechanism. The "
           "handoff's red-line list forbids 'backup isolation eliminates "
           "compromise', and Sophos 2024 reports backup compromise attempted "
           "in 95% of healthcare victims and succeeding in 66% of attempts. "
           "Scheduled for WP3: nonzero residual failure with a prespecified "
           "uncertainty range.",
    strict=True)
def test_isolated_backup_retains_a_residual_failure_mode(base_cfg):
    """An 'isolated' backup must still be able to fail sometimes."""
    cfg = copy.deepcopy(base_cfg)
    cfg.simulation.base_spread_rate = 1.0
    failures = 0
    for trial in range(40):
        spec = make_spec(
            trial_id=trial,
            portfolio="seg-flat|patch+0|det0|iso0|bak-isolated|idm0",
            scenario=9000 + trial)
        failures += run(cfg, spec)["backup_compromised"]
    assert failures > 0, (
        "isolated backups survived every one of 40 saturated-spread trials")


# ---------------------------------------------------------------------------
# Ordering and accounting invariants
# ---------------------------------------------------------------------------

def test_recovery_endpoints_cannot_occur_in_an_impossible_order(base_cfg):
    cfg = copy.deepcopy(base_cfg)
    for trial in range(12):
        row = run(cfg, make_spec(trial_id=trial, scenario=500 + trial))
        if row["containment_step"] >= 0 and row["recovery_step"] > 0:
            assert row["recovery_step"] >= row["containment_step"], (
                "services recovered before the estate was contained")
        assert row["steps_simulated"] <= row["horizon_steps"]
        if row["recovered_within_horizon"]:
            assert row["recovery_step"] >= 0
        else:
            assert row["recovery_step"] == -1


def test_service_downtime_never_exceeds_the_simulated_horizon(base_cfg):
    cfg = copy.deepcopy(base_cfg)
    row = run(cfg, make_spec())
    for service in Service:
        assert row[f"{service.value}_downtime_steps"] <= row["steps_simulated"]
        assert (row[max_streak_column(service)]
                <= row[f"{service.value}_downtime_steps"]), (
            "a longest continuous outage cannot exceed total downtime")


def test_compromise_counts_are_conserved(base_cfg):
    cfg = copy.deepcopy(base_cfg)
    row = run(cfg, make_spec())
    assert row["peak_compromised"] <= row["total_compromised"]
    assert row["total_compromised"] <= row["n_nodes"]
    assert row["total_compromised"] >= 1  # the entry node


# ---------------------------------------------------------------------------
# Reproducibility and invariance
# ---------------------------------------------------------------------------

def test_identical_seed_and_config_reproduce_identical_results(base_cfg):
    first = run(base_cfg, make_spec(trial_id=7, scenario=31337))
    second = run(base_cfg, make_spec(trial_id=7, scenario=31337))
    assert first == second


def test_paired_candidates_share_the_same_latent_scenario(base_cfg):
    """Common random numbers: same scenario means same topology and entry."""
    flat = run(base_cfg, make_spec(trial_id=1, portfolio=FLAT, scenario=777))
    armored = run(base_cfg, make_spec(
        trial_id=2,
        portfolio="seg-flat|patch+0|det1|iso1|bak-isolated|idm0",
        scenario=777))
    assert flat["entry_node"] == armored["entry_node"]
    assert flat["n_nodes"] == armored["n_nodes"]


# ---------------------------------------------------------------------------
# Pareto machinery
# ---------------------------------------------------------------------------

def test_candidate_ordering_does_not_change_the_frontier():
    rng = np.random.default_rng(20260903)
    matrix = rng.random((40, 6))
    order = rng.permutation(40)
    base = pareto_mask(matrix)
    shuffled = pareto_mask(matrix[order])
    assert set(np.flatnonzero(base)) == set(order[np.flatnonzero(shuffled)])


def test_adding_a_dominated_candidate_removes_none(rng_seed: int = 11):
    rng = np.random.default_rng(rng_seed)
    matrix = rng.random((25, 6))
    before = set(np.flatnonzero(pareto_mask(matrix)))
    dominated = matrix.max(axis=0) + 1.0  # worse on every objective
    extended = np.vstack([matrix, dominated])
    after = set(np.flatnonzero(pareto_mask(extended)))
    assert before <= after
    assert 25 not in after, "a strictly dominated point joined the frontier"


def test_pareto_mask_rejects_non_finite_objectives():
    matrix = np.array([[1.0, 2.0], [np.nan, 1.0]])
    with pytest.raises(ValueError):
        pareto_mask(matrix)


def test_duplicate_points_are_both_retained():
    """Identical rows dominate nobody, so neither may be dropped."""
    matrix = np.array([[1.0, 1.0], [1.0, 1.0], [2.0, 2.0]])
    mask = pareto_mask(matrix)
    assert mask.tolist() == [True, True, False]


# ---------------------------------------------------------------------------
# Full-space vs finalist-only (audit ISSUE-012)
# ---------------------------------------------------------------------------

def _summary(rows: list[tuple[str, float, float]]) -> pd.DataFrame:
    """Minimal six-objective summary; only two objectives vary."""
    from grrc.multiobjective import OBJECTIVES
    frame = pd.DataFrame({
        "profile": "p", "portfolio": [r[0] for r in rows],
        OBJECTIVES[0]: [r[1] for r in rows],
        OBJECTIVES[1]: [r[2] for r in rows]})
    for name in OBJECTIVES[2:]:
        frame[name] = 0.0
    return frame


def test_a_non_finalist_can_dominate_a_finalist():
    """The exact failure the pre-rebuild design could not detect.

    ``kept`` looks non-dominated inside the finalist subset. In the full
    space ``skipped`` — never evaluated on holdout before the rebuild —
    dominates it outright.
    """
    summary = _summary([
        ("kept", 10.0, 10.0),     # frozen finalist
        ("also_kept", 2.0, 20.0),  # frozen finalist, genuinely efficient
        ("skipped", 5.0, 5.0),     # not a finalist; dominates "kept" only
    ])
    comparison = restricted_frontier_comparison(
        summary, {"p": ["kept", "also_kept"]})
    by_name = comparison.set_index("portfolio")

    assert by_name.loc["kept", "pareto_finalist_only"] == 1
    assert by_name.loc["kept", "pareto_full_space"] == 0
    assert by_name.loc["kept", "finalist_only_artifact"] == 1
    assert by_name.loc["kept", "dominated_by_non_finalist"] == "skipped"

    assert by_name.loc["skipped", "pareto_full_space"] == 1
    assert by_name.loc["skipped", "is_frozen_finalist"] == 0
    # A genuinely efficient finalist is unaffected by the correction.
    assert by_name.loc["also_kept", "pareto_full_space"] == 1
    assert by_name.loc["also_kept", "finalist_only_artifact"] == 0


def test_frontiers_agree_when_the_finalist_set_is_the_whole_space():
    summary = _summary([("a", 1.0, 3.0), ("b", 3.0, 1.0), ("c", 4.0, 4.0)])
    comparison = restricted_frontier_comparison(
        summary, {"p": ["a", "b", "c"]})
    assert (comparison["pareto_full_space"]
            == comparison["pareto_finalist_only"]).all()
    assert comparison["finalist_only_artifact"].sum() == 0


def test_empty_finalist_set_yields_no_restricted_frontier():
    summary = _summary([("a", 1.0, 3.0), ("b", 3.0, 1.0)])
    comparison = restricted_frontier_comparison(summary, {"p": []})
    assert comparison["pareto_finalist_only"].sum() == 0
    assert comparison["finalist_only_artifact"].sum() == 0
    assert comparison["pareto_full_space"].sum() == 2

"""Regression tests for exogenous capacity vs. purchased controls.

These cover audit ISSUE-003, ISSUE-004 and ISSUE-005. Before the rebuild,
every enumerated candidate set both ``segmentation`` and ``backup_override``,
and :func:`grrc.defenses.effective_settings` let the portfolio value win
unconditionally. Combined with cost tables that charged nothing for the
weakest rung, a high-capacity hospital could "buy" flat segmentation and
connected backups for zero points. Four of the seven frozen high-capacity
finalists in the pre-rebuild study were exactly such free downgrades, and the
70-test suite passed throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grrc.config import load_config, load_defense_costs
from grrc.defenses import (
    BACKUP_ORDER,
    SEGMENTATION_ORDER,
    DefensePortfolio,
    effective_settings,
    enumerate_portfolios,
    portfolio_cost,
    upgrade_only,
)
from grrc.enums import BackupStrategy, SegmentationLevel
from grrc.multiobjective import (
    load_operational_burdens,
    portfolio_operational_burden,
)
from grrc.optimization import distinct_portfolios_for_profile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "multiobjective_portfolio.yaml"


@pytest.fixture(scope="module")
def cfg():
    return load_config(CONFIG)


@pytest.fixture(scope="module")
def costs():
    return load_defense_costs(ROOT / "configs" / "defense_costs.yaml")


@pytest.fixture(scope="module")
def burdens():
    return load_operational_burdens(ROOT / "configs" / "defense_burdens.yaml")


def resolve(cfg, profile_name, portfolio):
    return effective_settings(
        cfg.profiles[profile_name], portfolio,
        rapid_isolation_success=cfg.simulation.rapid_isolation_success,
        detection_improvement_factor=(
            cfg.simulation.detection_improvement_factor))


# ---------------------------------------------------------------------------
# Ladder mechanics
# ---------------------------------------------------------------------------

def test_upgrade_only_never_moves_down_a_ladder():
    for baseline in SEGMENTATION_ORDER:
        for target in SEGMENTATION_ORDER:
            result = upgrade_only(SEGMENTATION_ORDER, baseline, target)
            assert SEGMENTATION_ORDER.index(result) >= (
                SEGMENTATION_ORDER.index(baseline))
            assert result in (baseline, target)


def test_upgrade_only_passes_baseline_through_when_no_target():
    assert upgrade_only(
        BACKUP_ORDER, BackupStrategy.PERIODIC, None) is BackupStrategy.PERIODIC


def test_backup_ladder_orders_periodic_between_connected_and_isolated():
    assert BACKUP_ORDER == (BackupStrategy.CONNECTED, BackupStrategy.PERIODIC,
                            BackupStrategy.ISOLATED)


# ---------------------------------------------------------------------------
# Capacity survives portfolio application
# ---------------------------------------------------------------------------

def test_no_candidate_can_weaken_any_profile_posture(cfg):
    """The central invariant: capacity is exogenous, controls are additive."""
    for profile_name, profile in cfg.profiles.items():
        base_seg = SegmentationLevel(profile.base_segmentation)
        base_bak = BackupStrategy(profile.backup_strategy)
        for portfolio in enumerate_portfolios():
            eff = resolve(cfg, profile_name, portfolio)
            assert SEGMENTATION_ORDER.index(eff.segmentation) >= (
                SEGMENTATION_ORDER.index(base_seg)), (
                f"{portfolio.name} weakened {profile_name} segmentation")
            assert BACKUP_ORDER.index(BackupStrategy(eff.backup_strategy)) >= (
                BACKUP_ORDER.index(base_bak)), (
                f"{portfolio.name} weakened {profile_name} backups")
            assert eff.patch_coverage >= profile.patch_coverage
            assert eff.detection_delay <= profile.detection_delay_steps
            assert eff.isolation_success >= profile.isolation_success


def test_high_capacity_keeps_least_privilege_and_isolated_backups(cfg):
    """The specific pre-rebuild failure, pinned as a named case."""
    downgrade = next(p for p in enumerate_portfolios()
                     if p.name == "seg-flat|patch+0|det0|iso0"
                                  "|bak-connected|idm0")
    eff = resolve(cfg, "high_capacity", downgrade)
    assert eff.segmentation is SegmentationLevel.LEAST_PRIVILEGE
    assert eff.backup_strategy == BackupStrategy.ISOLATED.value


def test_intermediate_periodic_backup_tier_is_reachable(cfg):
    """Audit ISSUE-005: the declared middle rung must not be erased.

    No enumerated portfolio can name ``periodic``, so before the fix every
    candidate silently replaced the intermediate profile's periodic backups
    with connected or isolated ones, and the profile's declared architecture
    never ran.
    """
    assert cfg.profiles["intermediate_capacity"].backup_strategy == "periodic"
    keeps_periodic = [
        p for p in distinct_portfolios_for_profile(cfg, "intermediate_capacity")
        if resolve(cfg, "intermediate_capacity", p).backup_strategy
        == BackupStrategy.PERIODIC.value]
    assert keeps_periodic, (
        "no intermediate-capacity candidate runs on the profile's own "
        "periodic backup architecture")


# ---------------------------------------------------------------------------
# Cost conservation
# ---------------------------------------------------------------------------

def test_exactly_one_zero_cost_candidate_per_profile(cfg, costs):
    """Only the profile's own untouched posture is free."""
    for profile_name in cfg.optimization.profiles:
        profile = cfg.profiles[profile_name]
        free = [p for p in distinct_portfolios_for_profile(cfg, profile_name)
                if portfolio_cost(p, profile, costs) == 0]
        assert len(free) == 1, (
            f"{profile_name} has {len(free)} zero-cost candidates: "
            f"{[p.name for p in free]}")
        eff = resolve(cfg, profile_name, free[0])
        assert eff.segmentation is SegmentationLevel(profile.base_segmentation)
        assert eff.backup_strategy == profile.backup_strategy
        assert eff.patch_coverage == profile.patch_coverage


def test_zero_cost_portfolios_contain_no_positive_cost_control(cfg, costs):
    """Falsification check from the handoff: no free control leakage."""
    for profile_name in cfg.optimization.profiles:
        profile = cfg.profiles[profile_name]
        for portfolio in distinct_portfolios_for_profile(cfg, profile_name):
            if portfolio_cost(portfolio, profile, costs) != 0:
                continue
            assert not portfolio.detection_improvement
            assert not portfolio.rapid_isolation
            assert not portfolio.identity_controls


def test_cost_is_monotone_in_the_posture_ladders(cfg, costs):
    """Buying more rungs never costs less."""
    profile = cfg.profiles["resource_constrained"]
    previous = -1.0
    for level in SEGMENTATION_ORDER:
        candidate = DefensePortfolio(
            name=f"seg-{level.value}", segmentation=level,
            backup_override=BackupStrategy.CONNECTED)
        cost = portfolio_cost(candidate, profile, costs)
        assert cost >= previous
        previous = cost


def test_upgrade_is_never_charged_for_a_rung_the_profile_already_has(
        cfg, costs, burdens):
    """A strong profile pays only for the increment it actually buys."""
    isolated_backup = DefensePortfolio(
        name="bak", segmentation=SegmentationLevel.FLAT,
        backup_override=BackupStrategy.ISOLATED)

    weak = cfg.profiles["resource_constrained"]     # connected baseline
    middle = cfg.profiles["intermediate_capacity"]  # periodic baseline
    strong = cfg.profiles["high_capacity"]          # isolated baseline

    weak_cost = portfolio_cost(isolated_backup, weak, costs)
    middle_cost = portfolio_cost(isolated_backup, middle, costs)
    strong_cost = portfolio_cost(isolated_backup, strong, costs)

    assert weak_cost > middle_cost > strong_cost == 0
    # Burden follows the same increment rule as cost.
    assert portfolio_operational_burden(isolated_backup, strong, burdens) == (
        portfolio_operational_burden(
            DefensePortfolio(name="none"), strong, burdens))


def test_downgrade_attempt_is_never_refunded(cfg, costs):
    """Naming a weaker rung must cost zero, not a negative amount."""
    strong = cfg.profiles["high_capacity"]
    downgrade = DefensePortfolio(
        name="down", segmentation=SegmentationLevel.FLAT,
        backup_override=BackupStrategy.CONNECTED)
    assert portfolio_cost(downgrade, strong, costs) == 0.0


# ---------------------------------------------------------------------------
# Deduplication honesty
# ---------------------------------------------------------------------------

def test_representative_name_matches_its_resolved_posture(cfg):
    """A candidate must be labeled for what it actually runs.

    Under upgrade-only precedence many declared postures clamp up to a strong
    profile's baseline. Keeping enumeration order would have labeled a
    least-privilege, isolated-backup configuration "seg-flat ... bak-connected"
    in every table and figure.
    """
    for profile_name in cfg.optimization.profiles:
        for portfolio in distinct_portfolios_for_profile(cfg, profile_name):
            eff = resolve(cfg, profile_name, portfolio)
            assert f"seg-{eff.segmentation.value}|" in portfolio.name, (
                f"{profile_name}: {portfolio.name} resolves to "
                f"{eff.segmentation.value}")
            assert f"|bak-{eff.backup_strategy}|" in portfolio.name, (
                f"{profile_name}: {portfolio.name} resolves to "
                f"backup={eff.backup_strategy}")


def test_deduplication_uses_the_same_resolution_as_execution(cfg):
    """Dedup must not resolve under library defaults while trials use config.

    ``rapid_isolation_success`` is 0.63 in the study config and 0.95 in the
    library default, so resolving without the config value can merge or split
    the wrong candidates.
    """
    assert cfg.simulation.rapid_isolation_success != 0.95, (
        "this test is only meaningful when the config overrides the default")
    for profile_name in cfg.optimization.profiles:
        candidates = distinct_portfolios_for_profile(cfg, profile_name)
        keys = set()
        for portfolio in candidates:
            eff = resolve(cfg, profile_name, portfolio)
            key = (eff.segmentation.value, round(eff.patch_coverage, 6),
                   eff.detection_delay, round(eff.isolation_success, 6),
                   eff.isolate_same_step, eff.backup_strategy,
                   eff.identity_controls)
            assert key not in keys, (
                f"{profile_name} kept two candidates that resolve identically "
                "under the study config")
            keys.add(key)


def test_stronger_profiles_have_fewer_remaining_decisions(cfg):
    """Sanity: a profile that already owns a control cannot re-buy it."""
    counts = {name: len(distinct_portfolios_for_profile(cfg, name))
              for name in cfg.optimization.profiles}
    assert (counts["resource_constrained"] > counts["intermediate_capacity"]
            > counts["high_capacity"]), counts


def test_candidate_set_is_deterministic(cfg):
    first = [p.name for p in distinct_portfolios_for_profile(cfg, "high_capacity")]
    second = [p.name for p in distinct_portfolios_for_profile(cfg, "high_capacity")]
    assert first == second

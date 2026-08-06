"""Unit tests for defense portfolios, effective settings, and costing."""

import pytest

from grrc.config import default_config, load_defense_costs
from grrc.defenses import (DefensePortfolio, PORTFOLIO_CATALOG,
                           boosted_patch_coverage, effective_settings,
                           enumerate_portfolios, get_portfolio,
                           improved_detection_delay, portfolio_cost)
from grrc.enums import BackupStrategy, SegmentationLevel
from grrc.utilities import REPO_ROOT

COSTS = {"basic_segmentation": 3, "least_privilege_segmentation": 5,
         "patch_level_upgrade": 2, "detection_improvement": 3,
         "rapid_isolation": 5, "protected_backups": 2,
         "identity_controls": 4}


@pytest.fixture
def cfg():
    return default_config()


def test_catalog_contains_all_required_conditions():
    required = {"baseline_flat", "basic_segmentation", "least_privilege",
                "patch_90", "fast_detection", "isolated_backups",
                "identity_controls", "seg_plus_patch", "seg_plus_detection",
                "detection_plus_backups", "patch_plus_least_privilege",
                "seg_detect_backup", "full_defense", "profile_baseline"}
    assert required <= set(PORTFOLIO_CATALOG)


def test_unknown_portfolio_raises():
    with pytest.raises(KeyError):
        get_portfolio("not_a_portfolio")


def test_patch_ladder_boosts():
    assert boosted_patch_coverage(0.25, 1) == 0.50
    assert boosted_patch_coverage(0.25, 3) == 0.90
    assert boosted_patch_coverage(0.75, 2) == 0.90  # capped at top rung
    assert boosted_patch_coverage(0.90, 1) == 0.90


def test_detection_ladder_improvement():
    assert improved_detection_delay(24) == 12
    assert improved_detection_delay(3) == 1
    assert improved_detection_delay(1) == 1


def test_effective_settings_resolution(cfg):
    prof = cfg.profiles["resource_constrained"]
    eff = effective_settings(prof, get_portfolio("full_defense"))
    assert eff.segmentation == SegmentationLevel.LEAST_PRIVILEGE
    assert eff.patch_coverage == 0.90
    assert eff.detection_delay == 12  # 24 improved one tier
    assert eff.isolation_success >= 0.95
    assert eff.backup_strategy == "isolated"
    assert eff.identity_controls

    base = effective_settings(prof, get_portfolio("profile_baseline"))
    assert base.segmentation.value == prof.base_segmentation
    assert base.patch_coverage == prof.patch_coverage
    assert base.detection_delay == prof.detection_delay_steps


def test_rapid_isolation_success_can_be_configured(cfg):
    """The per-step hazard is explicit for time-step convergence tests."""
    prof = cfg.profiles["resource_constrained"]
    eff = effective_settings(
        prof, get_portfolio("fast_detection"),
        rapid_isolation_success=0.80)
    assert eff.isolation_success == 0.80


def test_detection_improvement_factor_preserves_clock_time(cfg):
    prof = cfg.profiles["intermediate_capacity"]
    eff = effective_settings(
        prof, get_portfolio("fast_detection"),
        detection_improvement_factor=0.5)
    assert eff.detection_delay == 6


def test_sweep_overrides_take_precedence(cfg):
    prof = cfg.profiles["intermediate_capacity"]
    eff = effective_settings(prof, get_portfolio("baseline_flat"),
                             patch_override=0.33, detection_override=7)
    assert eff.patch_coverage == 0.33
    assert eff.detection_delay == 7


def test_portfolio_cost_depends_on_profile_start(cfg):
    p = get_portfolio("patch_90")
    low = portfolio_cost(p, cfg.profiles["resource_constrained"], COSTS)
    high = portfolio_cost(p, cfg.profiles["high_capacity"], COSTS)
    assert low == 3 * COSTS["patch_level_upgrade"]  # 0.25 -> 0.90 = 3 rungs
    assert high == 1 * COSTS["patch_level_upgrade"]  # 0.75 -> 0.90 = 1 rung
    assert portfolio_cost(get_portfolio("baseline_flat"),
                          cfg.profiles["resource_constrained"], COSTS) == 0


def test_full_defense_cost_sums_components(cfg):
    p = get_portfolio("full_defense")
    cost = portfolio_cost(p, cfg.profiles["resource_constrained"], COSTS)
    expected = (COSTS["least_privilege_segmentation"]
                + 3 * COSTS["patch_level_upgrade"]
                + COSTS["detection_improvement"] + COSTS["rapid_isolation"]
                + COSTS["protected_backups"] + COSTS["identity_controls"])
    assert cost == expected


def test_cost_scaling_is_linear(cfg):
    p = get_portfolio("full_defense")
    prof = cfg.profiles["intermediate_capacity"]
    assert portfolio_cost(p, prof, COSTS, scale=0.5) == pytest.approx(
        0.5 * portfolio_cost(p, prof, COSTS))


def test_enumerated_space_size_and_uniqueness():
    # 3 segmentation x 4 patch boosts (0..3, so 90% is reachable from the
    # 25% baseline) x 2 detection x 2 isolation x 2 backup x 2 identity.
    space = list(enumerate_portfolios())
    assert len(space) == 192
    assert len({p.name for p in space}) == 192


def test_defense_costs_yaml_loads():
    costs = load_defense_costs(REPO_ROOT / "configs" / "defense_costs.yaml")
    assert costs["basic_segmentation"] == 3
    assert costs["least_privilege_segmentation"] == 5

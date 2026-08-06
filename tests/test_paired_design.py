"""Checks for the common-random-number confirmatory design."""

import numpy as np

from grrc.config import default_config
from grrc.defenses import effective_settings, get_portfolio
from grrc.enums import BackupStrategy, SegmentationLevel
from grrc.models import TrialSpec
from grrc.network_generator import apply_controls_to_base, generate_network
from grrc.simulation import run_trial
from grrc.utilities import trial_rng


def _paired_spec(portfolio: str, trial_id: int = 1) -> TrialSpec:
    return TrialSpec(
        trial_id=trial_id, experiment="test-paired",
        facility="regional_hospital", profile="intermediate_capacity",
        portfolio=portfolio, entry_point="workstation", master_seed=17,
        scenario_id=99, paired=True)


def test_paired_scenario_is_independent_of_trial_id():
    a = run_trial(default_config(), _paired_spec("baseline_flat", 1))
    b = run_trial(default_config(), _paired_spec("baseline_flat", 500))
    ignored = {"trial_id"}
    assert {k: v for k, v in a.items() if k not in ignored} == {
        k: v for k, v in b.items() if k not in ignored}


def test_paired_portfolios_share_base_nodes_and_nested_patch_draws():
    cfg = default_config()
    rng = trial_rng(17, 99, stream_id=0)
    base = generate_network(
        cfg, "regional_hospital", "intermediate_capacity", rng,
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.0,
        backup_strategy=BackupStrategy.CONNECTED.value)
    low_eff = effective_settings(
        cfg.profiles["intermediate_capacity"],
        get_portfolio("baseline_flat"))
    high_eff = effective_settings(
        cfg.profiles["intermediate_capacity"], get_portfolio("patch_90"))
    low = apply_controls_to_base(
        cfg, base, segmentation=low_eff.segmentation,
        patch_coverage=low_eff.patch_coverage,
        backup_strategy=low_eff.backup_strategy)
    high = apply_controls_to_base(
        cfg, base, segmentation=high_eff.segmentation,
        patch_coverage=high_eff.patch_coverage,
        backup_strategy=high_eff.backup_strategy)
    assert low.n_nodes == high.n_nodes
    assert np.array_equal(low.zone, high.zone)
    assert np.array_equal(low.vulnerability, high.vulnerability)
    assert np.all(~low.patched | high.patched)


def test_paired_portfolios_use_same_entry_node():
    cfg = default_config()
    a = run_trial(cfg, _paired_spec("baseline_flat"))
    b = run_trial(cfg, _paired_spec("full_defense", 2))
    assert a["n_nodes"] == b["n_nodes"]
    assert a["entry_node"] == b["entry_node"]
    assert a["scenario_id"] == b["scenario_id"] == 99

"""Tests for the adaptive service-targeting attacker."""
from __future__ import annotations

from grrc.attacker import AdaptiveAttackerSimulation
from grrc.config import default_config
from grrc.defenses import EffectiveSettings
from grrc.enums import SegmentationLevel
from grrc.network_generator import generate_network
from grrc.propagation import RansomwareSimulation
from grrc.simulation import choose_entry
from grrc.utilities import trial_rng


def _setup(seed=1, delay=6):
    cfg = default_config()
    net = generate_network(
        cfg, "regional_hospital", "intermediate_capacity",
        trial_rng(seed, 0), segmentation=SegmentationLevel.FLAT,
        patch_coverage=0.5, backup_strategy="connected")
    eff = EffectiveSettings(
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.5,
        detection_delay=delay, isolation_success=0.7, isolate_same_step=False,
        backup_strategy="connected", identity_controls=False)
    entry = choose_entry(net, "workstation", trial_rng(seed, 0))
    return cfg, net, eff, entry


def test_focus_zero_matches_base_attacker():
    """focus=0 must reproduce the base engine exactly on matched inputs."""
    cfg, net, eff, entry = _setup()
    base = RansomwareSimulation(cfg, net, eff, trial_rng(1, 9)).run(entry)
    atk = AdaptiveAttackerSimulation(cfg, net, eff, trial_rng(1, 9),
                                     focus=0.0).run(entry)
    assert base == atk


def test_targeting_does_not_reduce_damage():
    """A value-seeking attacker should not do LESS damage than the base one
    (averaged over matched trials); check it holds on aggregate."""
    cfg, net, eff, entry = _setup()
    base_tot = adap_tot = 0.0
    for k in range(15):
        e = choose_entry(net, "workstation", trial_rng(1, k))
        base_tot += RansomwareSimulation(
            cfg, net, eff, trial_rng(2, k)).run(e)["weighted_service_hours_lost"]
        adap_tot += AdaptiveAttackerSimulation(
            cfg, net, eff, trial_rng(2, k),
            focus=3.0).run(e)["weighted_service_hours_lost"]
    assert adap_tot >= base_tot


def test_value_norm_in_unit_range():
    cfg, net, eff, _ = _setup()
    sim = AdaptiveAttackerSimulation(cfg, net, eff, trial_rng(1, 1), focus=3.0)
    assert sim._value_norm.min() >= 0.0
    assert sim._value_norm.max() <= 1.0

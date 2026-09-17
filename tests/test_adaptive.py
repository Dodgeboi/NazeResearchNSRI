"""Tests for the reactive-segmentation extension (grrc.adaptive).

Two guarantees matter:
  1. The extension seams do not change baseline dynamics — the ``open``
     posture with zero operational cost must reproduce the base engine
     exactly on the same network and RNG.
  2. The reactive controller actually engages/clamps when an intrusion is
     detected, and the ``static`` posture protects from t=0.
"""
from __future__ import annotations

import numpy as np

from grrc.adaptive import AdaptiveSimulation
from grrc.config import default_config
from grrc.defenses import EffectiveSettings
from grrc.enums import SegmentationLevel
from grrc.network_generator import generate_network
from grrc.propagation import RansomwareSimulation
from grrc.simulation import choose_entry
from grrc.utilities import trial_rng


def _net_and_eff(seed=1, delay=6):
    cfg = default_config()
    net = generate_network(
        cfg, "regional_hospital", "intermediate_capacity",
        trial_rng(seed, 0), segmentation=SegmentationLevel.FLAT,
        patch_coverage=0.5, backup_strategy="connected")
    eff = EffectiveSettings(
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.5,
        detection_delay=delay, isolation_success=0.7,
        isolate_same_step=False, backup_strategy="connected",
        identity_controls=False)
    entry = choose_entry(net, "workstation", trial_rng(seed, 0))
    return cfg, net, eff, entry


def test_open_posture_matches_baseline():
    """open + zero cost == the untouched base engine on identical inputs."""
    cfg, net, eff, entry = _net_and_eff()

    base = RansomwareSimulation(cfg, net, eff, trial_rng(1, 99))
    base_metrics = base.run(entry)

    adapt = AdaptiveSimulation(
        cfg, net, eff, trial_rng(1, 99), posture="open",
        seg_clamp=0.25, avail_cost_frac=0.0)
    adapt_metrics = adapt.run(entry)

    assert base_metrics == adapt_metrics


def test_static_posture_reduces_spread_vs_open():
    """Always-on clamp should not increase compromise on a matched draw."""
    cfg, net, eff, entry = _net_and_eff(seed=3)
    open_m = AdaptiveSimulation(cfg, net, eff, trial_rng(3, 7),
                                posture="open", seg_clamp=0.25,
                                avail_cost_frac=0.0).run(entry)
    static_m = AdaptiveSimulation(cfg, net, eff, trial_rng(3, 7),
                                  posture="static", seg_clamp=0.25,
                                  avail_cost_frac=0.0).run(entry)
    assert static_m["total_compromised"] <= open_m["total_compromised"]


def test_reactive_engages_after_detection():
    """Reactive posture engages segmentation once an intrusion is detected."""
    cfg, net, eff, entry = _net_and_eff(seed=5, delay=3)
    sim = AdaptiveSimulation(cfg, net, eff, trial_rng(5, 11),
                             posture="reactive", seg_clamp=0.25,
                             avail_cost_frac=0.2, trigger=1, hold=6)
    sim.run(entry)
    # An attack was seeded, so detection should fire and engagement occur.
    assert sim.first_engage_step >= 1
    assert sim.engaged_steps > 0


def test_workflow_block_set_scales_with_cost():
    """Higher operational cost blocks at least as many workflow nodes."""
    cfg, net, eff, entry = _net_and_eff(seed=7)
    low = AdaptiveSimulation(cfg, net, eff, trial_rng(7, 1),
                             posture="static", seg_clamp=0.25,
                             avail_cost_frac=0.1)
    high = AdaptiveSimulation(cfg, net, eff, trial_rng(7, 1),
                              posture="static", seg_clamp=0.25,
                              avail_cost_frac=0.4)
    assert int(high.blocked.sum()) >= int(low.blocked.sum())
    assert int(low.blocked.sum()) >= 0

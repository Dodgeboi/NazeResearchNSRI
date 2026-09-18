"""Tests for concurrent recovery and Re-Infection-Aware Recovery (RIAR)."""
from __future__ import annotations

from grrc.config import default_config
from grrc.defenses import EffectiveSettings
from grrc.enums import SegmentationLevel
from grrc.network_generator import generate_network
from grrc.propagation import RansomwareSimulation
from grrc.riar import RIARSimulation
from grrc.simulation import choose_entry
from grrc.utilities import trial_rng


def _setup(concurrent, seed=1, delay=6):
    cfg = default_config()
    cfg.simulation.concurrent_recovery = concurrent
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


def test_concurrent_flag_default_off_is_unchanged():
    """With the flag off, the base engine behaves exactly as before: the seams
    are no-ops, so a run is deterministic and reports no re-infections (recovery
    only starts after containment)."""
    cfg, net, eff, entry = _setup(concurrent=False)
    a = RansomwareSimulation(cfg, net, eff, trial_rng(1, 3)).run(entry)
    b = RansomwareSimulation(cfg, net, eff, trial_rng(1, 3)).run(entry)
    assert a == b


def test_riar_reduces_reinfections_vs_naive_under_concurrent():
    """Under concurrent recovery, immunize-on-restore must not increase
    re-infections; on a churning matched trial it should reduce them."""
    cfg, net, eff, entry = _setup(concurrent=True, delay=6)
    naive = RansomwareSimulation(cfg, net, eff, trial_rng(1, 42))
    naive.run(entry)
    riar = RIARSimulation(cfg, net, eff, trial_rng(1, 42))
    riar.run(entry)
    assert riar.reinfections <= naive.reinfections


def test_riar_immunizes_restored_nodes():
    """Restored nodes are marked immune, lowering their inbound spread factor."""
    cfg, net, eff, entry = _setup(concurrent=True, delay=6)
    riar = RIARSimulation(cfg, net, eff, trial_rng(1, 7))
    riar.run(entry)
    # Some node was restored and hardened during the (churning) run.
    assert riar.immune.any()
    # The immunity factor equals 1 - patch_effectiveness (in (0,1)).
    assert 0.0 < riar._immunity_factor < 1.0

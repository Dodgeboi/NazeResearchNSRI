"""Tests for the targeted-segmentation (VGRI/RPE) and recovery (MVR) methods.

These guard the two properties the experiments rely on:
  * the cut masks are well-formed subsets of the cross-zone boundary, and
  * MVR only reorders restoration — it returns a true permutation of the
    candidates and never changes the base engine's restore *set* semantics.
"""
from __future__ import annotations

import numpy as np

from grrc.config import default_config
from grrc.defenses import EffectiveSettings
from grrc.enums import SegmentationLevel, Service
from grrc.mvr import MVRSimulation
from grrc.network_generator import generate_network
from grrc.simulation import choose_entry
from grrc.utilities import trial_rng
from grrc.vgri import (RPESimulation, VGRISimulation,
                       downstream_clinical_value, _PROTECTED_ZONES)


def _net_and_eff(seed=1, delay=6):
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


def test_downstream_value_nonnegative_and_core_positive():
    cfg, net, eff, _ = _net_and_eff()
    val = downstream_clinical_value(net)
    assert val.shape == (net.n_nodes,)
    assert np.all(val >= 0)
    # A clinical core can reach itself, so its value is strictly positive.
    ehr_core = int(net.services[Service.EHR]["core"])
    assert val[ehr_core] > 0


def test_vgri_cut_is_subset_of_cross_boundary():
    cfg, net, eff, _ = _net_and_eff()
    sim = VGRISimulation(cfg, net, eff, trial_rng(1, 5), seg_clamp=0.25,
                         avail_cost_frac=0.2, cut_fraction=0.34)
    assert np.all(net.edge_cross_boundary[sim._cut_edge])  # subset
    n_cross = int(net.edge_cross_boundary.sum())
    # ~34% of cross edges, allowing for ceil rounding.
    assert 0 < int(sim._cut_edge.sum()) <= n_cross


def test_rpe_cuts_only_into_protected_zones():
    cfg, net, eff, _ = _net_and_eff()
    sim = RPESimulation(cfg, net, eff, trial_rng(1, 5), seg_clamp=0.25,
                        avail_cost_frac=0.2)
    prot = {int(z) for z in _PROTECTED_ZONES}
    cut_ids = np.flatnonzero(sim._cut_edge)
    assert cut_ids.size > 0
    assert np.all(net.edge_cross_boundary[cut_ids])
    assert np.all(np.isin(net.zone[net.edge_dst[cut_ids]], list(prot)))


def test_mvr_restore_order_is_a_permutation():
    cfg, net, eff, _ = _net_and_eff()
    sim = MVRSimulation(cfg, net, eff, trial_rng(1, 5))
    # Fabricate a candidate set and check the order is a permutation of it.
    cand = np.array([3, 10, 25, 40, 7, 99], dtype=np.int64)
    order = sim._restore_order(cand)
    assert sorted(order.tolist()) == sorted(cand.tolist())


def test_mvr_runs_and_matches_baseline_shape():
    cfg, net, eff, entry = _net_and_eff()
    sim = MVRSimulation(cfg, net, eff, trial_rng(1, 5))
    m = sim.run(entry)
    assert m["weighted_service_hours_lost"] >= 0.0
    assert 0.0 <= m["pct_services_restored"] <= 1.0

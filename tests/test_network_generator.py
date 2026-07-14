"""Unit tests for the synthetic network generator."""

import numpy as np
import pytest

from grrc.config import default_config
from grrc.enums import EntryPoint, SegmentationLevel, Service, Zone
from grrc.network_generator import (allowed_zone_pairs, generate_network,
                                    REQUIRED_PATHS)
from grrc.utilities import trial_rng


@pytest.fixture
def cfg():
    return default_config()


def _gen(cfg, facility="small_clinic", profile="resource_constrained",
         seg=SegmentationLevel.FLAT, patch=0.5, backup="connected", seed=1):
    return generate_network(cfg, facility, profile, trial_rng(cfg.seed, seed),
                            segmentation=seg, patch_coverage=patch,
                            backup_strategy=backup)


def test_node_count_within_facility_range(cfg):
    for facility, lo, hi in [("small_clinic", 40, 60),
                             ("regional_hospital", 200, 300),
                             ("large_hospital", 750, 1000)]:
        net = _gen(cfg, facility=facility, seed=7)
        # min-per-zone adjustment can add a handful of nodes at the low end
        assert lo - 5 <= net.n_nodes <= hi + 5


def test_every_zone_present(cfg):
    net = _gen(cfg)
    for zone in Zone:
        assert net.nodes_in_zone(zone).size >= cfg.network.min_nodes_per_zone


def test_attributes_in_valid_ranges(cfg):
    net = _gen(cfg, facility="regional_hospital")
    assert np.all((net.vulnerability >= 0) & (net.vulnerability <= 1))
    assert np.all((net.edge_access >= 0) & (net.edge_access <= 1))
    assert np.all((net.edge_traversal_mod >= 0)
                  & (net.edge_traversal_mod <= 1))
    assert net.n_edges == len(net.edge_dst) == len(net.edge_access)
    assert np.all(net.edge_src != net.edge_dst), "no self-loops"


def test_patch_coverage_scales_with_setting(cfg):
    low = _gen(cfg, patch=0.1, seed=3)
    high = _gen(cfg, patch=0.9, seed=3)
    assert high.patched.mean() > low.patched.mean()


def test_segmentation_restricts_cross_zone_pairs(cfg):
    flat = allowed_zone_pairs(SegmentationLevel.FLAT)
    basic = allowed_zone_pairs(SegmentationLevel.BASIC)
    lp = allowed_zone_pairs(SegmentationLevel.LEAST_PRIVILEGE)
    assert lp < basic < flat
    assert lp == REQUIRED_PATHS


def test_least_privilege_lowers_traversal_modifiers(cfg):
    flat = _gen(cfg, seg=SegmentationLevel.FLAT, seed=5)
    lp = _gen(cfg, seg=SegmentationLevel.LEAST_PRIVILEGE, seed=5)
    flat_cross = flat.edge_traversal_mod[flat.edge_cross_boundary]
    lp_cross = lp.edge_traversal_mod[lp.edge_cross_boundary]
    assert lp_cross.mean() < flat_cross.mean()


def test_isolated_backup_has_no_inbound_cross_zone_edges(cfg):
    net = _gen(cfg, backup="isolated", seed=9)
    backup_nodes = set(net.nodes_in_zone(Zone.BACKUP).tolist())
    inbound = [e for e in range(net.n_edges)
               if int(net.edge_dst[e]) in backup_nodes
               and int(net.edge_src[e]) not in backup_nodes]
    assert inbound == []


def test_entry_candidates_nonempty_and_in_right_zone(cfg):
    net = _gen(cfg, facility="regional_hospital", seed=11)
    for ep in EntryPoint:
        assert net.entry_candidates[ep].size > 0, ep
    ws = net.entry_candidates[EntryPoint.WORKSTATION]
    assert np.all(net.zone[ws] == int(Zone.WORKSTATION))
    for v in net.entry_candidates[EntryPoint.VENDOR_CONNECTION]:
        assert net.node_type[int(v)] == "vendor_gateway"


def test_service_map_complete(cfg):
    net = _gen(cfg, seed=13)
    assert set(net.services) == set(Service)
    for svc, info in net.services.items():
        assert info["nodes"].size > 0
        assert 0 <= info["core"] < net.n_nodes


def test_topology_varies_between_trials(cfg):
    a = _gen(cfg, seed=100)
    b = _gen(cfg, seed=101)
    assert (a.n_nodes != b.n_nodes) or (a.n_edges != b.n_edges) or (
        not np.array_equal(a.vulnerability[:min(a.n_nodes, b.n_nodes)],
                           b.vulnerability[:min(a.n_nodes, b.n_nodes)]))

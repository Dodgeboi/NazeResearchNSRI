"""Tests of the critical-service dependency model."""

import numpy as np
import pytest

from grrc.config import default_config
from grrc.enums import SegmentationLevel, Service, Zone
from grrc.network_generator import generate_network
from grrc.service_dependencies import service_availability
from grrc.utilities import trial_rng


@pytest.fixture
def net():
    cfg = default_config()
    return generate_network(
        cfg, "regional_hospital", "high_capacity", trial_rng(cfg.seed, 21),
        segmentation=SegmentationLevel.BASIC, patch_coverage=0.9,
        backup_strategy="connected")


THRESHOLD = 0.6


def test_all_functional_means_all_available(net):
    ok = np.ones(net.n_nodes, dtype=bool)
    assert all(service_availability(net, ok, THRESHOLD).values())


def test_core_node_failure_downs_service(net):
    ok = np.ones(net.n_nodes, dtype=bool)
    ok[net.services[Service.PHARMACY]["core"]] = False
    avail = service_availability(net, ok, THRESHOLD)
    assert not avail[Service.PHARMACY]
    assert avail[Service.LABORATORY]


def test_threshold_fraction_of_support_nodes(net):
    nodes = net.services[Service.LABORATORY]["nodes"]
    ok = np.ones(net.n_nodes, dtype=bool)
    # disable just under the threshold: service stays up (core kept alive)
    core = net.services[Service.LABORATORY]["core"]
    non_core = np.array([n for n in nodes if n != core])
    n_down_ok = int(np.floor((1 - THRESHOLD) * nodes.size))
    ok[non_core[:n_down_ok]] = False
    assert service_availability(net, ok, THRESHOLD)[Service.LABORATORY]
    # push past the threshold: service goes down
    ok[non_core[:min(non_core.size, n_down_ok + 2)]] = False
    assert not service_availability(net, ok, THRESHOLD)[Service.LABORATORY]


def test_identity_outage_cascades(net):
    ok = np.ones(net.n_nodes, dtype=bool)
    ok[net.nodes_in_zone(Zone.IDENTITY)] = False
    avail = service_availability(net, ok, THRESHOLD)
    for svc in (Service.EHR, Service.LABORATORY, Service.PHARMACY,
                Service.IMAGING, Service.SCHEDULING):
        assert not avail[svc], f"{svc} should require identity"
    assert avail[Service.BACKUP_RECOVERY], \
        "backup service does not depend on identity"


def test_isolation_counts_as_unavailable():
    """Defensive isolation reduces service availability (tradeoff)."""
    cfg = default_config()
    net = generate_network(
        cfg, "small_clinic", "high_capacity", trial_rng(cfg.seed, 22),
        segmentation=SegmentationLevel.BASIC, patch_coverage=0.9,
        backup_strategy="connected")
    functional = np.ones(net.n_nodes, dtype=bool)
    functional[net.services[Service.EHR]["core"]] = False  # e.g. isolated
    assert not service_availability(net, functional,
                                    THRESHOLD)[Service.EHR]

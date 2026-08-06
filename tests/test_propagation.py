"""Unit tests for the compromise-propagation state machine."""

import numpy as np
import pytest

from grrc.config import default_config
from grrc.defenses import get_portfolio, effective_settings
from grrc.enums import CLINICAL_SERVICES, Service
from grrc.propagation import RansomwareSimulation
from grrc.utilities import trial_rng
from grrc.validation import (_aggressive_config, _toy_network)


@pytest.fixture
def cfg():
    return _aggressive_config()


def _sim(cfg, net, profile="resource_constrained"):
    eff = effective_settings(cfg.profiles[profile],
                             get_portfolio("baseline_flat"))
    return RansomwareSimulation(cfg, net, eff, trial_rng(cfg.seed, 1))


def test_chain_spreads_one_hop_per_step(cfg):
    net = _toy_network([(0, 1), (1, 2)], n=3)
    sim = _sim(cfg, net)
    rng = trial_rng(cfg.seed, 2)
    sim.compromise(np.array([0]), 0)
    sim._spread(1, rng)
    assert sim.comp.tolist() == [True, True, False], \
        "p=1 spreads exactly one hop in one step"
    sim._spread(2, rng)
    assert sim.comp.tolist() == [True, True, True]


def test_edges_are_directed(cfg):
    net = _toy_network([(0, 1)], n=3)  # no edge back to 0, none to/from 2
    sim = _sim(cfg, net)
    rng = trial_rng(cfg.seed, 3)
    sim.compromise(np.array([1]), 0)
    for t in range(1, 10):
        sim._spread(t, rng)
    assert not sim.comp[0], "infection must not travel against direction"
    assert not sim.comp[2]


def test_probabilities_stay_in_unit_interval():
    cfg = default_config()
    cfg.simulation.base_spread_rate = 1.0
    cfg.simulation.identity_breach_multiplier = 5.0
    from grrc.network_generator import generate_network
    from grrc.enums import SegmentationLevel
    net = generate_network(cfg, "small_clinic", "high_capacity",
                           trial_rng(1, 1),
                           segmentation=SegmentationLevel.FLAT,
                           patch_coverage=0.0, backup_strategy="connected")
    sim = _sim(cfg, net, profile="high_capacity")
    assert np.all(sim.edge_p >= 0) and np.all(sim.edge_p <= 1)


def test_detection_and_isolation_lifecycle():
    cfg = _aggressive_config()
    cfg.simulation.detection_model = "fixed"
    for prof in cfg.profiles.values():
        prof.detection_delay_steps = 2
        prof.isolation_success = 1.0
    net = _toy_network([(0, 1), (1, 2), (2, 0)], n=3)
    eff = effective_settings(cfg.profiles["resource_constrained"],
                             get_portfolio("baseline_flat"))
    sim = RansomwareSimulation(cfg, net, eff, trial_rng(cfg.seed, 4))
    row = sim.run(entry_node=0)
    # every compromised node must eventually be detected then isolated
    for node in np.flatnonzero(sim.ever_comp):
        assert sim.time_detected[node] >= 0
        assert sim.time_isolated[node] >= sim.time_detected[node]
    assert row["containment_step"] > 0


def test_restoration_completes_after_containment():
    cfg = _aggressive_config()
    cfg.simulation.detection_model = "fixed"
    cfg.simulation.restore_rate_min = 5.0
    for prof in cfg.profiles.values():
        prof.detection_delay_steps = 1
        prof.isolation_success = 1.0
    net = _toy_network([(0, 1), (1, 2)], n=3)
    eff = effective_settings(cfg.profiles["resource_constrained"],
                             get_portfolio("baseline_flat"))
    sim = RansomwareSimulation(cfg, net, eff, trial_rng(cfg.seed, 5))
    sim.run(entry_node=0)
    assert sim.restored[np.flatnonzero(sim.ever_comp)].all(), \
        "all compromised nodes should be restored within the horizon"
    assert not sim.comp.any()


def test_false_positive_isolation_expires():
    cfg = default_config()
    cfg.simulation.base_spread_rate = 0.0
    cfg.simulation.false_positive_rate = 0.5
    cfg.simulation.false_positive_duration = 2
    net = _toy_network([(0, 1)], n=8)
    eff = effective_settings(cfg.profiles["high_capacity"],
                             get_portfolio("baseline_flat"))
    sim = RansomwareSimulation(cfg, net, eff, trial_rng(cfg.seed, 6))
    rng = trial_rng(cfg.seed, 7)
    sim._false_positives(1, rng)
    assert sim.fp_isolated.any(), "with rate 0.5 some FP should occur"
    frozen = sim.fp_isolated.copy()
    # Disable new false positives, then step far past every release time so
    # we test the *release* semantics in isolation: no re-flagging can mask
    # a failure to release. (Previously this assertion was `... or True`,
    # which could never fail.)
    cfg.simulation.false_positive_rate = 0.0
    sim._false_positives(10, rng)  # far past every release time
    assert not (sim.fp_isolated & frozen).any(), \
        "all step-1 false-positive isolations should have been released"
    # released nodes are functional again unless re-flagged this step
    released = frozen & ~sim.fp_isolated
    assert not sim.isolated[released].any()


def test_metrics_row_is_internally_consistent():
    cfg = default_config()
    from grrc.models import TrialSpec
    from grrc.simulation import run_trial
    spec = TrialSpec(1, "test", "small_clinic", "resource_constrained",
                     "baseline_flat", "workstation", master_seed=cfg.seed)
    row = run_trial(cfg, spec)
    assert 1 <= row["total_compromised"] <= row["n_nodes"]
    assert 0 <= row["pct_compromised"] <= 1
    assert row["peak_compromised"] <= row["total_compromised"]
    assert 0 <= row["zones_reached"] <= 10
    assert row["steps_simulated"] <= cfg.simulation.max_steps
    assert row["weighted_service_hours_lost"] >= 0


def test_derived_ratios_are_independently_recomputable():
    cfg = default_config()
    from grrc.models import TrialSpec
    from grrc.simulation import run_trial
    spec = TrialSpec(2, "metric_audit", "small_clinic",
                     "resource_constrained", "baseline_flat",
                     "workstation", master_seed=cfg.seed)
    row = run_trial(cfg, spec)

    expected_compromised = row["total_compromised"] / row["n_nodes"]
    assert row["ever_compromised_fraction"] == pytest.approx(
        expected_compromised)
    assert row["pct_compromised"] == pytest.approx(expected_compromised)

    weights = cfg.service_weights.as_dict()
    clinical_weighted_steps = sum(
        weights[s.value] * row[f"{s.value}_downtime_steps"]
        for s in CLINICAL_SERVICES)
    clinical_weight_total = sum(weights[s.value]
                                for s in CLINICAL_SERVICES)
    expected_unavailability = (
        clinical_weighted_steps
        / (clinical_weight_total * row["horizon_steps"]))
    assert row["time_averaged_weighted_clinical_unavailability"] \
        == pytest.approx(expected_unavailability)
    assert row["pct_clinical_capacity_lost"] == pytest.approx(
        expected_unavailability)

    final_flags = [row[f"{s.value}_available_final"] for s in Service]
    expected_final = sum(final_flags) / len(final_flags)
    assert row["final_service_availability_fraction"] == pytest.approx(
        expected_final)
    assert row["pct_services_restored"] == pytest.approx(expected_final)

    disrupted = [s for s in Service
                 if row[f"{s.value}_downtime_steps"] > 0]
    expected_recovery = (sum(row[f"{s.value}_available_final"]
                             for s in disrupted) / len(disrupted)
                         if disrupted else 1.0)
    assert row["disrupted_service_recovery_fraction"] == pytest.approx(
        expected_recovery)

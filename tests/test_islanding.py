"""Dependency-closed controlled islanding: mechanism and inertness.

Specified in study/ISLANDING_SPECIFICATION.md. The mechanism tests pin the
properties the method's claim rests on — that disconnection without
dependency closure is itself an outage, that closure restores service, and
that the island-count rule holds in the availability function itself. The
inertness tests exist because this method touches service availability,
which is the study's endpoint: with the switch off it must be absent, not
merely small.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from grrc.config import default_config, load_defense_costs
from grrc.defenses import (DefensePortfolio, EffectiveSettings,
                           effective_settings, enumerate_portfolios,
                           get_portfolio, portfolio_cost)
from grrc.enums import (CLINICAL_SERVICES, BackupStrategy, SegmentationLevel,
                        Service)
from grrc.islanding import (SERVICE_CHAIN, ZONE, contained_island_mask,
                            island_restore_priority,
                            islanded_service_availability,
                            minimum_island_count, plan_islands)
from grrc.joint_stability import (ISLANDING_TARIFF_KEYS, TARIFF_KEYS,
                                  portfolio_features)
from grrc.models import TrialSpec
from grrc.multiobjective import (load_operational_burdens,
                                 portfolio_operational_burden)
from grrc.network_generator import generate_network
from grrc.optimization import (CONTROL_COLUMNS, ISLANDING_COLUMN,
                               distinct_portfolios_for_profile)
from grrc.propagation import RansomwareSimulation
from grrc.service_dependencies import service_availability
from grrc.simulation import run_trial
from grrc.utilities import trial_rng

ROOT = Path(__file__).resolve().parents[1]
COSTS = load_defense_costs(ROOT / "configs" / "defense_costs.yaml")
BURDENS = load_operational_burdens(ROOT / "configs" / "defense_burdens.yaml")
PROFILE = "intermediate_capacity"
THETA = 0.60


def _net(seed=4):
    return generate_network(
        default_config(), "regional_hospital", PROFILE,
        trial_rng(11, seed, stream_id=0),
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.5,
        backup_strategy=BackupStrategy.CONNECTED.value)


def _switched_on(cfg=None, **overrides):
    cfg = cfg or default_config()
    return dataclasses.replace(cfg, simulation=dataclasses.replace(
        cfg.simulation, islanding_enabled=True, **overrides))


def _clinical_up(avail):
    return all(avail[s] for s in CLINICAL_SERVICES)


def _clinical_down(avail):
    return not any(avail[s] for s in CLINICAL_SERVICES)


# ---------------------------------------------------------------------------
# Off by default
# ---------------------------------------------------------------------------

def test_switch_and_flags_default_off():
    assert default_config().simulation.islanding_enabled is False
    assert DefensePortfolio("x").islanding is False
    assert EffectiveSettings(
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.5,
        detection_delay=6, isolation_success=0.5, isolate_same_step=False,
        backup_strategy="connected",
        identity_controls=False).islanding is False


def test_search_space_unchanged_when_off_and_appended_when_on():
    base = list(enumerate_portfolios())
    ext = list(enumerate_portfolios(include_islanding=True))
    assert len(base) == 288 and not any(p.islanding for p in base)
    assert len(ext) == 576 and len({p.name for p in ext}) == 576
    # Original names and order are the join key to frozen results.
    assert [p.name for p in ext[:288]] == [p.name for p in base]
    assert all(p.islanding and p.name.endswith("|isl1") for p in ext[288:])


def test_full_defense_keeps_its_frozen_meaning():
    full = get_portfolio("full_defense")
    islanded = get_portfolio("full_defense_islanded")
    assert not full.islanding and islanded.islanding
    assert dataclasses.replace(islanded, name="full_defense",
                               islanding=False) == full
    prof = default_config().profiles[PROFILE]
    assert (portfolio_cost(islanded, prof, COSTS)
            - portfolio_cost(full, prof, COSTS)
            == pytest.approx(COSTS["islanding"]))


def test_schema_gated_on_switch():
    cfg = default_config()
    spec = TrialSpec(trial_id=2, experiment="t", facility="small_clinic",
                     profile=PROFILE, portfolio="baseline_flat",
                     entry_point="workstation", master_seed=5)
    assert "islanding" not in run_trial(cfg, spec)
    row = run_trial(_switched_on(cfg), spec)
    assert row["islanding"] == 0 and row["island_trip_step"] == -1


def test_unislanded_rows_identical_with_switch_on_or_off():
    """Switching the dimension on must not perturb any other candidate."""
    cfg = default_config()
    on = _switched_on(cfg)
    baseline_columns = set(run_trial(cfg, TrialSpec(
        trial_id=1, experiment="t", facility="small_clinic", profile=PROFILE,
        portfolio="baseline_flat", entry_point="workstation", master_seed=1)))
    # Every islanding column is named island*, and no pre-existing one is,
    # so a new islanding column cannot silently slip past this test.
    assert not any(c.startswith("island") for c in baseline_columns)
    for portfolio in ("baseline_flat", "full_defense", "profile_baseline"):
        for paired in (False, True):
            spec = TrialSpec(
                trial_id=9, scenario_id=(4 if paired else None),
                paired=paired, experiment="t", facility="regional_hospital",
                profile=PROFILE, portfolio=portfolio,
                entry_point="vendor_connection", master_seed=606)
            on_row = {k: v for k, v in run_trial(on, spec).items()
                      if not k.startswith("island")}
            assert on_row == run_trial(cfg, spec)


def test_frozen_column_and_tariff_sets_not_extended_in_place():
    assert ISLANDING_COLUMN not in CONTROL_COLUMNS
    assert len(CONTROL_COLUMNS) == 7 and len(TARIFF_KEYS) == 8
    assert ISLANDING_TARIFF_KEYS == TARIFF_KEYS + ("islanding",)
    prof = default_config().profiles[PROFILE]
    p = get_portfolio("full_defense_islanded")
    assert portfolio_features(p, prof).shape == (8,)
    assert portfolio_features(p, prof, include_islanding=True)[8] == 1


def test_undeclared_tariff_raises_rather_than_charging_zero():
    prof = default_config().profiles[PROFILE]
    bought = DefensePortfolio("p", segmentation=SegmentationLevel.FLAT,
                              backup_override=BackupStrategy.CONNECTED,
                              islanding=True)
    legacy_costs = {k: v for k, v in COSTS.items() if k != "islanding"}
    legacy_burdens = {k: v for k, v in BURDENS.items() if k != "islanding"}
    assert portfolio_cost(dataclasses.replace(bought, islanding=False),
                          prof, legacy_costs) == 0.0
    with pytest.raises(KeyError, match="islanding"):
        portfolio_cost(bought, prof, legacy_costs)
    with pytest.raises(KeyError, match="islanding"):
        portfolio_operational_burden(bought, prof, legacy_burdens)


def test_islanded_candidates_are_not_deduplicated_away():
    cfg = default_config()
    off = distinct_portfolios_for_profile(cfg, PROFILE)
    on = distinct_portfolios_for_profile(_switched_on(cfg), PROFILE)
    assert len(on) == 2 * len(off)
    assert sorted(p.name for p in on if not p.islanding) == sorted(
        p.name for p in off)


def test_restore_priority_is_untouched_without_a_plan():
    cfg = default_config()
    net = _net()
    eff = effective_settings(cfg.profiles[PROFILE],
                             get_portfolio("baseline_flat"))
    sim = RansomwareSimulation(cfg, net, eff, trial_rng(1, 1))
    # The same object, not an equal copy: restoration order cannot move.
    assert sim.restore_priority is net.criticality


# ---------------------------------------------------------------------------
# The island-count rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("theta,expected", [
    (0.50, 2), (0.45, 2), (0.60, 3), (2 / 3, 3), (0.67, 4), (0.75, 4),
    (0.80, 5),
])
def test_minimum_island_count(theta, expected):
    assert minimum_island_count(theta) == expected


def test_rule_holds_in_the_availability_function_itself():
    """Lose one whole island: survivable iff k >= 1 / (1 - theta).

    Every node outside the lost island is functional, so this isolates the
    capacity arithmetic from spread entirely.
    """
    net = _net()
    for k, theta, survives in [(3, 0.60, True), (2, 0.60, False),
                               (2, 0.45, True), (4, 0.60, True)]:
        plan = plan_islands(net, k, dependency_closed=True)
        functional = plan.island != 1
        avail = islanded_service_availability(net, functional, theta, plan)
        assert (_clinical_up(avail) if survives else _clinical_down(avail)), \
            (k, theta)


# ---------------------------------------------------------------------------
# Dependency closure — the claim
# ---------------------------------------------------------------------------

def test_disconnection_without_closure_is_itself_an_outage():
    """The core of the claim, with no attacker at all.

    Every node is healthy. Severing three islands that have no replicas
    strands the two islands without the primary cores and identity, and the
    clinical services go down hospital-wide. The same cut with replicas
    changes nothing.
    """
    net = _net()
    healthy = np.ones(net.n_nodes, dtype=bool)
    crude = plan_islands(net, 3, dependency_closed=False)
    closed = plan_islands(net, 3, dependency_closed=True)
    assert _clinical_up(service_availability(net, healthy, THETA))
    assert _clinical_down(
        islanded_service_availability(net, healthy, THETA, crude))
    assert _clinical_up(
        islanded_service_availability(net, healthy, THETA, closed))


def test_single_island_reduces_exactly_to_the_connected_rule():
    net = _net()
    rng = np.random.default_rng(3)
    for closed in (True, False):
        plan = plan_islands(net, 1, closed)
        for _ in range(300):
            functional = rng.random(net.n_nodes) < rng.uniform(0.3, 1.0)
            expected = service_availability(net, functional, THETA)
            got = islanded_service_availability(net, functional, THETA, plan)
            assert got == expected and list(got) == list(expected)


def test_plan_is_vertical_balanced_and_deterministic():
    net = _net()
    plan = plan_islands(net, 3, True)
    assert np.array_equal(plan.island, plan_islands(net, 3, True).island)
    for z in np.unique(net.zone):
        sizes = np.bincount(plan.island[net.zone == z], minlength=3)
        assert sizes.max() - sizes.min() <= 1  # a slice of every zone


def test_closed_plan_has_a_core_per_island_and_crude_only_the_primary():
    net = _net()
    closed = plan_islands(net, 3, True)
    crude = plan_islands(net, 3, False)
    for svc, info in net.services.items():
        assert closed.island[info["core"]] == 0  # primary in island 0
        assert (closed.cores[svc] >= 0).all()
        assert list(crude.cores[svc]) == [info["core"], -1, -1]
        for i, node in enumerate(closed.cores[svc]):
            assert closed.island[node] == i
            assert node in set(np.asarray(info["nodes"]).tolist())
    assert crude.replicas.size == 0 and closed.replicas.size > 0


def test_replicas_restore_at_core_priority():
    net = _net()
    plan = plan_islands(net, 3, True)
    priority = island_restore_priority(net, plan)
    assert (priority[plan.replicas] >= 2.0).all()
    others = np.setdiff1d(np.arange(net.n_nodes), plan.replicas)
    assert np.array_equal(priority[others], net.criticality[others])


# ---------------------------------------------------------------------------
# Breakers, restoration, reconnection
# ---------------------------------------------------------------------------

def _islanded_sim(plan, cfg=None):
    cfg = cfg or default_config()
    eff = effective_settings(
        cfg.profiles[PROFILE],
        DefensePortfolio("i", segmentation=SegmentationLevel.FLAT,
                         backup_override=BackupStrategy.CONNECTED,
                         islanding=True))
    return RansomwareSimulation(cfg, _net(), eff, trial_rng(2, 2),
                                island_plan=plan)


def test_open_breakers_confine_spread_to_one_island():
    net = _net()
    plan = plan_islands(net, 3, True)
    seed = int(np.flatnonzero(plan.island == 1)[0])
    rng = np.random.default_rng(0)

    confined = _islanded_sim(plan)
    confined.islanded = True
    confined.compromise(np.array([seed]), 0)
    for t in range(1, 150):
        confined._spread(t, rng)
    assert confined.comp.sum() > 1, "must spread within the island"
    assert set(np.unique(plan.island[confined.comp])) == {1}

    # Not vacuous: with closed breakers the same seed crosses islands.
    free = _islanded_sim(plan)
    free.compromise(np.array([seed]), 0)
    for t in range(1, 150):
        free._spread(t, np.random.default_rng(t))
    assert np.unique(plan.island[free.comp]).size > 1


def test_zone_comparator_keeps_required_paths_and_dependencies():
    net = _net()
    plan = plan_islands(net, 3, True, partition=ZONE)
    assert plan.partition == ZONE and not plan.severs_dependencies
    same_zone = net.zone[net.edge_src] == net.zone[net.edge_dst]
    assert plan.traversable[same_zone].all()
    assert not plan.traversable.all()  # it does cut something
    closed = plan_islands(net, 3, True)
    assert closed.partition == SERVICE_CHAIN and closed.severs_dependencies


def test_contained_island_mask():
    net = _net()
    plan = plan_islands(net, 3, True)
    active = np.zeros(net.n_nodes, dtype=bool)
    active[np.flatnonzero(plan.island == 2)[0]] = True
    mask = contained_island_mask(plan, active)
    assert not mask[plan.island == 2].any()
    assert mask[plan.island != 2].all()


def test_local_restore_cannot_bank_capacity_for_a_burst():
    sim = _islanded_sim(plan_islands(_net(), 3, True))
    nothing = np.zeros(sim.net.n_nodes, dtype=bool)
    for t in range(1, 50):
        sim._restore_within(t, rate=3.7, eligible=nothing)
    assert sim.restore_carry == 0.0  # no work, no accrual
    node = int(np.flatnonzero(sim.island_plan.island == 1)[0])
    sim.comp[node] = sim.isolated[node] = True
    everything = ~nothing
    sim._restore_within(50, rate=3.7, eligible=everything)
    assert sim.restore_carry <= 3.7


def test_trial_trips_on_detection_and_reconnects_only_after_containment():
    cfg = _switched_on()
    seen_trip = False
    for sid in range(8):
        spec = TrialSpec(trial_id=sid, scenario_id=sid, paired=True,
                         experiment="t", facility="regional_hospital",
                         profile=PROFILE, portfolio="controlled_islanding",
                         entry_point="workstation", master_seed=77)
        row = run_trial(cfg, spec)
        if row["island_trip_step"] < 0:
            continue
        seen_trip = True
        assert row["islanded_steps"] >= 1
        if row["island_reconnect_step"] >= 0:
            assert row["containment_step"] >= 0
            assert row["island_reconnect_step"] >= row["containment_step"]
            assert row["island_reconnect_step"] >= row["island_trip_step"]
    assert seen_trip


def test_paired_islanded_trials_are_deterministic():
    cfg = _switched_on()
    spec = TrialSpec(trial_id=3, scenario_id=3, paired=True, experiment="t",
                     facility="regional_hospital", profile=PROFILE,
                     portfolio="controlled_islanding",
                     entry_point="medical_device", master_seed=12)
    assert run_trial(cfg, spec) == run_trial(cfg, spec)


def test_micro_lockdown_cuts_every_intra_zone_edge_and_keeps_required_paths():
    from grrc.islanding import ZONE_MICRO
    net = _net()
    plain = plan_islands(net, 3, True, partition=ZONE)
    micro = plan_islands(net, 3, True, partition=ZONE_MICRO)
    same_zone = net.zone[net.edge_src] == net.zone[net.edge_dst]
    assert not micro.traversable[same_zone].any()
    # Cross-zone treatment is identical: only the intra-zone edges differ.
    assert np.array_equal(micro.traversable[~same_zone],
                          plain.traversable[~same_zone])
    assert micro.traversable[~same_zone].any()  # required paths survive
    assert not micro.severs_dependencies


def test_micro_within_islands_is_the_intersection():
    net = _net()
    islands = plan_islands(net, 3, True)
    combined = plan_islands(net, 3, True, micro_within=True)
    from grrc.islanding import ZONE_MICRO
    micro = plan_islands(net, 3, True, partition=ZONE_MICRO)
    assert np.array_equal(combined.traversable,
                          islands.traversable & micro.traversable)
    assert combined.severs_dependencies
    assert np.array_equal(combined.island, islands.island)

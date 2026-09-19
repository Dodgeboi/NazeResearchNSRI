"""Vendor access mediation: mechanism, pricing, and inertness when off.

The control is specified in study/VENDOR_MEDIATION_SPECIFICATION.md. It fills
the one traversal mechanism the rebuild left uncontrolled: patching acts on
EXPLOIT edges, identity controls on CREDENTIAL edges, and before this control
nothing acted on VENDOR edges — which additionally enjoyed an exemption from
the segmentation permitted-pair filter.

Half these tests are about the mechanism. The other half exist because adding
a seventh control to a study with frozen protocols, archived result CSVs and a
byte-for-byte reproducibility claim is exactly the kind of change that breaks
those guarantees silently. They assert that with the master switch off, the
control is not merely small but *absent*.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from grrc.config import default_config, load_defense_costs
from grrc.defenses import (DefensePortfolio, EffectiveSettings,
                           describe_portfolio, effective_settings,
                           enumerate_portfolios, get_portfolio,
                           portfolio_cost)
from grrc.enums import BackupStrategy, SegmentationLevel, Zone
from grrc.joint_stability import (TARIFF_KEYS, VENDOR_MEDIATION_TARIFF_KEYS,
                                  portfolio_features)
from grrc.models import TrialSpec
from grrc.multiobjective import (load_operational_burdens,
                                 portfolio_operational_burden)
from grrc.network_generator import (VENDOR_PATHS, apply_controls_to_base,
                                    brokered_support_path_count,
                                    generate_network)
from grrc.optimization import (CONTROL_COLUMNS, VENDOR_MEDIATION_COLUMN,
                               distinct_portfolios_for_profile)
from grrc.simulation import run_trial
from grrc.utilities import trial_rng

ROOT = Path(__file__).resolve().parents[1]
COSTS = load_defense_costs(ROOT / "configs" / "defense_costs.yaml")
BURDENS = load_operational_burdens(ROOT / "configs" / "defense_burdens.yaml")
PROFILE = "intermediate_capacity"


def _base_graph(cfg, seed=99):
    """A flat/connected base graph, as the paired design builds it."""
    return generate_network(
        cfg, "regional_hospital", PROFILE, trial_rng(17, seed, stream_id=0),
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.0,
        backup_strategy=BackupStrategy.CONNECTED.value)


def _support_path_ids(base):
    """Edge ids of the vendor-gateway support paths on a base graph."""
    dst_zone = base.zone[base.edge_dst]
    gateway_src = np.array(
        [base.node_type[int(s)] == "vendor_gateway" for s in base.edge_src],
        dtype=bool)
    return np.flatnonzero(
        gateway_src & np.isin(dst_zone, [int(z) for z in VENDOR_PATHS]))


# ---------------------------------------------------------------------------
# Off by default
# ---------------------------------------------------------------------------

def test_master_switch_and_portfolio_flag_default_off():
    cfg = default_config()
    assert cfg.simulation.vendor_mediation_enabled is False
    assert DefensePortfolio("x").vendor_mediation is False
    assert EffectiveSettings(
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.5,
        detection_delay=6, isolation_success=0.5, isolate_same_step=False,
        backup_strategy="connected",
        identity_controls=False).vendor_mediation is False


def test_detection_gain_is_exactly_inert_by_default():
    # Not "small": exactly 1.0, so the default path performs no arithmetic on
    # detect_prob at all and cannot perturb it by a float rounding step.
    assert default_config().simulation.vendor_mediation_detection_gain == 1.0


def test_enumerated_space_unchanged_when_dimension_off():
    base = list(enumerate_portfolios())
    assert len(base) == 288
    assert all(not p.vendor_mediation for p in base)
    assert not any("vam" in p.name for p in base)


def test_extended_space_appends_and_never_renames():
    base = list(enumerate_portfolios())
    ext = list(enumerate_portfolios(include_vendor_mediation=True))
    assert len(ext) == 576
    assert len({p.name for p in ext}) == 576
    # The original candidates keep their exact names AND their order: those
    # names are the join key to the frozen result CSVs and protocol snapshots,
    # and list(enumerate_portfolios())[-1] is itself used as a test fixture.
    assert [p.name for p in ext[:288]] == [p.name for p in base]
    assert all(p.name.endswith("|vam1") and p.vendor_mediation
               for p in ext[288:])


def test_full_defense_keeps_its_frozen_meaning():
    full = get_portfolio("full_defense")
    mediated = get_portfolio("full_defense_mediated")
    assert full.vendor_mediation is False
    assert mediated.vendor_mediation is True
    prof = default_config().profiles[PROFILE]
    # The mediated condition differs from the frozen one by exactly the price
    # of the new control, and by nothing else.
    assert (portfolio_cost(mediated, prof, COSTS)
            - portfolio_cost(full, prof, COSTS)
            == pytest.approx(COSTS["vendor_mediation"]))
    assert dataclasses.replace(mediated, name="full_defense",
                               vendor_mediation=False) == full


def test_trial_row_schema_is_gated_on_the_master_switch():
    cfg = default_config()
    spec = TrialSpec(trial_id=3, experiment="t", facility="small_clinic",
                     profile=PROFILE, portfolio="baseline_flat",
                     entry_point="workstation", master_seed=11)
    assert "vendor_mediation" not in run_trial(cfg, spec)
    on = dataclasses.replace(
        cfg, simulation=dataclasses.replace(
            cfg.simulation, vendor_mediation_enabled=True))
    assert "vendor_mediation" in run_trial(on, spec)


def test_results_identical_for_an_unmediated_portfolio_either_way():
    """Switching the dimension on must not perturb unmediated candidates.

    This is the property that lets the 576-candidate space be compared against
    the frozen 288-candidate results at all.
    """
    cfg = default_config()
    on = dataclasses.replace(
        cfg, simulation=dataclasses.replace(
            cfg.simulation, vendor_mediation_enabled=True))
    for portfolio in ("baseline_flat", "full_defense", "least_privilege"):
        for entry in ("workstation", "vendor_connection"):
            for paired in (False, True):
                spec = TrialSpec(
                    trial_id=5, scenario_id=(2 if paired else None),
                    paired=paired, experiment="t",
                    facility="regional_hospital", profile=PROFILE,
                    portfolio=portfolio, entry_point=entry, master_seed=808)
                off_row = run_trial(cfg, spec)
                on_row = run_trial(on, spec)
                assert on_row.pop("vendor_mediation") == 0
                assert off_row == on_row


def test_frozen_column_and_tariff_sets_are_not_extended_in_place():
    assert VENDOR_MEDIATION_COLUMN not in CONTROL_COLUMNS
    assert len(CONTROL_COLUMNS) == 7
    assert len(TARIFF_KEYS) == 8
    assert VENDOR_MEDIATION_TARIFF_KEYS == TARIFF_KEYS + ("vendor_mediation",)


def test_price_feature_vector_keeps_its_dimension_by_default():
    # The simultaneous screen is computed over a price region whose dimension
    # is this vector's length. Widening it silently would change every
    # published retention count.
    cfg = default_config()
    prof = cfg.profiles[PROFILE]
    p = get_portfolio("full_defense_mediated")
    assert portfolio_features(p, prof).shape == (8,)
    extended = portfolio_features(p, prof, include_vendor_mediation=True)
    assert extended.shape == (9,)
    assert extended[8] == 1
    assert np.array_equal(extended[:8], portfolio_features(p, prof))
    assert portfolio_features(get_portfolio("full_defense"), prof,
                              include_vendor_mediation=True)[8] == 0


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

def test_control_is_free_only_when_not_bought():
    prof = default_config().profiles[PROFILE]
    plain = DefensePortfolio("p", segmentation=SegmentationLevel.FLAT,
                             backup_override=BackupStrategy.CONNECTED)
    bought = dataclasses.replace(plain, vendor_mediation=True)
    assert portfolio_cost(plain, prof, COSTS) == 0.0
    assert portfolio_cost(bought, prof, COSTS) == COSTS["vendor_mediation"]
    assert portfolio_operational_burden(plain, prof, BURDENS) == 0.0
    assert (portfolio_operational_burden(bought, prof, BURDENS)
            == BURDENS["vendor_mediation"])


def test_undeclared_tariff_raises_rather_than_charging_zero():
    """Audit ISSUE-003/ISSUE-004 in miniature.

    A tariff file written before this control existed must still load — the
    config snapshots archived beside every frozen run are such files. But a
    portfolio that BUYS the control must never be silently priced at zero,
    because a free control is one the optimizer will always take.
    """
    prof = default_config().profiles[PROFILE]
    legacy = {k: v for k, v in COSTS.items() if k != "vendor_mediation"}
    bought = DefensePortfolio("p", segmentation=SegmentationLevel.FLAT,
                              backup_override=BackupStrategy.CONNECTED,
                              vendor_mediation=True)
    unbought = dataclasses.replace(bought, vendor_mediation=False)
    # A legacy table still prices every legacy portfolio.
    assert portfolio_cost(unbought, prof, legacy) == 0.0
    with pytest.raises(KeyError, match="vendor_mediation"):
        portfolio_cost(bought, prof, legacy)
    with pytest.raises(KeyError, match="vendor_mediation"):
        portfolio_operational_burden(
            bought, prof,
            {k: v for k, v in BURDENS.items() if k != "vendor_mediation"})


def test_shipped_tariff_files_declare_the_control():
    assert COSTS["vendor_mediation"] > 0
    # Burden exceeds cost: most of the work is external to the estate.
    assert BURDENS["vendor_mediation"] >= COSTS["vendor_mediation"] - 1
    assert BURDENS["vendor_mediation"] > BURDENS["identity_controls"]


def test_description_names_the_control():
    assert "vendor access mediation" in describe_portfolio(
        get_portfolio("vendor_access_mediation"))
    assert "vendor" not in describe_portfolio(get_portfolio("full_defense"))


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_mediated_candidates_are_not_deduplicated_away():
    """A mediated candidate must not collapse onto its unmediated twin.

    Without vendor_mediation in the resolved-configuration key, every mediated
    candidate would hash to the same key as the unmediated candidate with the
    same postures, and deduplication would discard one of the pair at random.
    """
    cfg = default_config()
    off = distinct_portfolios_for_profile(cfg, PROFILE)
    on_cfg = dataclasses.replace(
        cfg, simulation=dataclasses.replace(
            cfg.simulation, vendor_mediation_enabled=True))
    on = distinct_portfolios_for_profile(on_cfg, PROFILE)
    assert len(on) == 2 * len(off)
    assert sum(p.vendor_mediation for p in on) == len(off)
    # Switching the dimension on must not change which unmediated
    # configurations survive deduplication.
    assert sorted(p.name for p in on if not p.vendor_mediation) == sorted(
        p.name for p in off)


# ---------------------------------------------------------------------------
# Mechanism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n,coverage,expected", [
    (3, 0.75, 2), (3, 1.0, 3), (3, 0.0, 0), (0, 0.75, 0), (8, 0.5, 4),
])
def test_brokered_count_follows_coverage(n, coverage, expected):
    assert brokered_support_path_count(n, coverage) == expected


def test_coverage_is_clamped_not_trusted():
    assert brokered_support_path_count(4, 1.5) == 4
    assert brokered_support_path_count(4, -1.0) == 0


def test_the_model_has_support_paths_to_act_on():
    """Guard the premise. If the base graph grew no vendor support paths,
    every mechanism test below would pass vacuously."""
    ids = _support_path_ids(_base_graph(default_config()))
    assert ids.size >= 1


def test_mediation_strips_the_segmentation_exemption():
    """The core mechanism.

    Under least privilege, a brokered support path into a zone the
    architecture does not permit is REMOVED. Before this control, the same
    path survived at every segmentation tier.
    """
    cfg = default_config()
    base = _base_graph(cfg)
    support = set(_support_path_ids(base).tolist())
    common = dict(patch_coverage=0.9,
                  backup_strategy=BackupStrategy.CONNECTED.value)

    unmediated = apply_controls_to_base(
        cfg, base, segmentation=SegmentationLevel.LEAST_PRIVILEGE, **common)
    mediated = apply_controls_to_base(
        cfg, base, segmentation=SegmentationLevel.LEAST_PRIVILEGE,
        vendor_mediation=True, **common)

    kept_unmediated = support & set(unmediated.edge_base_id.tolist())
    kept_mediated = support & set(mediated.edge_base_id.tolist())
    # Brokered paths are gone; the control strictly removes support paths.
    assert kept_mediated < kept_unmediated
    n_brokered = brokered_support_path_count(
        len(support), cfg.simulation.vendor_mediation_coverage)
    assert len(kept_unmediated) - len(kept_mediated) == n_brokered


def test_unbrokered_paths_keep_the_exemption():
    """Coverage below 1.0 means a residual the control cannot reach.

    This is the honest half of the mechanism and the part a reviewer should
    attack: the surviving paths are what makes this control unable to close
    its own pathway.
    """
    cfg = default_config()
    assert cfg.simulation.vendor_mediation_coverage < 1.0
    base = _base_graph(cfg)
    support = set(_support_path_ids(base).tolist())
    mediated = apply_controls_to_base(
        cfg, base, segmentation=SegmentationLevel.LEAST_PRIVILEGE,
        patch_coverage=0.9, backup_strategy=BackupStrategy.CONNECTED.value,
        vendor_mediation=True)
    survivors = support & set(mediated.edge_base_id.tolist())
    assert survivors, "with coverage < 1 some support path must remain"


def test_full_coverage_closes_every_brokered_path():
    cfg = dataclasses.replace(
        default_config(),
        simulation=dataclasses.replace(
            default_config().simulation, vendor_mediation_coverage=1.0))
    base = _base_graph(cfg)
    support = set(_support_path_ids(base).tolist())
    mediated = apply_controls_to_base(
        cfg, base, segmentation=SegmentationLevel.LEAST_PRIVILEGE,
        patch_coverage=0.9, backup_strategy=BackupStrategy.CONNECTED.value,
        vendor_mediation=True)
    assert not (support & set(mediated.edge_base_id.tolist()))


def test_surviving_brokered_paths_are_weakened():
    """Under flat segmentation every pair is permitted, so no brokered path is
    removed — which isolates the traversal mechanism from the structural one.
    """
    cfg = default_config()
    base = _base_graph(cfg)
    support = _support_path_ids(base)
    common = dict(segmentation=SegmentationLevel.FLAT, patch_coverage=0.9,
                  backup_strategy=BackupStrategy.CONNECTED.value)
    plain = apply_controls_to_base(cfg, base, **common)
    mediated = apply_controls_to_base(cfg, base, vendor_mediation=True,
                                      **common)

    def traversal_by_base_id(net):
        return dict(zip(net.edge_base_id.tolist(),
                        net.edge_traversal_mod.tolist()))

    plain_t, med_t = traversal_by_base_id(plain), traversal_by_base_id(mediated)
    factor = 1.0 - cfg.simulation.vendor_mediation_effectiveness
    n_brokered = brokered_support_path_count(
        support.size, cfg.simulation.vendor_mediation_coverage)
    weakened = [eid for eid in support.tolist()
                if eid in med_t
                and med_t[eid] == pytest.approx(plain_t[eid] * factor)]
    assert len(weakened) == n_brokered
    # Every non-support edge is untouched.
    for eid, value in plain_t.items():
        if eid not in set(support.tolist()):
            assert med_t[eid] == pytest.approx(value)


def test_mediation_leaves_nodes_and_other_edges_alone():
    cfg = default_config()
    base = _base_graph(cfg)
    common = dict(segmentation=SegmentationLevel.BASIC, patch_coverage=0.75,
                  backup_strategy=BackupStrategy.CONNECTED.value)
    plain = apply_controls_to_base(cfg, base, **common)
    mediated = apply_controls_to_base(cfg, base, vendor_mediation=True,
                                      **common)
    assert plain.n_nodes == mediated.n_nodes
    assert np.array_equal(plain.patched, mediated.patched)
    assert np.array_equal(plain.zone, mediated.zone)
    support = set(_support_path_ids(base).tolist())
    # Only support paths may be dropped.
    assert (set(plain.edge_base_id.tolist())
            - set(mediated.edge_base_id.tolist())) <= support


def test_paired_candidates_agree_on_which_paths_are_brokered():
    """The paired design's matching depends on this.

    Two candidates sharing a scenario must see the same estate. Because the
    brokered set is deterministic in base-edge order rather than drawn, any
    two mediated candidates on the same base graph broker the same paths.
    """
    cfg = default_config()
    base = _base_graph(cfg)
    a = apply_controls_to_base(
        cfg, base, segmentation=SegmentationLevel.LEAST_PRIVILEGE,
        patch_coverage=0.25, backup_strategy=BackupStrategy.CONNECTED.value,
        vendor_mediation=True)
    b = apply_controls_to_base(
        cfg, base, segmentation=SegmentationLevel.LEAST_PRIVILEGE,
        patch_coverage=0.90, backup_strategy=BackupStrategy.ISOLATED.value,
        vendor_mediation=True)
    support = set(_support_path_ids(base).tolist())
    assert (support & set(a.edge_base_id.tolist())
            == support & set(b.edge_base_id.tolist()))


def test_unpaired_generator_does_not_shift_its_random_stream():
    """Switching the control on must not move the generator's draws.

    Both the destination choice and the access weight are drawn for every
    support path whether or not it is brokered, so the only differences
    between these two graphs are the ones the control is supposed to cause.
    """
    cfg = default_config()
    kw = dict(segmentation=SegmentationLevel.FLAT, patch_coverage=0.5,
              backup_strategy=BackupStrategy.CONNECTED.value)
    plain = generate_network(cfg, "regional_hospital", PROFILE,
                             trial_rng(5, 5, stream_id=0), **kw)
    mediated = generate_network(cfg, "regional_hospital", PROFILE,
                                trial_rng(5, 5, stream_id=0),
                                vendor_mediation=True, **kw)
    assert plain.n_nodes == mediated.n_nodes
    assert np.array_equal(plain.vulnerability, mediated.vulnerability)
    assert np.array_equal(plain.patched, mediated.patched)
    assert np.array_equal(plain.privilege, mediated.privilege)
    # Under flat segmentation no brokered path is removed, so even the edge
    # set matches; only the traversal modifiers on support paths differ.
    assert plain.n_edges == mediated.n_edges
    assert np.array_equal(plain.edge_src, mediated.edge_src)
    assert np.array_equal(plain.edge_dst, mediated.edge_dst)


def test_detection_gain_acts_only_on_gateways_and_only_when_raised():
    from grrc.propagation import RansomwareSimulation
    cfg = default_config()
    net = _base_graph(cfg)
    eff = effective_settings(
        cfg.profiles[PROFILE],
        DefensePortfolio("m", segmentation=SegmentationLevel.FLAT,
                         backup_override=BackupStrategy.CONNECTED,
                         vendor_mediation=True))
    plain_eff = dataclasses.replace(eff, vendor_mediation=False)

    def detect_prob(config, settings):
        return RansomwareSimulation(
            config, net, settings, trial_rng(1, 1)).detect_prob.copy()

    # Default gain is exactly inert even for a mediated portfolio.
    assert np.array_equal(detect_prob(cfg, eff), detect_prob(cfg, plain_eff))

    raised = dataclasses.replace(
        cfg, simulation=dataclasses.replace(
            cfg.simulation, vendor_mediation_detection_gain=2.0))
    boosted = detect_prob(raised, eff)
    baseline = detect_prob(raised, plain_eff)
    gateway = np.array([t == "vendor_gateway" for t in net.node_type])
    assert np.array_equal(boosted[~gateway], baseline[~gateway])
    assert gateway.any() and np.all(boosted[gateway] >= baseline[gateway])


def test_mediation_never_increases_reachability_from_a_vendor_foothold():
    """A monotonicity property worth asserting: the control is a control.

    Over a bank of scenarios entered at a vendor connection, buying mediation
    must not raise mean weighted service hours lost. This is a property of the
    mechanism (it only removes edges and lowers traversal), not an empirical
    finding, and it would catch a sign error in either mechanism.
    """
    cfg = dataclasses.replace(
        default_config(),
        simulation=dataclasses.replace(
            default_config().simulation, vendor_mediation_enabled=True))
    metric = "weighted_service_hours_lost"

    def mean_hours(portfolio_name):
        total = 0.0
        for scenario in range(12):
            spec = TrialSpec(
                trial_id=scenario, scenario_id=scenario, paired=True,
                experiment="t", facility="regional_hospital", profile=PROFILE,
                portfolio=portfolio_name, entry_point="vendor_connection",
                master_seed=31337)
            total += run_trial(cfg, spec)[metric]
        return total / 12

    assert mean_hours("full_defense_mediated") <= mean_hours("full_defense")


def test_unpaired_generator_also_strips_the_exemption():
    """The mechanism must hold in both generator paths.

    ``apply_controls_to_base`` serves the paired confirmatory design and
    ``generate_network`` serves everything else. A control implemented in only
    one of them would silently do nothing in half the study.
    """
    cfg = default_config()
    kw = dict(patch_coverage=0.5,
              backup_strategy=BackupStrategy.CONNECTED.value)

    def support_edges(seg, vam):
        net = generate_network(
            cfg, "regional_hospital", PROFILE, trial_rng(5, 5, stream_id=0),
            segmentation=seg, vendor_mediation=vam, **kw)
        gateway = np.array(
            [t == "vendor_gateway" for t in net.node_type], dtype=bool)
        return int((gateway[net.edge_src]
                    & np.isin(net.zone[net.edge_dst],
                              [int(z) for z in VENDOR_PATHS])).sum())

    for seg in (SegmentationLevel.BASIC, SegmentationLevel.LEAST_PRIVILEGE):
        assert support_edges(seg, True) < support_edges(seg, False)


def test_no_vendor_destination_is_permitted_above_flat():
    """Records a structural consequence of the existing architecture.

    Under basic and least-privilege segmentation the architecture permits no
    path at all from the internet-facing zone into any VENDOR_PATHS zone. So a
    brokered support path is always *removed* at those tiers, and M2 (traversal
    weakening) can only ever bite under flat segmentation.

    This means vendor mediation and segmentation interact strongly rather than
    additively: above flat, the control's whole effect is structural. Any
    reported interaction between the two controls is therefore a property of
    REQUIRED_PATHS and BASIC_EXTRA_PATHS, not an empirical finding, and this
    test exists so that a later change to those sets cannot quietly invalidate
    that reading.
    """
    from grrc.network_generator import allowed_zone_pairs
    for seg in (SegmentationLevel.BASIC, SegmentationLevel.LEAST_PRIVILEGE):
        allowed = allowed_zone_pairs(seg)
        assert not any((Zone.INTERNET_FACING, zb) in allowed
                       for zb in VENDOR_PATHS)
    flat = allowed_zone_pairs(SegmentationLevel.FLAT)
    assert all((Zone.INTERNET_FACING, zb) in flat for zb in VENDOR_PATHS)

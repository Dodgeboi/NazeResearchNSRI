"""Regression tests for the endpoint registry and the sustained-outage rule.

Every test here corresponds to a defect the pre-rebuild suite did not detect.
The 70-test baseline passed both before and after the sustained-outage
endpoint was changed from k = 1 to k = 2, which is the clearest possible
demonstration that a green suite was not evidence of semantic correctness
(audit ISSUE-020). These tests assert the *manuscript's* definitions, not the
implementation's behavior, so they fail when the two drift apart.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from grrc.config import ConfigError, load_config
from grrc.endpoints import (
    ENDPOINTS,
    IDENTIFICATION_CLASSES,
    PARETO_OBJECTIVES,
    SUSTAINED_OUTAGE_K_LADDER,
    endpoint,
    max_streak_column,
    sustained_clinical_outage,
    sustained_outage_column,
    sustained_outage_ladder,
)
from grrc.enums import CLINICAL_SERVICES, Service

ROOT = Path(__file__).resolve().parents[1]

#: A trial's per-service longest outage, in steps. Only the four clinical
#: services participate in the endpoint.
EHR, LAB, PHARM, IMG = CLINICAL_SERVICES


def streaks(**overrides: int) -> dict[Service, int]:
    """Per-service max-streak map with every service healthy by default."""
    base = {s: 0 for s in Service}
    for name, value in overrides.items():
        base[Service(name)] = value
    return base


# ---------------------------------------------------------------------------
# The k-of-n rule itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("qualifying,k,expected", [
    # The exact boundary cases the handoff requires: 0, 1, 3, 4 and all.
    (0, 1, False), (0, 2, False), (0, 4, False),
    (1, 1, True),  (1, 2, False), (1, 3, False), (1, 4, False),
    (2, 1, True),  (2, 2, True),  (2, 3, False), (2, 4, False),
    (3, 1, True),  (3, 2, True),  (3, 3, True),  (3, 4, False),
    (4, 1, True),  (4, 2, True),  (4, 3, True),  (4, 4, True),
])
def test_k_of_n_fires_at_exactly_the_configured_service_count(
        qualifying, k, expected):
    """The endpoint requires *at least k* qualifying services, no more, no less.

    This is the test that would have caught audit ISSUE-001. The manuscript
    defined the endpoint at k = 4 while ``propagation.py`` used ``any()``,
    i.e. k = 1, over a four-member clinical set.
    """
    threshold = 24
    mapping = streaks(**{
        service.value: threshold + 1
        for service in CLINICAL_SERVICES[:qualifying]})
    assert sustained_clinical_outage(mapping, threshold, k) is expected


def test_threshold_comparison_is_strict():
    """A run of exactly the threshold does not qualify; one step more does.

    The manuscript says "more than two modeled hours", so ``threshold_steps``
    is the longest outage that still does *not* count.
    """
    threshold = 24
    at_threshold = streaks(ehr=threshold, laboratory=threshold)
    just_over = streaks(ehr=threshold + 1, laboratory=threshold + 1)
    assert sustained_clinical_outage(at_threshold, threshold, 2) is False
    assert sustained_clinical_outage(just_over, threshold, 2) is True


def test_non_clinical_services_never_contribute():
    """Scheduling, identity and backup outages cannot trigger the endpoint."""
    threshold = 24
    non_clinical = [s for s in Service if s not in CLINICAL_SERVICES]
    assert non_clinical, "expected non-clinical services in the model"
    mapping = streaks(**{s.value: threshold * 10 for s in non_clinical})
    assert sustained_clinical_outage(mapping, threshold, 1) is False


def test_ladder_is_monotone_non_increasing_in_k():
    """Raising k can never turn a negative trial positive."""
    threshold = 24
    mapping = streaks(ehr=100, laboratory=100, pharmacy=25, imaging=3)
    ladder = sustained_outage_ladder(mapping, threshold)
    values = [ladder[k] for k in SUSTAINED_OUTAGE_K_LADDER]
    assert values == sorted(values, reverse=True)
    # Three services exceed 24 steps, so k<=3 fires and k=4 does not.
    assert ladder == {1: True, 2: True, 3: True, 4: False}


def test_ladder_covers_every_clinical_service_count():
    assert set(sustained_outage_ladder(streaks(), 24)) == set(
        SUSTAINED_OUTAGE_K_LADDER)
    assert len(SUSTAINED_OUTAGE_K_LADDER) == len(CLINICAL_SERVICES)


@pytest.mark.parametrize("k", [0, -1, len(CLINICAL_SERVICES) + 1])
def test_out_of_range_k_is_rejected(k):
    with pytest.raises(ValueError):
        sustained_clinical_outage(streaks(), 24, k)


def test_missing_clinical_service_is_rejected_loudly():
    """A truncated streak map must raise, never silently score as healthy."""
    partial = {EHR: 100, LAB: 100}
    with pytest.raises(ValueError, match="missing clinical services"):
        sustained_clinical_outage(partial, 24, 2)


def test_zero_threshold_is_rejected():
    with pytest.raises(ValueError):
        sustained_clinical_outage(streaks(), 0, 2)


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------

def test_every_endpoint_declares_an_identification_class():
    for spec in ENDPOINTS.values():
        assert spec.identification in IDENTIFICATION_CLASSES
        assert spec.interpretation_boundary.strip(), spec.id
        assert spec.computed_from, spec.id


def test_pareto_objectives_are_exactly_the_minimized_endpoints():
    assert len(PARETO_OBJECTIVES) == 6
    for name in PARETO_OBJECTIVES:
        assert endpoint(name).direction == "minimize"
    diagnostics = [s.id for s in ENDPOINTS.values() if s.direction is None]
    assert "mean_defensive_isolation_hours_per_node" in diagnostics


def test_multiobjective_objectives_come_from_the_registry():
    """The optimizer must not keep its own private objective list."""
    from grrc.multiobjective import OBJECTIVES
    assert tuple(OBJECTIVES) == PARETO_OBJECTIVES


def test_unknown_endpoint_lookup_names_the_alternatives():
    with pytest.raises(KeyError, match="registered"):
        endpoint("catastrophic_probability")


def test_thresholded_endpoint_documents_its_rationale():
    """Any arbitrary constant must carry a written justification."""
    spec = endpoint("sustained_outage_probability")
    assert len(spec.threshold_rationale) > 200
    assert "declared modeling choice" in spec.threshold_rationale
    # It must not claim clinical standing for the threshold.
    assert "catastroph" not in spec.definition.lower()
    assert "not a clinical catastrophe threshold" in (
        spec.interpretation_boundary)


# ---------------------------------------------------------------------------
# Raw-output recomputability (audit ISSUE-002)
# ---------------------------------------------------------------------------

def test_simulation_emits_every_column_the_endpoint_needs():
    """An auditor must be able to recompute the endpoint at any k offline."""
    from grrc.models import TrialSpec
    from grrc.simulation import run_trial

    cfg = load_config(ROOT / "configs" / "multiobjective_portfolio.yaml")
    cfg.simulation.max_steps = 40  # keep the test fast
    spec = TrialSpec(
        trial_id=1, experiment="test", facility="regional_hospital",
        profile="resource_constrained",
        portfolio="seg-flat|patch+0|det0|iso0|bak-connected|idm0",
        entry_point="workstation", master_seed=7, scenario_id=7, paired=True)
    from grrc.defenses import enumerate_portfolios
    portfolio = next(p for p in enumerate_portfolios()
                     if p.name == spec.portfolio)
    row = run_trial(cfg, spec, portfolio=portfolio)

    for service in Service:
        assert max_streak_column(service) in row
    for k in SUSTAINED_OUTAGE_K_LADDER:
        assert sustained_outage_column(k) in row
    for column in endpoint("sustained_outage_probability").computed_from:
        assert column in row

    # The emitted indicators must agree with recomputing from the streaks.
    recomputed = sustained_outage_ladder(
        {s: row[max_streak_column(s)] for s in Service},
        cfg.simulation.sustained_outage_service_steps)
    for k, value in recomputed.items():
        assert row[sustained_outage_column(k)] == int(value)

    # The deprecated alias must equal the configured primary k.
    primary = cfg.simulation.sustained_outage_min_services
    assert row["catastrophic"] == row[sustained_outage_column(primary)]

    # A streak can never exceed the number of steps actually simulated.
    for service in Service:
        assert row[max_streak_column(service)] <= row["steps_simulated"]


# ---------------------------------------------------------------------------
# Config plumbing
# ---------------------------------------------------------------------------

def test_legacy_catastrophic_key_still_loads(tmp_path):
    """Archived protocols must stay loadable under the old key name."""
    config = tmp_path / "legacy.yaml"
    config.write_text(
        "mode: standard\nsimulation:\n  catastrophic_service_steps: 12\n",
        encoding="utf-8")
    cfg = load_config(config)
    assert cfg.simulation.sustained_outage_service_steps == 12


def test_setting_both_outage_keys_is_an_error(tmp_path):
    config = tmp_path / "both.yaml"
    config.write_text(
        "mode: standard\nsimulation:\n"
        "  catastrophic_service_steps: 12\n"
        "  sustained_outage_service_steps: 24\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="keep only the latter"):
        load_config(config)


@pytest.mark.parametrize("k", [0, len(CLINICAL_SERVICES) + 1])
def test_config_rejects_out_of_range_primary_k(tmp_path, k):
    config = tmp_path / "bad_k.yaml"
    config.write_text(
        f"mode: standard\nsimulation:\n  sustained_outage_min_services: {k}\n",
        encoding="utf-8")
    with pytest.raises(ConfigError, match="sustained_outage_min_services"):
        load_config(config)


def test_every_study_config_declares_the_primary_k():
    """No config may inherit the primary k silently from a library default."""
    for path in sorted((ROOT / "configs").glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if "sustained_outage_service_steps" not in text:
            continue  # config does not exercise the endpoint
        assert "sustained_outage_min_services" in text, (
            f"{path.name} sets the outage duration but not the service count; "
            "the primary k must be declared explicitly in every config that "
            "reports the endpoint")


# ---------------------------------------------------------------------------
# Manuscript agreement (the claim audit's first hook)
# ---------------------------------------------------------------------------

def test_manuscript_does_not_use_catastrophe_language_for_the_endpoint():
    """The red-line list forbids calling the threshold a clinical catastrophe."""
    tex = (ROOT / "docs" / "manuscript" / "main.tex").read_text(
        encoding="utf-8")
    banned = re.findall(r"catastroph\w*", tex, flags=re.IGNORECASE)
    assert not banned, (
        "manuscript still uses catastrophe language for a threshold that has "
        f"had no clinical validation: {sorted(set(banned))}")


def test_manuscript_states_the_primary_k_and_the_ladder():
    tex = (ROOT / "docs" / "manuscript" / "main.tex").read_text(
        encoding="utf-8")
    assert "sustained" in tex.lower()
    # The primary k must be stated as a number, and the ladder must be
    # reported so a reader can substitute their own k.
    assert re.search(r"\bk\s*=\s*2\b", tex), (
        "manuscript must state the primary k explicitly")

from pathlib import Path

import numpy as np
import pytest

from grrc.attack_graph import (build_graph, load_bundle, RANSOMWARE_STAGES,
                               IMPACT_TECHNIQUE)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"

pytestmark = pytest.mark.skipif(not BUNDLE.exists(),
                                reason="run scripts/fetch_attack.py first")


def _graph():
    return build_graph(load_bundle(BUNDLE))


def test_parses_pinned_version_and_real_structure():
    g = _graph()
    assert g.version == "17.1"
    assert g.n_techniques > 400 and g.n_mitigations == 44
    assert g.coverage.shape == (g.n_techniques, g.n_mitigations)
    assert g.coverage.dtype == bool and g.coverage.any()


def test_impact_objective_present_and_mitigated():
    g = _graph()
    assert g.techniques[g.impact_index] == IMPACT_TECHNIQUE
    # T1486 must carry at least one real mitigates edge (e.g. Data Backup).
    assert g.coverage[g.impact_index].any()


def test_every_stage_has_active_techniques():
    g = _graph()
    for stage in RANSOMWARE_STAGES:
        assert len(g.stage_members[stage]) > 0


def test_usage_weights_are_nonnegative_and_real():
    g = _graph()
    assert g.usage.shape == (g.n_techniques,)
    assert (g.usage >= 0).all() and g.usage.sum() > 0


def test_mitigation_ids_are_attack_ids():
    g = _graph()
    assert all(m.startswith("M") for m in g.mitigations)
    assert all(t.startswith("T") for t in g.techniques)

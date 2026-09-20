from pathlib import Path

import numpy as np
import pytest

from grrc.attack_graph import build_graph, load_bundle
from grrc.hospital_attack_model import (build_model, impact_reachability, service_outage,
                                        certify_clinical, certify_catastrophic, IMPACT_TECHNIQUES)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
pytestmark = pytest.mark.skipif(not BUNDLE.exists(), reason="run scripts/fetch_attack.py first")


def _model():
    return build_model(build_graph(load_bundle(BUNDLE)))


def test_model_has_four_clinical_services_and_impact_techniques():
    m = _model()
    assert len(m.services) == 4
    assert len(m.impact_members) >= 1
    present = [m.graph.techniques[i] for i in m.impact_members]
    assert set(present) <= set(IMPACT_TECHNIQUES)
    assert "T1486" in present  # ransomware encryption must be represented


def test_reachability_in_unit_interval_and_decreasing_in_controls():
    m = _model()
    n = m.graph.n_mitigations
    eff = np.full(n, 0.5)
    empty = impact_reachability(np.zeros((1, n), bool), 0.9, eff, m)[0]
    full = impact_reachability(np.ones((1, n), bool), 0.9, eff, m)[0]
    assert 0 <= full <= empty <= 1


def test_service_outage_is_reachability_times_degradation():
    m = _model()
    n = m.graph.n_mitigations
    port = np.zeros((1, n), bool)
    eff = np.full(n, 0.4)
    deg = m.degradation[:, 1]
    reach = impact_reachability(port, 0.8, eff, m)[0]
    out = service_outage(port, 0.8, eff, deg, m)[0]
    assert out == pytest.approx(reach * deg)


def test_certificate_monotone_and_union_is_sum():
    m = _model()
    n = m.graph.n_mitigations
    eff_bounds = np.tile([0.2, 0.7], (n, 1))
    ports = np.array([np.zeros(n, bool), np.ones(n, bool)])
    worst, best, guaranteed, possible = certify_clinical(
        ports, (0.5, 0.9), eff_bounds, m.degradation, m, 0.05)
    # Union column equals the per-service sum.
    assert worst[:, -1] == pytest.approx(worst[:, :-1].sum(axis=1))
    # Full portfolio's worst case does not exceed the empty portfolio's.
    assert (worst[1] <= worst[0] + 1e-12).all()
    # guaranteed implies possible.
    assert not (guaranteed & ~possible).any()
    assert bool(guaranteed[1]) and not bool(guaranteed[0])


def test_higher_degradation_never_lowers_outage():
    m = _model()
    n = m.graph.n_mitigations
    port = np.ones((1, n), bool)
    eff = np.full(n, 0.5)
    low = service_outage(port, 0.9, eff, m.degradation[:, 0], m)[0]
    high = service_outage(port, 0.9, eff, m.degradation[:, 1], m)[0]
    assert (high >= low - 1e-12).all()


def test_corner_bounds_a_random_interior_sample():
    m = _model()
    n = m.graph.n_mitigations
    eff_bounds = np.tile([0.2, 0.7], (n, 1))
    port = np.ones((1, n), bool)
    worst, best, _, _ = certify_clinical(port, (0.4, 0.9), eff_bounds, m.degradation, m, 0.5)
    rng = np.random.default_rng(0)
    for _ in range(20):
        base = rng.uniform(0.4, 0.9)
        eff = eff_bounds[:, 0] + rng.random(n) * (eff_bounds[:, 1] - eff_bounds[:, 0])
        deg = m.degradation[:, 0] + rng.random(4) * (m.degradation[:, 1] - m.degradation[:, 0])
        per = service_outage(port, base, eff, deg, m)[0]
        assert (per <= worst[0, :-1] + 1e-12).all()
        assert (per >= best[0, :-1] - 1e-12).all()


@pytest.mark.parametrize("eps", [0.0, 1.0])
def test_certify_rejects_bad_epsilon(eps):
    m = _model()
    n = m.graph.n_mitigations
    with pytest.raises(ValueError):
        certify_clinical(np.ones((1, n), bool), (0.5, 0.9),
                         np.tile([0.2, 0.7], (n, 1)), m.degradation, m, eps)


def test_catastrophic_k1_matches_clinical_union_column():
    m = _model()
    n = m.graph.n_mitigations
    eff = np.tile([0.2, 0.7], (n, 1))
    port = np.zeros((1, n), bool)
    union = certify_clinical(port, (0.5, 0.9), eff, m.degradation, m, 0.5)[0][0, -1]
    worst, _, _, _ = certify_catastrophic(port, (0.5, 0.9), eff, m.degradation, m, 1, 0.5)
    assert worst[0] == pytest.approx(min(1.0, union))


def test_catastrophic_nonincreasing_in_k_and_guaranteed_implies_possible():
    m = _model()
    n = m.graph.n_mitigations
    eff = np.tile([0.2, 0.7], (n, 1))
    port = np.zeros((1, n), bool)
    vals = []
    for k in (1, 2, 3, 4):
        worst, best, guaranteed, possible = certify_catastrophic(
            port, (0.5, 0.9), eff, m.degradation, m, k, 0.05)
        vals.append(worst[0])
        assert (best <= worst + 1e-9).all()
        assert not (guaranteed & ~possible).any()
    assert all(vals[i] >= vals[i + 1] - 1e-9 for i in range(3))


@pytest.mark.parametrize("k", [0, 5, -1])
def test_catastrophic_rejects_bad_k(k):
    m = _model()
    n = m.graph.n_mitigations
    with pytest.raises(ValueError):
        certify_catastrophic(np.ones((1, n), bool), (0.5, 0.9),
                             np.tile([0.2, 0.7], (n, 1)), m.degradation, m, k, 0.05)

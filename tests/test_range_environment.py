from pathlib import Path

import numpy as np
import pytest

from grrc.attack_graph import build_graph, load_bundle
from grrc.hospital_attack_model import build_model, certify_catastrophic
from grrc.control_certificate import certify_portfolios
from grrc.range import DefenseRange, default_regimes

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"


@pytest.fixture(scope="module")
def model():
    return build_model(build_graph(load_bundle(BUNDLE)))


@pytest.fixture(scope="module")
def env(model):
    regime = default_regimes(model)[0]
    return DefenseRange(model, regime)


def test_score_matches_direct_certificate_calls(env):
    """The range's score is exactly the underlying certificate, not a re-derivation."""
    idx = [env.graph.mitigations.index(m) for m in ("M1032", "M1030", "M1051")
           if m in env.graph.mitigations]
    port = np.zeros(env.n_mitigations, bool)
    port[idx] = True
    s = env.score(idx)
    cw, cb, cg, cp = certify_portfolios(port[None], env.regime.base_bounds, env.regime.eff_bounds,
                                        env.graph.coverage, env.graph.usage, env.stage_index,
                                        env.impact_index, env.regime.epsilon)
    kw, kb, kg, kp = certify_catastrophic(port[None], env.regime.base_bounds, env.regime.eff_bounds,
                                          env.regime.deg_bounds, env.model, env.regime.k,
                                          env.regime.epsilon)
    assert s["worst_reachability"] == pytest.approx(float(cw[0]))
    assert s["best_reachability"] == pytest.approx(float(cb[0]))
    assert s["guaranteed"] == bool(cg[0]) and s["possible"] == bool(cp[0])
    assert s["cat_worst"] == pytest.approx(float(kw[0]))
    assert s["cat_guaranteed"] == bool(kg[0]) and s["cat_possible"] == bool(kp[0])
    assert s["cost"] == len(idx)


def test_adding_a_control_never_raises_risk(env):
    """Certificate scores are monotone: adding a mitigation cannot increase risk."""
    base = env.score([])
    added = env.score([0])
    assert added["worst_reachability"] <= base["worst_reachability"] + 1e-12
    assert added["cat_worst"] <= base["cat_worst"] + 1e-12
    assert added["cost"] == 1


def test_stateful_interface_tracks_portfolio(env):
    env.reset([])
    assert env.portfolio_indices() == ()
    env.add(3)
    env.add(1)
    assert env.portfolio_indices() == (1, 3)
    env.remove(1)
    assert env.portfolio_indices() == (3,)
    obs = env.set_portfolio([2, 5])
    assert obs["portfolio"] == (2, 5)
    assert obs["score"]["cost"] == 2


def test_catalog_is_wellformed(env):
    cat = env.mitigation_catalog()
    assert len(cat) == env.n_mitigations
    row = cat[0]
    assert set(row) == {"index", "id", "name", "techniques_covered", "stages"}
    assert row["id"].startswith("M") and row["techniques_covered"] >= 0
    assert all(s in {"initial-access", "execution", "persistence", "privilege-escalation",
                     "defense-evasion", "credential-access", "discovery", "lateral-movement",
                     "collection", "command-and-control", "exfiltration"} for s in row["stages"])


def test_looser_epsilon_never_harder(model):
    """A portfolio certified at a strict epsilon certifies at a looser one (same k)."""
    regimes = {r.epsilon: r for r in default_regimes(model) if r.k == 1
               and r.degradation_source == "assumed"}
    strict = DefenseRange(model, regimes[0.01])
    loose = DefenseRange(model, regimes[0.10])
    port = [strict.graph.mitigations.index("M1032")] if "M1032" in strict.graph.mitigations else [0]
    if strict.score(port)["cat_guaranteed"]:
        assert loose.score(port)["cat_guaranteed"]


@pytest.mark.parametrize("bad", [[-1], [10_000]])
def test_out_of_range_index_rejected(env, bad):
    with pytest.raises(ValueError):
        env.score(bad)

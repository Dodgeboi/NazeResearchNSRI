from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from grrc.attack_graph import build_graph, load_bundle
from grrc.hospital_attack_model import build_model
from grrc.control_certificate import greedy_frontier, certify_portfolios
from grrc.range import DefenseRange, default_regimes
from grrc.range import policies
from grrc.range.runner import cost_to_certify, run_sweep

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"


@pytest.fixture(scope="module")
def model():
    return build_model(build_graph(load_bundle(BUNDLE)))


def _regime(model, source="assumed", eps=0.10, k=2, adversary="typical"):
    for r in default_regimes(model):
        if (r.adversary == adversary and r.degradation_source == source
                and r.epsilon == eps and r.k == k):
            return r
    raise KeyError((adversary, source, eps, k))


def test_greedy_wrapper_matches_greedy_frontier(model):
    """greedy_order is exactly greedy_frontier's order, and reproduces its curve."""
    env = DefenseRange(model, _regime(model))
    order, curve = greedy_frontier(env.regime.base_bounds, env.regime.eff_bounds,
                                   env.graph.coverage, env.graph.usage,
                                   env.stage_index, env.impact_index)
    assert policies.greedy_order(env) == list(order)
    running = np.zeros(env.n_mitigations, bool)
    recomputed = []
    for m in order:
        running = running.copy(); running[m] = True
        recomputed.append(float(certify_portfolios(running[None], env.regime.base_bounds,
                          env.regime.eff_bounds, env.graph.coverage, env.graph.usage,
                          env.stage_index, env.impact_index, 0.5)[0][0]))
    assert recomputed == pytest.approx(curve)


def test_coverage_order_is_certificate_blind_and_sorted(model):
    env = DefenseRange(model, _regime(model))
    order = policies.coverage_order(env)
    covered = env.graph.coverage.sum(axis=0)
    assert [covered[m] for m in order] == sorted(covered, reverse=True)
    assert set(order) == set(range(env.n_mitigations))


def test_random_order_is_seeded_and_reproducible(model):
    env = DefenseRange(model, _regime(model))
    assert policies.random_order(env, 7) == policies.random_order(env, 7)
    assert set(policies.random_order(env, 7)) == set(range(env.n_mitigations))


def test_optimal_small_matches_bruteforce_oracle(model):
    """Independent exhaustive oracle: optimal_small returns the true minimum size."""
    env = DefenseRange(model, _regime(model, eps=0.10, k=2))    # optimum is small here
    n = env.n_mitigations

    def certifies(combo):
        port = np.zeros(n, bool); port[list(combo)] = True
        return bool(env.catastrophic_certify(port[None])[2][0])

    true_size = None
    for size in range(0, 3):
        if any(certifies(c) for c in combinations(range(n), size)):
            true_size = size
            break
    idx, size, computed = policies.optimal_small(env, max_size=3)
    assert computed and size == true_size
    assert certifies(idx)                                        # the returned set works


def test_optimal_never_exceeds_greedy_and_greedy_beats_coverage(model):
    """Optimality ordering the benchmark reports: optimal <= greedy <= coverage."""
    for eps, k in [(0.10, 1), (0.10, 2), (0.05, 2)]:
        env = DefenseRange(model, _regime(model, eps=eps, k=k))
        g = cost_to_certify(env, policies.greedy_order(env))
        c = cost_to_certify(env, policies.coverage_order(env))
        _, opt, computed = policies.optimal_small(env, upper_bound=g)
        assert computed and opt is not None
        assert opt <= g <= c


def test_cost_to_certify_zero_when_empty_certifies(model):
    """Where the empty portfolio already certifies, cost-to-certify is 0."""
    env = DefenseRange(model, _regime(model, eps=0.10, k=4))     # easy regime
    if env.score([])["cat_guaranteed"]:
        assert cost_to_certify(env, policies.greedy_order(env)) == 0


def test_run_sweep_shapes_and_sanity(model):
    """A small sweep produces the three tables and passes the inline monotonicity gates."""
    regimes = [r for r in default_regimes(model) if r.degradation_source == "assumed"]
    out = run_sweep(model, regimes)
    assert set(out) == {"leaderboard", "optimality_gap", "regime_robustness"}
    assert len(out["leaderboard"]) == len(regimes) * 6          # six policies per regime
    assert {r["policy"] for r in out["regime_robustness"]} == {"greedy", "coverage",
                                                               "random", "optimal"}
    assert {r["adversary"] for r in out["leaderboard"]} == {"typical", "adaptive"}


def test_certificate_greedy_reproduces_greedy_frontier_under_typical(model):
    """The generic env-based greedy equals greedy_frontier for the typical adversary."""
    env = DefenseRange(model, _regime(model, adversary="typical"))
    order, _ = greedy_frontier(env.regime.base_bounds, env.regime.eff_bounds,
                               env.graph.coverage, env.graph.usage,
                               env.stage_index, env.impact_index)
    assert policies.certificate_greedy(env) == list(order)


def test_adaptive_costs_at_least_as_much_as_typical(model):
    """Defending against the adaptive adversary is never cheaper than the typical one."""
    for eps, k in [(0.10, 1), (0.10, 2), (0.05, 2)]:
        typ = DefenseRange(model, _regime(model, eps=eps, k=k, adversary="typical"))
        adv = DefenseRange(model, _regime(model, eps=eps, k=k, adversary="adaptive"))
        ct = cost_to_certify(typ, policies.greedy_order(typ))
        ca = cost_to_certify(adv, policies.greedy_order(adv))
        if ct is not None and ca is not None:
            assert ca >= ct

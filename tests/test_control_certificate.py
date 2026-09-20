import itertools

import numpy as np
import pytest

from grrc.control_certificate import reachability, certify_portfolios, greedy_frontier


# A tiny hand-built graph: techniques 0,1 in stage A; 2,3 in stage B; 4 = impact.
# Mitigation 0 covers {0,2,4}; mitigation 1 covers {1,3}.
COVERAGE = np.array([
    [1, 0],
    [0, 1],
    [1, 0],
    [0, 1],
    [1, 0],
], dtype=bool)
USAGE = np.array([3.0, 1.0, 2.0, 2.0, 5.0])
STAGES = [np.array([0, 1]), np.array([2, 3])]
IMPACT = 4
ARGS = (COVERAGE, USAGE, STAGES, IMPACT)


def _brute(portfolio, base, eff):
    """Independent, loop-based reachability oracle mirroring the model."""
    residual = []
    for t in range(COVERAGE.shape[0]):
        r = base
        for m in range(COVERAGE.shape[1]):
            if COVERAGE[t, m] and portfolio[m]:
                r *= (1 - eff[m])
        residual.append(r)
    out = 1.0
    for members in STAGES:
        w = USAGE[members] + 1.0
        out *= float(np.dot([residual[i] for i in members], w) / w.sum())
    return out * residual[IMPACT]


@pytest.mark.parametrize("port", list(itertools.product([0, 1], repeat=2)))
def test_reachability_matches_brute_force(port):
    port = np.array(port, bool)
    base, eff = 0.7, np.array([0.3, 0.6])
    got = reachability(port[None], base, eff, *ARGS)[0]
    assert got == pytest.approx(_brute(port, base, eff))


def test_corners_are_the_interval_extremes_over_a_grid():
    base_bounds = (0.4, 0.9)
    eff_bounds = np.array([[0.1, 0.7], [0.2, 0.8]])
    port = np.array([1, 1], bool)
    worst, best, _, _ = certify_portfolios(port[None], base_bounds, eff_bounds, *ARGS, 0.5)
    # Exhaustively sample the interior; corners must bound every grid point.
    grid = np.linspace(0, 1, 6)
    vals = []
    for bg in grid:
        base = base_bounds[0] + bg * (base_bounds[1] - base_bounds[0])
        for e0 in grid:
            for e1 in grid:
                eff = np.array([eff_bounds[0, 0] + e0 * (eff_bounds[0, 1] - eff_bounds[0, 0]),
                                eff_bounds[1, 0] + e1 * (eff_bounds[1, 1] - eff_bounds[1, 0])])
                vals.append(reachability(port[None], base, eff, *ARGS)[0])
    assert worst[0] >= max(vals) - 1e-12
    assert best[0] <= min(vals) + 1e-12


def test_more_controls_never_increase_worst_case():
    base_bounds = (0.5, 0.9)
    eff_bounds = np.array([[0.2, 0.6], [0.2, 0.6]])
    ports = np.array([[0, 0], [1, 0], [0, 1], [1, 1]], bool)
    worst, _, _, _ = certify_portfolios(ports, base_bounds, eff_bounds, *ARGS, 0.5)
    assert worst[0] >= worst[1] - 1e-12 and worst[0] >= worst[2] - 1e-12
    assert worst[1] >= worst[3] - 1e-12 and worst[2] >= worst[3] - 1e-12


def test_guaranteed_implies_possible_and_matches_threshold():
    base_bounds = (0.5, 0.9)
    eff_bounds = np.array([[0.3, 0.8], [0.3, 0.8]])
    ports = np.array([[0, 0], [1, 1]], bool)
    worst, best, guaranteed, possible = certify_portfolios(
        ports, base_bounds, eff_bounds, *ARGS, 0.05)
    assert np.array_equal(guaranteed, worst <= 0.05)
    assert np.array_equal(possible, best <= 0.05)
    assert not (guaranteed & ~possible).any()


def test_greedy_frontier_is_monotone_nonincreasing():
    base_bounds = (0.5, 0.9)
    eff_bounds = np.array([[0.2, 0.6], [0.2, 0.6]])
    order, curve = greedy_frontier(base_bounds, eff_bounds, *ARGS)
    assert sorted(order) == [0, 1]
    assert all(curve[i] >= curve[i + 1] - 1e-12 for i in range(len(curve) - 1))


def test_zero_uncertainty_reproduces_point_reachability():
    base_bounds = (0.7, 0.7)
    eff_bounds = np.array([[0.4, 0.4], [0.5, 0.5]])
    port = np.array([1, 1], bool)
    worst, best, _, _ = certify_portfolios(port[None], base_bounds, eff_bounds, *ARGS, 0.5)
    point = reachability(port[None], 0.7, np.array([0.4, 0.5]), *ARGS)[0]
    assert worst[0] == pytest.approx(point) == pytest.approx(best[0])


@pytest.mark.parametrize("base,eff", [
    (0.0, np.array([0.3, 0.4])),    # base out of range
    (0.7, np.array([0.3, 1.0])),    # effectiveness == 1
    (0.7, np.array([-0.1, 0.4])),   # negative effectiveness
])
def test_reachability_rejects_invalid_parameters(base, eff):
    with pytest.raises(ValueError):
        reachability(np.array([[1, 1]], bool), base, eff, *ARGS)


@pytest.mark.parametrize("eps", [0.0, 1.0, -0.2])
def test_certify_rejects_invalid_epsilon(eps):
    with pytest.raises(ValueError):
        certify_portfolios(np.array([[1, 1]], bool), (0.5, 0.9),
                           np.array([[0.2, 0.6], [0.2, 0.6]]), *ARGS, eps)


def test_certify_rejects_reversed_intervals():
    with pytest.raises(ValueError):
        certify_portfolios(np.array([[1, 1]], bool), (0.9, 0.5),
                           np.array([[0.2, 0.6], [0.2, 0.6]]), *ARGS, 0.1)

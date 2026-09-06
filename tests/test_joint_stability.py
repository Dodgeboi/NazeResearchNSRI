from itertools import product
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import linprog

from grrc.config import load_config, load_defense_costs
from grrc.defenses import enumerate_portfolios, portfolio_cost
from grrc.frontier_certificates import certify_frontier
from grrc.joint_stability import (TARIFF_KEYS, ORDERED_PAIRS, portfolio_features,
    ordered_rectangle_vertices, minimum_tariff_difference, tariff_pair_minima,
    guaranteed_with_shared_tariffs, hoeffding_lower_differences,
    sufficient_population_retention)
from grrc.multiobjective import (load_operational_burdens,
    portfolio_operational_burden, pareto_mask)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("radius", [0, .1, .25, .5, .75])
@pytest.mark.parametrize("preserve_gaps", [False, True])
def test_support_matches_independent_linear_program(radius, preserve_gaps):
    t = np.array([3, 5, 2, 3, 5, 1, 2, 4.])
    rng = np.random.default_rng(61)
    coefficients = rng.integers(-4, 5, (50, 8))
    observed = minimum_tariff_difference(coefficients, t, radius, preserve_gaps)
    constraint = np.zeros((2, 8))
    for row, (i, j) in enumerate(ORDERED_PAIRS):
        constraint[row, i], constraint[row, j] = 1, -1
    for a, value in zip(coefficients, observed):
        bound = [-(1-radius)*(t[j]-t[i]) if preserve_gaps else 0
                 for i, j in ORDERED_PAIRS]
        answer = linprog(a, A_ub=constraint, b_ub=bound,
            bounds=list(zip(t * (1-radius), t * (1+radius))), method="highs")
        assert answer.success
        assert value == pytest.approx(answer.fun, abs=1e-10)


def test_feature_prices_match_original_functions():
    cfg = load_config(ROOT/"configs/multiobjective_portfolio.yaml")
    costs = load_defense_costs(ROOT/"configs/defense_costs.yaml")
    burdens = load_operational_burdens(ROOT/"configs/defense_burdens.yaml")
    rng = np.random.default_rng(62)
    for profile in cfg.profiles.values():
        for points in [costs, burdens] + [
            dict(zip(TARIFF_KEYS, [1, 4, *rng.uniform(.1, 4, 3), 2, 5, 3])),
            dict(zip(TARIFF_KEYS, [2, 2, *rng.uniform(.1, 4, 3), 1, 1, 6])),
        ]:
            for p in enumerate_portfolios():
                value = portfolio_features(p, profile) @ [points[k] for k in TARIFF_KEYS]
                assert value == pytest.approx(portfolio_cost(p, profile, points))
                assert value == pytest.approx(portfolio_operational_burden(p, profile, points))


def test_zero_price_radius_matches_independent_endpoint_certificate():
    rng = np.random.default_rng(63)
    for _ in range(25):
        fixed = rng.integers(0, 5, (9, 6)).astype(float)
        upper = fixed.copy()
        upper[:, 2] += rng.integers(0, 5, 9)
        prices = fixed[:, None, 4:] - fixed[None, :, 4:]
        got = guaranteed_with_shared_tariffs(fixed[:, :4], upper[:, :4], prices)
        assert np.array_equal(got, certify_frontier(fixed, upper).guaranteed)


def test_shared_prices_do_not_become_independent_candidate_boxes():
    # One price multiplies both candidates. Its sign cannot reverse their order.
    features = np.zeros((2, 8)); features[:, 2] = [1, 2]
    t = dict(zip(TARIFF_KEYS, [3, 5, 2, 3, 5, 1, 2, 4]))
    prices = tariff_pair_minima(features, t, t, .75)
    observed = guaranteed_with_shared_tariffs(np.zeros((2, 1)),
                                              np.zeros((2, 1)), prices)
    assert observed.tolist() == [True, False]
    # Independent cost boxes overlap, losing the valid first guarantee.
    assert certify_frontier(np.array([[.5], [1.]]),
                            np.array([[3.5], [7.]])).guaranteed.tolist() == [False, False]


def test_guarantee_matches_small_full_corner_enumeration():
    rng = np.random.default_rng(64)
    for _ in range(8):
        features = np.zeros((3, 8))
        features[:, 0:2] = rng.integers(0, 3, (3, 2))
        t = np.array([2, 3, 2, 3, 5, 1, 2, 4])
        vertices = ordered_rectangle_vertices(t[:2] * .5, t[:2] * 1.5)
        low = rng.integers(0, 4, (3, 1)).astype(float)
        upper = low + rng.integers(0, 3, (3, 1))
        points = dict(zip(TARIFF_KEYS, t))
        got = guaranteed_with_shared_tariffs(low, upper,
            tariff_pair_minima(features, points, points, .5))
        masks = []
        for bits, cost, burden in product(product([False, True], repeat=3),
                                          vertices, vertices):
            outcome = np.where(np.array(bits)[:, None], upper, low)
            masks.append(pareto_mask(np.column_stack([
                outcome, features[:, :2] @ cost, features[:, :2] @ burden])))
        assert np.array_equal(got, np.logical_and.reduce(masks))


def test_population_screen_keeps_strict_coordinate_requirement():
    lower = np.zeros((2, 2, 3))
    prices = np.zeros((2, 2, 2))
    assert sufficient_population_retention(lower, prices).tolist() == [False, False]
    prices[1, 0] = 1
    assert sufficient_population_retention(lower, prices).tolist() == [True, False]


def test_hoeffding_family_and_nested_endpoint_difference():
    loss = np.array([[1, 3], [2, 2], [0, 4]], float)
    low = np.array([[0, 1], [0, 0], [1, 1]], float)
    high = np.ones((3, 2))
    non = low.copy()
    lower, width = hoeffding_lower_differences(loss, low, high, non,
        loss_bound=4, family_size=6, alpha=.05)
    expected = 2 * np.array([4, 1, 1]) * np.sqrt(np.log(6/.05)/6)
    np.testing.assert_allclose(width, expected)
    np.testing.assert_allclose(lower[1, 0] + width, [2, -1/3, 1/3])
    stronger, _ = hoeffding_lower_differences(loss, low, high, non,
        loss_bound=4, family_size=60, alpha=.05)
    assert (stronger < lower).all()
    with pytest.raises(ValueError):
        hoeffding_lower_differences(loss, high, low, non,
            loss_bound=4, family_size=6, alpha=.05)


def test_invalid_price_regions_rejected():
    with pytest.raises(ValueError):
        ordered_rectangle_vertices([3, 0], [4, 2])
    with pytest.raises(ValueError):
        minimum_tariff_difference(np.ones(8), np.ones(8), 1)
    with pytest.raises(ValueError):
        minimum_tariff_difference(np.ones(8), [4, 1, 1, 1, 1, 1, 1, 1], .5)

import numpy as np
import pytest

from grrc.betting import (LAMBDA_GRID, betting_lower_bound, betting_margins,
                          _mixture_log_capital, _lower_matrix)


def _explicit_log_capital(y, m, grid):
    """Reference grid-mixture log capital from a plain loop over fractions and steps."""
    products = []
    for lam in grid:
        total = 0.0
        for value in y:
            total += np.log1p(lam * (value - m))
        products.append(total)
    return np.log(np.mean(np.exp(products)))


def test_mixture_log_capital_matches_explicit_loop():
    rng = np.random.default_rng(11)
    y = rng.uniform(0, 1, 20)
    for m in (0.2, 0.5, 0.8):
        assert _mixture_log_capital(y, m, LAMBDA_GRID) == pytest.approx(
            _explicit_log_capital(y, m, LAMBDA_GRID))


def test_lower_bound_sits_at_the_capital_threshold():
    rng = np.random.default_rng(3)
    d = np.clip(rng.uniform(-2, 2, 250) + 0.8, -2, 2)  # positive mean -> interior solution
    bound, alpha = 2.0, 0.05
    lo = betting_lower_bound(d, observation_bound=bound, alpha=alpha)
    y = (d + bound) / (2 * bound)
    scaled = (lo + bound) / (2 * bound)
    # The bound is the mean m at which the mixture capital crosses 1 / alpha.
    assert _mixture_log_capital(y, scaled, LAMBDA_GRID) == pytest.approx(np.log(1 / alpha), abs=1e-6)


def test_vectorized_matrix_matches_scalar_bound():
    rng = np.random.default_rng(5)
    a, b = rng.uniform(0, 5, (60, 3)), rng.uniform(0, 5, (60, 3))
    matrix = _lower_matrix(a, b, 5.0, 0.01, LAMBDA_GRID)
    for i in range(3):
        for j in range(3):
            scalar = betting_lower_bound(a[:, i] - b[:, j], observation_bound=5.0, alpha=0.01)
            assert matrix[i, j] == pytest.approx(scalar, abs=1e-9)


def test_bound_below_mean_and_tighter_at_larger_alpha():
    rng = np.random.default_rng(9)
    d = rng.uniform(-1, 1, 300)
    loose = betting_lower_bound(d, observation_bound=1.0, alpha=0.10)
    strict = betting_lower_bound(d, observation_bound=1.0, alpha=0.01)
    assert loose <= d.mean() + 1e-9
    assert loose >= strict - 1e-12


def test_constant_difference_is_handled_and_valid():
    d = np.full(50, 0.4)
    lo = betting_lower_bound(d, observation_bound=1.0, alpha=0.05)
    assert -1.0 <= lo <= 0.4 + 1e-9


@pytest.mark.parametrize("seed", range(4))
def test_one_sided_coverage_valid_for_identical_data(seed):
    """Empirical non-coverage of the lower bound must not exceed alpha."""
    alpha, reps, n, mu = 0.1, 1000, 120, 0.65
    rng = np.random.default_rng(100 + seed)
    misses = sum((2 * mu - 1) < betting_lower_bound(2 * rng.binomial(1, mu, n) - 1,
                                                     observation_bound=1.0, alpha=alpha)
                 for _ in range(reps))
    assert misses / reps <= alpha + 0.03


@pytest.mark.parametrize("seed", range(3))
def test_one_sided_coverage_valid_for_non_identical_data(seed):
    """The e-value guarantee holds for independent, non-identically distributed data."""
    alpha, reps, n = 0.1, 1000, 40
    means = np.array([0.2, 0.4, 0.6, 0.8, 0.9])
    average = means.mean()
    rng = np.random.default_rng(200 + seed)
    misses = 0
    for _ in range(reps):
        x = np.concatenate([rng.binomial(1, m, n).astype(float) for m in means])
        if (2 * average - 1) < betting_lower_bound(2 * x - 1, observation_bound=1.0, alpha=alpha):
            misses += 1
    assert misses / reps <= alpha + 0.03


def test_shift_invariance_of_the_margin():
    rng = np.random.default_rng(21)
    a, b = rng.uniform(0, 6, (24, 3)), rng.uniform(0, 6, (24, 3))
    _, m1 = betting_margins(a, b, observation_bound=8.0, family_size=6)
    _, m2 = betting_margins(a + 1, b + 1, observation_bound=8.0, family_size=6)
    assert m1 == pytest.approx(m2, abs=1e-9)


def test_margin_is_deterministic():
    rng = np.random.default_rng(2)
    a, b = rng.uniform(0, 4, (30, 4)), rng.uniform(0, 4, (30, 4))
    _, first = betting_margins(a, b, observation_bound=4.0, family_size=12)
    _, second = betting_margins(a, b, observation_bound=4.0, family_size=12)
    assert np.array_equal(first, second)


def test_full_margin_row_matches_scalar_bounds():
    """A whole rival row of the margin matrix matches the scalar bound per contrast."""
    rng = np.random.default_rng(31)
    a, b = rng.uniform(0, 5, (30, 40)), rng.uniform(0, 5, (30, 40))
    _, margin = betting_margins(a, b, observation_bound=5.0, family_size=100)
    columns = np.array([betting_lower_bound(a[:, 7] - b[:, j], observation_bound=5.0,
                                            alpha=0.05 / 100) for j in range(40)])
    expected = (a[:, 7].mean() - b.mean(0)) - columns
    assert margin[7] == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("bound,family,alpha", [(0, 1, .05), (1, 0, .05), (1, 1, 0),
                                                (1, 1, 1), (np.inf, 1, .05)])
def test_invalid_bound_or_error_allocation_rejected(bound, family, alpha):
    with pytest.raises(ValueError):
        betting_margins(np.zeros((8, 2)), np.zeros((8, 2)),
                        observation_bound=bound, family_size=family, alpha=alpha)


def test_out_of_range_observations_rejected():
    with pytest.raises(ValueError):
        betting_margins(np.full((8, 2), 2.0), np.zeros((8, 2)), observation_bound=1, family_size=6)


def test_invalid_betting_grid_rejected():
    for grid in ([1.0, 0.5], [0.0, 0.3], []):
        with pytest.raises(ValueError):
            betting_margins(np.zeros((8, 2)), np.zeros((8, 2)), observation_bound=1,
                            family_size=6, grid=grid)


@pytest.mark.parametrize("kwargs", [dict(observation_bound=0, alpha=.05),
                                    dict(observation_bound=1, alpha=0),
                                    dict(observation_bound=1, alpha=1)])
def test_scalar_bound_rejects_invalid_arguments(kwargs):
    with pytest.raises(ValueError):
        betting_lower_bound(np.zeros(5), **kwargs)


def test_scalar_bound_rejects_difference_outside_bound():
    with pytest.raises(ValueError):
        betting_lower_bound(np.array([0.0, 5.0]), observation_bound=1.0, alpha=0.05)

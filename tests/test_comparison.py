import numpy as np
import pytest
from scipy.stats import t

from grrc.comparison import paired_moments, comparison_margins, conditional_indices


def test_moments_and_stratified_t_against_explicit_paired_vectors():
    rng = np.random.default_rng(471)
    a, b = rng.uniform(0, 5, (17, 4)), rng.uniform(0, 5, (17, 4))
    groups = [np.arange(5), np.arange(5, 17)]
    mean, margins = comparison_margins(a, b, groups, observation_bound=5, family_size=36)
    _, variance = paired_moments(a, b)
    for i in range(4):
        for j in range(4):
            d = a[:, i] - b[:, j]
            assert mean[i, j] == pytest.approx(d.mean())
            assert variance[i, j] == pytest.approx(d.var(ddof=1))
            pieces = [(len(g)/17)**2 * d[g].var(ddof=1) / len(g) for g in groups]
            v = sum(pieces)
            df = v*v / sum(p*p / (len(g)-1) for p, g in zip(pieces, groups))
            assert margins["paired_t_approx"][i, j] == pytest.approx(t.isf(.05/36, df)*np.sqrt(v))
            logterm = np.log(72/.05)
            expected = np.sqrt(2*d.var(ddof=1)*logterm/17) + 70*logterm/48
            assert margins["empirical_bernstein"][i, j] == pytest.approx(expected)


def test_pairing_reduces_variance_without_erasing_range_penalty():
    a = np.arange(20.)[:, None]
    a = np.column_stack([a, a+1])
    mean, margins = comparison_margins(a, a, [np.arange(20)], observation_bound=20, family_size=6)
    assert mean[1, 0] == 1
    assert margins["empirical_bernstein"][1, 0] > 0
    assert margins["paired_t_approx"][1, 0] == margins["hoeffding"][1, 0]


def test_nonidentical_strata_variance_is_not_pooled_t_variance():
    a = np.array([[0], [1], [0], [1], [8], [9], [8], [9.]])
    b = np.zeros_like(a)
    _, margins = comparison_margins(a, b, [np.arange(4), np.arange(4, 8)],
                                    observation_bound=9, family_size=1)
    expected = t.isf(.05, 6)*np.sqrt(1/24)
    assert margins["paired_t_approx"][0, 0] == pytest.approx(expected)


@pytest.mark.parametrize("groups", [[np.arange(7)], [np.arange(4), np.arange(3, 8)],
                                     [np.array([0]), np.arange(1, 8)]])
def test_bad_strata_rejected(groups):
    with pytest.raises(ValueError, match="strata"):
        comparison_margins(np.zeros((8, 2)), np.zeros((8, 2)), groups,
                           observation_bound=1, family_size=6)


def test_conditional_selection_preserves_each_entry_and_ties():
    p = np.array([4, 1, 3, 2, 0, 5, 10, 10, 10, 10, 10, 10.])
    groups = [np.arange(6), np.arange(6, 12)]
    assert conditional_indices(p, groups).tolist() == [4, 1, 6, 7]
    assert conditional_indices(p, groups, high=True).tolist() == [0, 5, 10, 11]


@pytest.mark.parametrize("bound,family,alpha", [(0, 1, .05), (1, 0, .05), (1, 1, 0),
                                                (1, 1, 1), (np.inf, 1, .05)])
def test_invalid_bound_or_error_allocation_rejected(bound, family, alpha):
    with pytest.raises(ValueError):
        comparison_margins(np.zeros((8, 2)), np.zeros((8, 2)), [np.arange(8)],
                           observation_bound=bound, family_size=family, alpha=alpha)

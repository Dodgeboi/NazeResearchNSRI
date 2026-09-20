import itertools

import numpy as np
import pytest
from scipy.optimize import linprog

from grrc.joint_bounds import sharp_k_of_n_upper, brute_force_k_of_n_upper


def _achieving_joint(p, k):
    """Re-solve for the optimal joint and return (value, achieved P(>=k), marginals)."""
    n = len(p)
    atoms = list(itertools.product([0, 1], repeat=n))
    obj = np.array([-1.0 if sum(a) >= k else 0.0 for a in atoms])
    a_eq = [[1.0] * len(atoms)] + [[float(a[i]) for a in atoms] for i in range(n)]
    res = linprog(obj, A_eq=a_eq, b_eq=[1.0] + list(p), bounds=[(0, 1)] * len(atoms), method="highs")
    x = res.x
    pk = sum(x[i] for i, a in enumerate(atoms) if sum(a) >= k)
    marg = [sum(x[i] for i, a in enumerate(atoms) if a[j]) for j in range(n)]
    return -res.fun, pk, marg, x


def test_reduces_to_union_bound_at_k1():
    for p in ([0.3, 0.25, 0.2, 0.15], [0.4, 0.4, 0.4], [0.6, 0.7]):
        assert sharp_k_of_n_upper(p, 1) == pytest.approx(min(1.0, sum(p)))


def test_equals_min_marginal_at_k_equals_n():
    for p in ([0.3, 0.25, 0.2, 0.15], [0.4, 0.5, 0.9], [0.6, 0.7]):
        assert sharp_k_of_n_upper(p, len(p)) == pytest.approx(min(p))


def test_bound_is_attained_by_a_valid_joint():
    """Sharpness: the LP optimum is realised by a genuine distribution."""
    p = [0.3, 0.25, 0.2, 0.15]
    for k in (1, 2, 3, 4):
        value, achieved, marg, x = _achieving_joint(p, k)
        assert (x >= -1e-9).all() and x.sum() == pytest.approx(1.0)
        assert marg == pytest.approx(p, abs=1e-9)          # reproduces marginals
        assert achieved == pytest.approx(value, abs=1e-9)  # attains the bound
        assert sharp_k_of_n_upper(p, k) == pytest.approx(value, abs=1e-9)


def test_never_exceeds_markov_and_union():
    p = [0.3, 0.25, 0.2, 0.15]
    for k in (1, 2, 3, 4):
        v = sharp_k_of_n_upper(p, k)
        assert v <= min(1.0, sum(p) / k) + 1e-9          # Markov
        assert v <= min(1.0, sum(p)) + 1e-9              # union (k=1) dominates all


def test_strictly_tighter_than_union_for_k_ge_2():
    p = [0.3, 0.25, 0.2, 0.15]
    assert sharp_k_of_n_upper(p, 2) < min(1.0, sum(p)) - 1e-6


def test_monotone_nondecreasing_in_each_marginal():
    base = [0.3, 0.25, 0.2, 0.15]
    for j in range(4):
        raised = list(base); raised[j] = min(1.0, base[j] + 0.2)
        for k in (1, 2, 3, 4):
            assert sharp_k_of_n_upper(raised, k) >= sharp_k_of_n_upper(base, k) - 1e-9


def test_nonincreasing_in_k():
    p = [0.5, 0.4, 0.3, 0.2]
    vals = [sharp_k_of_n_upper(p, k) for k in (1, 2, 3, 4)]
    assert all(vals[i] >= vals[i + 1] - 1e-9 for i in range(3))


def test_two_solvers_agree():
    p = [0.35, 0.3, 0.22, 0.18]
    for k in (1, 2, 3, 4):
        assert sharp_k_of_n_upper(p, k) == pytest.approx(brute_force_k_of_n_upper(p, k), abs=1e-7)


@pytest.mark.parametrize("k", [0, 5, -1])
def test_bad_k_rejected(k):
    with pytest.raises(ValueError):
        sharp_k_of_n_upper([0.2, 0.3, 0.4, 0.5], k)


@pytest.mark.parametrize("p", [[1.2, 0.3], [-0.1, 0.4], [np.inf, 0.2], []])
def test_bad_marginals_rejected(p):
    with pytest.raises(ValueError):
        sharp_k_of_n_upper(p, 1)

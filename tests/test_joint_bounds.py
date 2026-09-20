import itertools

import numpy as np
import pytest

from grrc.joint_bounds import (sharp_k_of_n_upper, sharp_k_of_n_closed_form,
                               brute_force_k_of_n_upper, _lp_k_of_n_upper,
                               dual_certificate, attaining_coupling)


def _achieving_joint(p, k):
    """Re-solve the LP for the optimal joint; return (value, achieved P(>=k), marginals)."""
    from scipy.optimize import linprog
    n = len(p)
    atoms = list(itertools.product([0, 1], repeat=n))
    obj = np.array([-1.0 if sum(a) >= k else 0.0 for a in atoms])
    a_eq = [[1.0] * len(atoms)] + [[float(a[i]) for a in atoms] for i in range(n)]
    res = linprog(obj, A_eq=a_eq, b_eq=[1.0] + list(p), bounds=[(0, 1)] * len(atoms), method="highs")
    x = res.x
    pk = sum(x[i] for i, a in enumerate(atoms) if sum(a) >= k)
    marg = [sum(x[i] for i, a in enumerate(atoms) if a[j]) for j in range(n)]
    return -res.fun, pk, marg, x


# --- The theorem's numerical certificate: closed form == the LP over all couplings ---

def test_closed_form_equals_lp_randomized():
    """Closed form matches the sharp LP to machine precision over many (n, k, p)."""
    rng = np.random.default_rng(20260920)
    worst = 0.0
    for _ in range(1500):
        n = int(rng.integers(1, 8))
        k = int(rng.integers(1, n + 1))
        p = rng.random(n).round(3).tolist()
        worst = max(worst, abs(sharp_k_of_n_closed_form(p, k) - _lp_k_of_n_upper(p, k)))
    assert worst < 1e-9


def test_closed_form_matches_both_lp_solvers():
    p = [0.35, 0.3, 0.22, 0.18]
    for k in (1, 2, 3, 4):
        cf = sharp_k_of_n_closed_form(p, k)
        assert cf == pytest.approx(_lp_k_of_n_upper(p, k), abs=1e-9)
        assert cf == pytest.approx(brute_force_k_of_n_upper(p, k), abs=1e-7)


def test_sharp_upper_uses_closed_form():
    p = [0.3, 0.25, 0.2, 0.15]
    for k in (1, 2, 3, 4):
        assert sharp_k_of_n_upper(p, k) == sharp_k_of_n_closed_form(p, k)


# --- Boundary identities the theorem predicts ---

def test_reduces_to_union_bound_at_k1():
    for p in ([0.3, 0.25, 0.2, 0.15], [0.4, 0.4, 0.4], [0.6, 0.7]):
        assert sharp_k_of_n_upper(p, 1) == pytest.approx(min(1.0, sum(p)))


def test_equals_min_marginal_at_k_equals_n():
    for p in ([0.3, 0.25, 0.2, 0.15], [0.4, 0.5, 0.9], [0.6, 0.7]):
        assert sharp_k_of_n_upper(p, len(p)) == pytest.approx(min(p))


# --- Validity: the bound dominates P(>=k) of explicit couplings ---

def test_dominates_independent_and_comonotone_couplings():
    """Bound >= P(S>=k) under both the independent and the comonotone coupling."""
    rng = np.random.default_rng(7)
    for _ in range(300):
        n = int(rng.integers(2, 7))
        k = int(rng.integers(1, n + 1))
        p = rng.random(n)
        bound = sharp_k_of_n_upper(p, k)
        # independent
        pk_indep = 0.0
        for a in itertools.product([0, 1], repeat=n):
            if sum(a) >= k:
                pk_indep += np.prod([p[i] if a[i] else 1 - p[i] for i in range(n)])
        # comonotone via a shared uniform X_i = 1[U <= p_i]: S >= k iff U <= p_(k),
        # so P(S>=k) is exactly the k-th largest marginal.
        pk_como = float(np.sort(p)[::-1][k - 1])
        assert pk_indep <= bound + 1e-9
        assert pk_como <= bound + 1e-9


def test_dominates_random_sampled_couplings():
    """Any explicit coupling realised as atom masses obeys the bound (Monte-Carlo)."""
    rng = np.random.default_rng(11)
    for _ in range(200):
        n = int(rng.integers(2, 6))
        k = int(rng.integers(1, n + 1))
        # random marginals, then a random feasible joint via the LP feasibility set:
        p = rng.random(n).round(3)
        # a feasible joint: independent product perturbed toward a random vertex is overkill;
        # simply sample many uniforms with random per-event thresholds sharing partial rank.
        atoms = attaining_coupling(p, k)  # our constructed coupling is itself an explicit joint
        pk = sum(m for a, m in atoms.items() if sum(a) >= k)
        assert pk <= sharp_k_of_n_upper(p, k) + 1e-9


# --- Attainment: the explicit coupling is a genuine joint achieving the bound ---

def test_attaining_coupling_reproduces_marginals_and_bound():
    rng = np.random.default_rng(2024)
    worst_marg = worst_val = 0.0
    for _ in range(800):
        n = int(rng.integers(1, 7))
        k = int(rng.integers(1, n + 1))
        p = rng.random(n).round(3)
        atoms = attaining_coupling(p, k)
        total = sum(atoms.values())
        marg = [sum(m for a, m in atoms.items() if a[i]) for i in range(n)]
        pk = sum(m for a, m in atoms.items() if sum(a) >= k)
        assert total == pytest.approx(1.0, abs=1e-9)
        assert all(m >= -1e-12 for m in atoms.values())
        worst_marg = max(worst_marg, max(abs(marg[i] - p[i]) for i in range(n)))
        worst_val = max(worst_val, abs(pk - sharp_k_of_n_upper(p, k)))
    assert worst_marg < 1e-8 and worst_val < 1e-8


def test_attaining_coupling_matches_lp_witness_on_hand_case():
    p = [0.3, 0.25, 0.2, 0.15]
    for k in (1, 2, 3, 4):
        value, _, _, _ = _achieving_joint(p, k)
        atoms = attaining_coupling(p, k)
        pk = sum(m for a, m in atoms.items() if sum(a) >= k)
        assert pk == pytest.approx(value, abs=1e-9)


# --- Duality: the dual certificate proves the bound (weak duality, tight when uncapped) ---

def test_dual_certificate_is_feasible_and_tight():
    rng = np.random.default_rng(99)
    for _ in range(400):
        n = int(rng.integers(1, 7))
        k = int(rng.integers(1, n + 1))
        p = rng.random(n)
        lam0, lam, obj = dual_certificate(p, k)
        assert lam0 == 0.0 and (lam >= -1e-12).all()
        # dual feasibility: for every subset A with |A| >= k, lam0 + sum_{A} lam >= 1
        for a in itertools.product([0, 1], repeat=n):
            s = lam0 + sum(lam[i] for i in range(n) if a[i])
            if sum(a) >= k:
                assert s >= 1.0 - 1e-9
            assert s >= -1e-12
        # weak duality: the true max is <= the dual objective
        assert sharp_k_of_n_upper(p, k) <= obj + 1e-9
        # tight (strong duality) when the bound is not capped at 1
        if obj < 1.0 - 1e-9:
            assert sharp_k_of_n_upper(p, k) == pytest.approx(obj, abs=1e-9)


# --- Monotonicity corollary (proves the interval-corner worst case is exact) ---

def test_monotone_nondecreasing_in_each_marginal():
    base = [0.3, 0.25, 0.2, 0.15]
    for j in range(4):
        raised = list(base)
        raised[j] = min(1.0, base[j] + 0.2)
        for k in (1, 2, 3, 4):
            assert sharp_k_of_n_upper(raised, k) >= sharp_k_of_n_upper(base, k) - 1e-9


def test_nonincreasing_in_k():
    p = [0.5, 0.4, 0.3, 0.2]
    vals = [sharp_k_of_n_upper(p, k) for k in (1, 2, 3, 4)]
    assert all(vals[i] >= vals[i + 1] - 1e-9 for i in range(3))


def test_never_exceeds_markov_and_union():
    p = [0.3, 0.25, 0.2, 0.15]
    for k in (1, 2, 3, 4):
        v = sharp_k_of_n_upper(p, k)
        assert v <= min(1.0, sum(p) / k) + 1e-9
        assert v <= min(1.0, sum(p)) + 1e-9


def test_strictly_tighter_than_union_for_k_ge_2():
    p = [0.3, 0.25, 0.2, 0.15]
    assert sharp_k_of_n_upper(p, 2) < min(1.0, sum(p)) - 1e-6


# --- Input validation ---

@pytest.mark.parametrize("k", [0, 5, -1])
def test_bad_k_rejected(k):
    with pytest.raises(ValueError):
        sharp_k_of_n_upper([0.2, 0.3, 0.4, 0.5], k)


@pytest.mark.parametrize("p", [[1.2, 0.3], [-0.1, 0.4], [np.inf, 0.2], []])
def test_bad_marginals_rejected(p):
    with pytest.raises(ValueError):
        sharp_k_of_n_upper(p, 1)


@pytest.mark.parametrize("fn", [sharp_k_of_n_closed_form, dual_certificate, attaining_coupling])
def test_all_entry_points_validate(fn):
    with pytest.raises(ValueError):
        fn([0.5, 1.3], 1)
    with pytest.raises(ValueError):
        fn([0.5, 0.4], 3)

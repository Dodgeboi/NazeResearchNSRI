"""Sharp distribution-free bounds on k-of-n event aggregation, in closed form.

Given only the marginal probabilities ``p_1, ..., p_n`` of ``n`` events (here:
each clinical service suffering a sustained outage), what is the largest possible
probability that **at least k** of them occur simultaneously, over every joint
distribution consistent with those marginals?

The catastrophic certificate used to answer this with a linear program over the
``2**n`` outcome atoms. This module proves and implements the **closed form**
(see ``study/KOFN_THEOREM.md``): with order statistics ``p_(1) >= ... >= p_(n)``,

    max_couplings P(sum_i X_i >= k)
        = min( 1, min_{0 <= j <= k-1} (1/(k-j)) * sum_{i=j+1}^{n} p_(i) ),

and the maximum is attained. The inner minimand at index ``j`` sums the ``n-j``
*smallest* marginals. This is an ``O(n log n)`` sort-and-prefix-sum computation
(:func:`sharp_k_of_n_closed_form`), solver-free and exact; the LP
(:func:`_lp_k_of_n_upper`) is retained only as an independent verification oracle
for the tests. The bound reduces to ``min(1, sum p_i)`` at ``k=1`` (the union
bound) and to ``min_i p_i`` at ``k=n``, is monotone non-decreasing in each
marginal (so it composes with the interval-corner certificate), and is tighter
than the union/Markov bound for ``k >= 2``.

The result is of classical Frechet/Boole / Ruschendorf ("m-of-n" reliability)
lineage; the theorem note states, proves (validity by an elementary pointwise
domination, attainment by an explicit coupling and an LP-dual certificate), and
machine-verifies it. Pure functions, no I/O.
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy.optimize import linprog


def _check(marginals, k):
    p = np.asarray(marginals, float)
    n = len(p)
    if n == 0 or (p < 0).any() or (p > 1).any() or not np.isfinite(p).all():
        raise ValueError("marginals must be n>=1 probabilities in [0, 1]")
    if not isinstance(k, (int, np.integer)) or not 1 <= k <= n:
        raise ValueError("k must be an integer in [1, n]")
    return p, n


def sharp_k_of_n_closed_form(marginals, k: int) -> float:
    """Closed-form sharp upper bound on P(at least k of n events); ``O(n log n)``.

    Implements the theorem: ``min(1, min_{0<=j<=k-1} (1/(k-j)) * S_j)`` where
    ``S_j`` is the sum of the ``n-j`` smallest marginals. Equal to the linear
    program of :func:`_lp_k_of_n_upper` to machine precision, but solver-free.
    """
    p, n = _check(marginals, k)
    desc = np.sort(p)[::-1]                       # p_(1) >= ... >= p_(n)
    suffix = np.concatenate([np.cumsum(desc[::-1])[::-1], [0.0]])  # suffix[j] = sum_{i>j}
    best = min(suffix[j] / (k - j) for j in range(0, k))
    return float(min(1.0, best))


def sharp_k_of_n_upper(marginals, k: int) -> float:
    """Sharp upper bound on P(at least k of n events) given only the marginals.

    ``marginals`` are ``n`` probabilities in [0, 1]; ``1 <= k <= n``. Returns the
    maximum of P(#events >= k) over all joint distributions with those marginals.
    This is the theorem's closed form (:func:`sharp_k_of_n_closed_form`); the LP
    is kept as a test-only oracle.
    """
    return sharp_k_of_n_closed_form(marginals, k)


def _minimizing_index(desc, k: int) -> int:
    """Largest ``j`` in ``[0, k-1]`` minimizing ``(1/(k-j)) * sum_{i>j} p_(i)``.

    ``desc`` are the marginals sorted descending. The largest minimizer ``j*``
    satisfies ``p_(j*) >= M >= p_(j*+1)`` (proved in the theorem note), which is
    what makes the explicit coupling below well defined.
    """
    n = len(desc)
    suffix = np.concatenate([np.cumsum(desc[::-1])[::-1], [0.0]])
    vals = [suffix[j] / (k - j) for j in range(0, k)]
    best = min(vals)
    jstar = max(j for j in range(0, k) if abs(vals[j] - best) <= 1e-15)
    return jstar, float(best)


def dual_certificate(marginals, k: int):
    """LP-dual certificate proving the closed form is an upper bound (weak duality).

    Returns ``(lambda0, lambda_vec, objective)`` where ``lambda_vec`` is aligned to
    the *input* order. The dual of the sharp-bound LP minimizes
    ``lambda0 + sum_i lambda_i p_i`` subject to ``lambda0 + sum_{i in A} lambda_i
    >= 1`` for every subset ``A`` with ``|A| >= k`` (and ``>= 0`` otherwise). The
    certificate puts ``lambda0 = 0`` and ``lambda_i = 1/(k-j*)`` on the ``n-j*``
    smallest marginals (0 on the ``j*`` largest); its objective equals the
    uncapped closed form ``M_raw``, so weak duality gives ``max P(S>=k) <= M_raw``.
    The reported ``objective`` is ``min(1, M_raw)`` (the trivial ``lambda0=1`` dual
    supplies the cap).
    """
    p, n = _check(marginals, k)
    order = np.argsort(-p, kind="stable")          # indices, largest marginal first
    desc = p[order]
    jstar, raw = _minimizing_index(desc, k)
    weight = 1.0 / (k - jstar)
    lam = np.zeros(n)
    for rank, idx in enumerate(order):
        if rank >= jstar:                          # the n-j* smallest marginals
            lam[idx] = weight
    return 0.0, lam, float(min(1.0, raw))


def attaining_coupling(marginals, k: int):
    """An explicit joint distribution attaining the sharp bound.

    Returns ``{outcome_tuple: mass}`` with keys in the *input* coordinate order,
    masses summing to one, reproducing the marginals, and achieving
    ``P(sum X_i >= k) = sharp_k_of_n_upper(marginals, k)``. Construction (proved in
    the theorem note): sort descending and split at the minimizer ``j*``; spread
    the ``n-j*`` smallest marginals as arcs around a circle of circumference
    ``M`` (the uncapped bound) so their depth is exactly ``k-j*`` on ``[0, M)``,
    while the ``j*`` largest cover ``[0, M)`` fully (each has marginal ``>= M``);
    off ``[0, M)`` fewer than ``k`` events fire. When the uncapped bound is ``>=
    1`` the same arcs laid around the unit circle give depth ``>= k`` everywhere,
    so ``P(S>=k) = 1``.
    """
    p, n = _check(marginals, k)
    order = np.argsort(-p, kind="stable")
    desc = p[order]
    jstar, raw = _minimizing_index(desc, k)
    capped = raw >= 1.0 - 1e-15

    circ = 1.0 if capped else raw                  # circle circumference
    top = [] if capped else list(range(0, jstar))  # events that cover [0, circ) fully
    spread = list(range(0, n)) if capped else list(range(jstar, n))

    breaks = {0.0, circ, 1.0}
    arcs = []                                      # (rank_in_desc, [(a, b), ...]) segments

    def lay(items, lengths, lo, hi):
        """Lay each item's arc consecutively in [lo, hi), wrapping within it."""
        span = hi - lo
        pos = lo
        for si, length in zip(items, lengths):
            a, b = pos, pos + length
            segs = []
            while b > hi + 1e-15:
                segs.append((a, hi))
                b -= span
                a = lo
            segs.append((a, b))
            arcs.append((si, segs))
            for x, y in segs:
                breaks.add(x)
                breaks.add(y)
            pos = lo + (((pos - lo) + length) % span if span > 1e-15 else 0.0)
            if pos > hi - 1e-15:
                pos = lo

    lay(spread, [desc[si] for si in spread], 0.0, circ)
    if top and 1.0 - circ > 1e-15:                 # top events' extra mass in [circ, 1)
        lay(top, [desc[si] - circ for si in top], circ, 1.0)

    bp = sorted(x for x in breaks if -1e-12 <= x <= 1.0 + 1e-12)
    atoms: dict[tuple, float] = {}
    for a, b in zip(bp[:-1], bp[1:]):
        if b - a < 1e-13:
            continue
        mid = 0.5 * (a + b)
        vec = [0] * n
        if not capped:                             # top events cover [0, circ) fully
            for si in top:
                if mid < circ:
                    vec[order[si]] = 1
        for si, segs in arcs:
            for x, y in segs:
                if x - 1e-12 <= mid <= y + 1e-12:
                    vec[order[si]] = 1
        key = tuple(vec)
        atoms[key] = atoms.get(key, 0.0) + (b - a)
    return atoms


def _lp_k_of_n_upper(marginals, k: int) -> float:
    """LP over the 2**n outcome atoms -- the independent oracle for the closed form.

    Retained solely to verify :func:`sharp_k_of_n_closed_form` in the tests; not on
    the hot path. Maximizes the mass of atoms with popcount ``>= k`` subject to the
    total-mass and per-event-marginal equalities.
    """
    p, n = _check(marginals, k)
    atoms = list(itertools.product([0, 1], repeat=n))          # 2**n outcomes
    objective = np.array([-1.0 if sum(a) >= k else 0.0 for a in atoms])
    a_eq = [[1.0] * len(atoms)] + [[float(a[i]) for a in atoms] for i in range(n)]
    b_eq = [1.0] + list(p)
    res = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=[(0.0, 1.0)] * len(atoms),
                  method="highs")
    if not res.success:
        raise RuntimeError("k-of-n bound LP failed: " + res.message)
    return float(min(1.0, max(0.0, -res.fun)))


def brute_force_k_of_n_upper(marginals, k: int, grid: int = 0) -> float:
    """Second independent LP path (dense simplex) cross-checking the closed form."""
    p, n = _check(marginals, k)
    atoms = list(itertools.product([0, 1], repeat=n))
    objective = np.array([-1.0 if sum(a) >= k else 0.0 for a in atoms])
    a_eq = [[1.0] * len(atoms)] + [[float(a[i]) for a in atoms] for i in range(n)]
    b_eq = [1.0] + list(p)
    res = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=[(0.0, 1.0)] * len(atoms),
                  method="highs-ds")
    return float(min(1.0, max(0.0, -res.fun)))

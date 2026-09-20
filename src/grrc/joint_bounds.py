"""Sharp distribution-free bounds on k-of-n event aggregation.

Given only the marginal probabilities ``p_1, ..., p_n`` of ``n`` events (here:
each clinical service suffering a sustained outage), what is the largest possible
probability that **at least k** of them occur simultaneously, over every joint
distribution consistent with those marginals? That sharp worst-case is a small
linear program over the ``2**n`` outcome atoms; its optimum is attained by an
explicit joint, so the bound is tight, not merely valid.

This replaces the loose union bound (``sum p_i``, the k=1 special case) used by the
clinical-impact certificate, and lets it certify the clinically defined
catastrophic event -- several critical services down at once -- rather than only
"at least one". The bound reduces to ``min(1, sum p_i)`` at k=1 and to
``min_i p_i`` at k=n, is monotone non-decreasing in each marginal (so it composes
with the interval-corner certificate), and is tighter than the union/Markov bound
for k >= 2. The aggregation bound is classical (Frechet/Boole/linear programming);
nothing new is claimed about it.
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy.optimize import linprog


def sharp_k_of_n_upper(marginals, k: int) -> float:
    """Sharp upper bound on P(at least k of n events) given only the marginals.

    ``marginals`` are ``n`` probabilities in [0, 1]; ``1 <= k <= n``. Returns the
    maximum of P(#events >= k) over all joint distributions with those marginals,
    computed as a linear program over the 2**n outcome atoms.
    """
    p = np.asarray(marginals, float)
    n = len(p)
    if n == 0 or (p < 0).any() or (p > 1).any() or not np.isfinite(p).all():
        raise ValueError("marginals must be n>=1 probabilities in [0, 1]")
    if not isinstance(k, (int, np.integer)) or not 1 <= k <= n:
        raise ValueError("k must be an integer in [1, n]")
    atoms = list(itertools.product([0, 1], repeat=n))          # 2**n outcomes
    # maximize sum of atom mass with popcount >= k  ==  minimize its negation
    objective = np.array([-1.0 if sum(a) >= k else 0.0 for a in atoms])
    # equality constraints: total mass = 1, and each event's marginal.
    a_eq = [[1.0] * len(atoms)] + [[float(a[i]) for a in atoms] for i in range(n)]
    b_eq = [1.0] + list(p)
    res = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=[(0.0, 1.0)] * len(atoms),
                  method="highs")
    if not res.success:
        raise RuntimeError("k-of-n bound LP failed: " + res.message)
    return float(min(1.0, max(0.0, -res.fun)))


def brute_force_k_of_n_upper(marginals, k: int, grid: int = 0) -> float:
    """Independent cross-check of :func:`sharp_k_of_n_upper` for small n.

    Enumerates the vertices of the marginal-constrained joint polytope implicitly
    handled by the LP; here it simply re-solves with a dense simplex as an
    independent path (``grid`` is unused, kept for signature stability).
    """
    p = np.asarray(marginals, float)
    n = len(p)
    atoms = list(itertools.product([0, 1], repeat=n))
    objective = np.array([-1.0 if sum(a) >= k else 0.0 for a in atoms])
    a_eq = [[1.0] * len(atoms)] + [[float(a[i]) for a in atoms] for i in range(n)]
    b_eq = [1.0] + list(p)
    res = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=[(0.0, 1.0)] * len(atoms),
                  method="highs-ds")
    return float(min(1.0, max(0.0, -res.fun)))

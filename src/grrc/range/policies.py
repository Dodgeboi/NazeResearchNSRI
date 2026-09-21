"""Reference automated defenders for the cyber range (all non-LLM).

Each policy either produces an *acquisition order* -- the sequence in which it would
add mitigations -- or, for the exact optimiser, a specific portfolio. The runner
turns an order into a cost-to-certify by taking the smallest prefix that the range
certifies (``cat_guaranteed`` at the regime's ``k`` and ``epsilon``).

- ``greedy_order`` wraps :func:`grrc.control_certificate.greedy_frontier` -- the
  certificate-informed strong baseline (order by worst-case reachability reduction).
- ``coverage_order`` orders by ATT&CK techniques covered per mitigation, ignoring the
  certificate -- a structure-only heuristic whose larger gap shows the certificate's
  value.
- ``random_order`` is a seeded shuffle (a weak reference).
- ``optimal_small`` finds the exact minimum-cardinality certifying portfolio by
  batched increasing-cardinality search, feasible because catastrophic adequacy is
  monotone in the portfolio; it yields the other policies' optimality gap. It is
  capped (``max_size``) and reports whether the exact value was computed.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

from grrc.control_certificate import greedy_frontier

MAX_EXACT_SIZE = 4        # exhaustive search is only run up to this cardinality
_BATCH = 20000            # portfolios scored per certify call in the exact search


def greedy_order(env):
    order, _ = greedy_frontier(env.regime.base_bounds, env.regime.eff_bounds,
                               env.graph.coverage, env.graph.usage,
                               env.stage_index, env.impact_index)
    return list(order)


def coverage_order(env):
    covered = env.graph.coverage.sum(axis=0)             # per-mitigation technique count
    return [int(m) for m in np.argsort(-covered, kind="stable")]


def random_order(env, seed):
    rng = np.random.default_rng(seed)
    order = np.arange(env.n_mitigations)
    rng.shuffle(order)
    return [int(m) for m in order]


def _cat_guaranteed_mask(env, portfolios):
    """Batched catastrophic-guaranteed mask over a [P, M] boolean portfolio matrix."""
    out = np.zeros(len(portfolios), bool)
    for start in range(0, len(portfolios), _BATCH):
        chunk = portfolios[start:start + _BATCH]
        out[start:start + len(chunk)] = env.catastrophic_certify(chunk)[2]
    return out


def optimal_small(env, max_size=MAX_EXACT_SIZE, upper_bound=None):
    """Exact minimum-cardinality portfolio that is catastrophic-guaranteed.

    Searches cardinalities 0, 1, 2, ... and returns the first size at which some
    subset certifies. Bounded by ``max_size`` and by ``upper_bound`` (e.g. a greedy
    solution's size, since the optimum cannot exceed it). Returns
    ``(indices, size, computed)``; ``computed`` is False when the search was capped
    out before deciding (size unknown but > cap).
    """
    n = env.n_mitigations
    cap = max_size if upper_bound is None else min(max_size, int(upper_bound))
    for size in range(0, cap + 1):
        combos = list(combinations(range(n), size))
        mats = np.zeros((len(combos), n), bool)
        for i, combo in enumerate(combos):
            mats[i, list(combo)] = True
        ok = _cat_guaranteed_mask(env, mats)
        hit = np.flatnonzero(ok)
        if hit.size:
            first = combos[int(hit[0])]
            return list(first), size, True
    # Nothing certified up to the cap. If the cap was the true upper bound, the
    # problem is infeasible; otherwise the optimum is simply beyond the exact cap.
    infeasible = upper_bound is not None and cap >= int(upper_bound)
    return (None, None, True) if infeasible else (None, None, False)

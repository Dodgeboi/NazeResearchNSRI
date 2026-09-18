"""Marginal-Value Restoration (MVR) — dependency-aware recovery sequencing.

Every defense studied so far acts *before or during* the attack and trades
protection against availability. Recovery is the one lever with no such
tradeoff: restoring a node is pure upside. Yet the base engine restores nodes
in a fixed order — descending static zone *criticality* — which is only loosely
related to what actually shortens a service outage.

MVR replaces that order with a greedy that, at each restoration slot, brings
back the node that most increases **weighted service availability right now**,
under the model's own availability rules (a service needs its core functional,
at least ``service_functional_fraction`` of its supporting nodes functional,
and its identity dependency available). Because availability is a threshold
function, the marginal value of a node depends on the current state — a node
that tips a high-weight service back over its threshold is worth far more than
one that merely adds slack to a service already up, even if the latter sits in
a nominally "more critical" zone. Criticality ordering cannot see that; MVR
can, because it evaluates the actual dependency map.

MVR changes only the *sequence* of restoration, never its rate or capacity, so
any improvement is attributable to sequencing alone. It adds no availability
cost and never weakens protection, so — unlike segmentation-timing policies —
it has no regime where it can lose to the baseline; the only question is how
much it helps.

Prior art (honest): this is NOT a novel technique. Dependency-aware,
consequence-minimizing recovery sequencing is an established field — see NIST
SP 800-184 (Guide for Cybersecurity Event Recovery), Sandia's "Optimal
Recovery Sequencing for Enhanced Resilience," generalized network-recovery
optimization (arXiv:1811.07242), standard DR/ITSM restoration-order practice,
and granted patents on application-dependency-based malware recovery. MVR is a
faithful in-model *implementation* of that idea (a greedy on the simulator's
threshold-based service-availability function), useful here only for measuring
how much recovery *sequencing* can matter within this model. Its benefit is
also regime-dependent: under strong defenses (little damage to recover) or weak
detection (little that gets isolated and restored) it is a no-op; it helps only
in the mid-containment regime where substantial isolation-and-restoration
actually happens.
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .defenses import EffectiveSettings
from .models import HospitalNetwork
from .propagation import RansomwareSimulation
from .service_dependencies import service_availability


class MVRSimulation(RansomwareSimulation):
    """A simulation whose only change from the base engine is the restoration
    order: a greedy maximizing marginal weighted-service availability."""

    #: Cap on how many candidates the greedy ranks explicitly. Nodes beyond
    #: the top-``_GREEDY_CAP`` by criticality are appended in criticality
    #: order; a low-criticality node almost never tips a high-weight service
    #: over its threshold, so this bounds cost with negligible quality loss.
    _GREEDY_CAP = 64

    def __init__(self, cfg: Config, net: HospitalNetwork,
                 eff: EffectiveSettings, rng: np.random.Generator) -> None:
        super().__init__(cfg, net, eff, rng)
        self._weights = cfg.service_weights.as_dict()
        self._threshold = cfg.simulation.service_functional_fraction

    def _weighted_available(self, functional: np.ndarray) -> float:
        avail = service_availability(self.net, functional, self._threshold)
        return sum(self._weights[s.value] for s, ok in avail.items() if ok)

    def _restore_order(self, candidates: np.ndarray) -> np.ndarray:
        """Greedy: repeatedly add the candidate that most raises weighted
        service availability once restored, re-evaluating after each pick.

        A restored node becomes functional (not compromised, not isolated), so
        we score each candidate by flipping it into a working copy of the
        functional mask. Ties and any residual candidates fall back to the
        base engine's criticality order, so the result is always a full
        permutation of ``candidates``.
        """
        base_order = super()._restore_order(candidates)
        if candidates.size <= 1 or not self.net.services:
            return base_order

        func = self.functional().copy()
        # Greedy over the top-priority candidates only; the tail keeps
        # criticality order (see _GREEDY_CAP).
        base_list = list(base_order)
        remaining = base_list[:self._GREEDY_CAP]
        tail = base_list[self._GREEDY_CAP:]
        chosen: list[int] = []
        cur = self._weighted_available(func)
        while remaining:
            best_node = remaining[0]
            best_gain = -1.0
            for v in remaining:
                func[v] = True
                gain = self._weighted_available(func) - cur
                func[v] = False
                if gain > best_gain:
                    best_gain, best_node = gain, v
            chosen.append(best_node)
            func[best_node] = True
            cur += best_gain
            remaining.remove(best_node)
            # Once no candidate yields any gain, the rest are indifferent for
            # service availability; keep them in criticality order.
            if best_gain <= 0.0:
                chosen.extend(remaining)
                break
        chosen.extend(tail)
        return np.asarray(chosen, dtype=np.int64)

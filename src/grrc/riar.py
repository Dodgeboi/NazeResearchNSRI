"""Re-Infection-Aware Recovery (RIAR) — recovery under an active intrusion.

The recovery-sequencing literature (NIST SP 800-184, Sandia optimal recovery
sequencing, generalized network-recovery optimization) assumes the disruption
is **over** before recovery begins: you restore components into a quiescent
system. Ransomware recovery in the real world is not like that — organizations
rebuild systems while the intrusion is still live, and freshly reimaged
machines are routinely re-encrypted before the foothold is eradicated. The base
GRRC engine inherits the literature's assumption: it only restores once the
outbreak is fully contained, so re-infection during recovery cannot happen.

Turning on ``simulation.concurrent_recovery`` removes that assumption —
restoration runs during active spread, so a restored node (healthy, reconnected)
can be compromised again by a neighbour that is still active. Under that regime,
naive recovery (restore the most valuable node, reconnect it, watch it fall
again) wastes restore capacity on a treadmill.

RIAR is a recovery policy designed for that regime. It adds, on top of the
marginal-value ordering of :mod:`grrc.mvr`, an **immunize-on-restore** step:
when a node is brought back, it is hardened (patched), so its probability of
immediate re-infection drops by the model's patch effectiveness. Recovery that
sticks, instead of recovery that feeds the attacker.

Novelty status (honest, checked against the literature): this is NOT a novel
technique. "Harden/patch a system before reconnecting it, because fast recovery
during an active incident causes re-infection" is established ransomware-
recovery best practice (Veeam, SentinelOne, ThreatDown and others say exactly
this), and recovery-with-re-infection is the classic SIRS epidemic model, with
"balance treatment vs. recovery" and network immunization both well studied.
RIAR is a faithful in-model *implementation and quantification* of that known
practice against this study's service-weighted damage metric. Its value here is
the measurement — showing how badly naive concurrent recovery churns and how
much immunize-on-restore recovers — not a new idea.
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .defenses import EffectiveSettings
from .models import HospitalNetwork
from .mvr import MVRSimulation


class RIARSimulation(MVRSimulation):
    """Marginal-value recovery ordering + immunize-on-restore, for recovery
    that runs while the intrusion is still active.

    Intended to be run with ``cfg.simulation.concurrent_recovery = True``; it
    is well-defined either way, but its point is the concurrent-recovery
    regime, where re-infection of restored nodes is possible.
    """

    def __init__(self, cfg: Config, net: HospitalNetwork,
                 eff: EffectiveSettings, rng: np.random.Generator) -> None:
        super().__init__(cfg, net, eff, rng)
        self.immune = np.zeros(net.n_nodes, dtype=bool)
        # Restored nodes are hardened; a hardened target's inbound spread
        # probability is scaled by (1 - patch_effectiveness), matching how the
        # engine models a patched target at t=0.
        self._immunity_factor = 1.0 - cfg.simulation.patch_effectiveness

    def _target_factor(self, candidates: np.ndarray) -> np.ndarray | float:
        """Lower inbound spread probability for immunized (restored) targets."""
        if not self.immune.any():
            return 1.0
        dst = self.net.edge_dst[candidates]
        return np.where(self.immune[dst], self._immunity_factor, 1.0)

    def _on_restored(self, nodes: np.ndarray) -> None:
        """Harden nodes as they come back online (immunize-on-restore)."""
        self.immune[nodes] = True

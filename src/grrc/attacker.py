"""Adaptive, service-targeting attacker — a stress test of the study's claims.

The base engine's attacker is memoryless and untargeted: lateral movement is a
uniform per-edge coin flip, indifferent to what a node is worth. Real
ransomware operators are not like that — they work hands-on-keyboard toward the
systems that hurt the most (domain controllers, EHR, backups). The main study's
headline (a full defense portfolio cuts weighted service-hours by ~98%) is
measured against the naive attacker only, so it is worth asking: **does that
resilience survive an attacker that steers toward clinical value?**

``AdaptiveAttackerSimulation`` biases lateral movement toward nodes with high
*downstream clinical value* — the same reverse-BFS service value used by
`grrc.vgri` — abstracting an operator who navigates toward the services whose
loss tips the weighted-damage / availability-threshold structure the defenses
rely on. ``focus`` (alpha) controls sophistication: 0 reproduces the base
attacker exactly, larger values concentrate movement on high-value targets.

Nothing else in the dynamics changes, so a comparison at matched seeds isolates
the effect of attacker targeting. This is a *robustness probe of the study's
conclusions*, not a claim of a novel attack technique (targeted / crown-jewel
lateral movement is well known); the contribution is quantifying how
adversary-dependent the reported defense benefit is.
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .defenses import EffectiveSettings
from .models import HospitalNetwork
from .propagation import RansomwareSimulation
from .vgri import downstream_clinical_value


class AdaptiveAttackerSimulation(RansomwareSimulation):
    """Base dynamics, but lateral movement is biased toward clinical value.

    focus:
        Targeting strength alpha >= 0. The per-edge success probability is
        scaled by ``1 + focus * value_norm[dst]`` (then clamped to 1), where
        ``value_norm`` is the destination node's downstream clinical value
        normalized to [0, 1]. ``focus = 0`` is exactly the base attacker.
    """

    def __init__(self, cfg: Config, net: HospitalNetwork,
                 eff: EffectiveSettings, rng: np.random.Generator, *,
                 focus: float = 3.0) -> None:
        super().__init__(cfg, net, eff, rng)
        self.focus = float(max(0.0, focus))
        value = downstream_clinical_value(net)
        vmax = float(value.max()) if value.size and value.max() > 0 else 1.0
        self._value_norm = value / vmax

    def _target_factor(self, candidates: np.ndarray) -> np.ndarray | float:
        """Boost inbound spread probability toward high-value targets."""
        if self.focus <= 0.0:
            return 1.0
        dst = self.net.edge_dst[candidates]
        return 1.0 + self.focus * self._value_norm[dst]

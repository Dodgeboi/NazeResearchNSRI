"""An adaptive attacker that learns across episodes which strategy hurts a defender most.

Before each episode it draws one of a fixed set of attacker strategies by EXP3
(Auer et al., 2002), observes only that episode's damage (the defender's loss rescaled
to ``[0, 1]``) and updates. Because the choice depends on past outcomes, episodes are
no longer independent; the certification protocol therefore uses the martingale bound
of :func:`grrc.cage.certify.adaptive_bounds` for this attacker.
"""
from __future__ import annotations

import math

import numpy as np


class Exp3:
    def __init__(self, arms, horizon, seed):
        self.arms = list(arms)
        k = len(self.arms)
        self.gamma = min(1.0, math.sqrt(k * math.log(k) / ((math.e - 1) * horizon)))
        self.w = np.ones(k)
        self.rng = np.random.default_rng(seed)
        self.last = None

    def probs(self):
        k = len(self.arms)
        return (1 - self.gamma) * self.w / self.w.sum() + self.gamma / k

    def choose(self):
        p = self.probs()
        i = int(self.rng.choice(len(self.arms), p=p))
        self.last = (i, p[i])
        return self.arms[i]

    def update(self, gain):
        """``gain`` in [0, 1]: how much damage the chosen strategy did."""
        i, p = self.last
        k = len(self.arms)
        self.w[i] *= math.exp(self.gamma * (gain / p) / k)
        self.w /= self.w.max()                    # numerical rescaling only

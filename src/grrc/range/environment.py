"""The defender cyber range: an agent-agnostic API over the provable certificate.

:class:`DefenseRange` presents a control-selection problem on the real ATT&CK-driven
hospital as an observation / action / score loop. The score is **not** an empirical
attack-success rate but a distribution-free residual-risk certificate:

- ``control`` -- worst-/best-corner ransomware reachability to the impact objective
  and the ``guaranteed``/``possible`` adequacy verdict at ``epsilon``
  (:func:`grrc.control_certificate.certify_portfolios`);
- ``catastrophic`` -- worst-/best-corner sharp bound on P(at least ``k`` clinical
  services in simultaneous sustained outage) and its guaranteed mask
  (:func:`grrc.hospital_attack_model.certify_catastrophic`);
- ``cost`` -- the portfolio size.

The primary adequacy target of the benchmark is the catastrophic clinical verdict
(``cat_guaranteed``), because it varies with every regime axis (epsilon, k,
degradation). A stateful add / remove / observe interface is provided so an agentic
defender can drive the range turn by turn; the reference policies use the batched
certify helpers directly. Deterministic; the only inputs are the model and regime.
"""
from __future__ import annotations

import numpy as np

from grrc.control_certificate import certify_portfolios
from grrc.hospital_attack_model import certify_catastrophic
from grrc.range.adversary import adaptive_certify_control, adaptive_certify_catastrophic


class DefenseRange:
    def __init__(self, model, regime):
        self.model = model
        self.graph = model.graph
        self.regime = regime
        # The control certificate's non-impact stages equal the hospital model's
        # stage_index; the impact objective is T1486 alone (graph.impact_index).
        self.stage_index = model.stage_index
        self.impact_index = self.graph.impact_index
        self.n_mitigations = self.graph.n_mitigations
        self._portfolio = np.zeros(self.n_mitigations, bool)
        # Static per-mitigation structure for the observation.
        cov = self.graph.coverage
        self._covered = cov.sum(axis=0)               # techniques covered per mitigation
        from grrc.attack_graph import RANSOMWARE_STAGES
        self._stage_names = [s for s in RANSOMWARE_STAGES if s != "impact"]
        self._touch = {}
        for name, members in zip(self._stage_names, self.stage_index):
            self._touch[name] = cov[members, :].any(axis=0)   # [mitigation] bool

    # -- observation -------------------------------------------------------

    def mitigation_catalog(self):
        """Static ATT&CK structure a defender sees: one record per mitigation."""
        out = []
        for m in range(self.n_mitigations):
            stages = [s for s in self._stage_names if self._touch[s][m]]
            out.append(dict(index=m, id=self.graph.mitigations[m],
                            name=self.graph.mitigation_names[m],
                            techniques_covered=int(self._covered[m]), stages=stages))
        return out

    def portfolio_indices(self):
        return tuple(int(i) for i in np.flatnonzero(self._portfolio))

    # -- stateful agent interface ------------------------------------------

    def reset(self, portfolio=None):
        self._portfolio = self._as_mask(portfolio)
        return self.observe()

    def add(self, index):
        self._check_index(index)
        self._portfolio = self._portfolio.copy()
        self._portfolio[index] = True
        return self.observe()

    def remove(self, index):
        self._check_index(index)
        self._portfolio = self._portfolio.copy()
        self._portfolio[index] = False
        return self.observe()

    def set_portfolio(self, indices):
        self._portfolio = self._as_mask(indices)
        return self.observe()

    def observe(self):
        return dict(portfolio=self.portfolio_indices(), score=self.score())

    # -- scoring (the provable certificate) --------------------------------

    def control_certify(self, portfolios):
        """Batched control-adequacy certificate: (worst, best, guaranteed, possible).

        Dispatches on the regime's adversary: ``typical`` uses the usage-weighted-mean
        certificate; ``adaptive`` uses the max-aggregation best-response adversary.
        """
        portfolios = np.atleast_2d(np.asarray(portfolios, bool))
        if self.regime.adversary == "adaptive":
            return adaptive_certify_control(portfolios, self.regime.base_bounds,
                                            self.regime.eff_bounds, self.model, self.regime.epsilon)
        return certify_portfolios(portfolios, self.regime.base_bounds, self.regime.eff_bounds,
                                  self.graph.coverage, self.graph.usage,
                                  self.stage_index, self.impact_index, self.regime.epsilon)

    def catastrophic_certify(self, portfolios):
        """Batched catastrophic k-of-n certificate: (worst, best, guaranteed, possible)."""
        portfolios = np.atleast_2d(np.asarray(portfolios, bool))
        if self.regime.adversary == "adaptive":
            return adaptive_certify_catastrophic(portfolios, self.regime.base_bounds,
                                                 self.regime.eff_bounds, self.regime.deg_bounds,
                                                 self.model, self.regime.k, self.regime.epsilon)
        return certify_catastrophic(portfolios, self.regime.base_bounds, self.regime.eff_bounds,
                                    self.regime.deg_bounds, self.model, self.regime.k,
                                    self.regime.epsilon)

    def score(self, portfolio=None):
        """Full certified score for one portfolio (defaults to the current state)."""
        mask = self._portfolio if portfolio is None else self._as_mask(portfolio)
        cw, cb, cg, cp = self.control_certify(mask[None])
        kw, kb, kg, kp = self.catastrophic_certify(mask[None])
        return dict(
            cost=int(mask.sum()),
            worst_reachability=float(cw[0]), best_reachability=float(cb[0]),
            guaranteed=bool(cg[0]), possible=bool(cp[0]),
            cat_worst=float(kw[0]), cat_best=float(kb[0]),
            cat_guaranteed=bool(kg[0]), cat_possible=bool(kp[0]))

    # -- helpers -----------------------------------------------------------

    def _as_mask(self, portfolio):
        mask = np.zeros(self.n_mitigations, bool)
        if portfolio is None:
            return mask
        idx = np.asarray(list(portfolio), int)
        if idx.size:
            if idx.min() < 0 or idx.max() >= self.n_mitigations:
                raise ValueError("mitigation index out of range")
            mask[idx] = True
        return mask

    def _check_index(self, index):
        if not isinstance(index, (int, np.integer)) or not 0 <= index < self.n_mitigations:
            raise ValueError("mitigation index out of range")

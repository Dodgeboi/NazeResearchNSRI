"""Certified evaluation of autonomous defenders: time-uniform, distribution-free bounds.

An evaluation episode yields bounded outcomes: the CAGE reward (in ``[r_min, 0]``),
whether the critical server was breached (0/1) and the fraction of steps it was
impacted (in ``[0, 1]``). For each (defender, attacker) pair we report confidence
bounds that hold **simultaneously at every number of episodes**, so evaluation can be
stopped as soon as the answer is settled without invalidating it.

Two cases:

- *Fixed attacker* (episodes i.i.d.): the betting bound of :mod:`grrc.betting`. For a
  fixed betting fraction the capital ``prod (1 + lam (y_s - m))`` is a non-negative
  martingale when the mean is ``m`` (a supermartingale when it is below ``m``), the
  fixed-grid mixture is too, and Ville's inequality makes ``{m : K_t(m) < 1/alpha}``
  valid uniformly over ``t``.
- *Adaptive attacker* (the attacker chooses each episode's strategy from past outcomes):
  observations are no longer independent and the target is the running average of the
  conditional means. With increments in ``[0, 1]``, ``S_t = sum (y_s - mu_s)`` is a
  martingale with 1/4-sub-Gaussian increments, and the normal-mixture boundary
  ``sqrt(2 (t/4 + rho) log(sqrt((t/4 + rho)/rho) / alpha))`` bounds it for all ``t`` with
  probability ``1 - alpha`` (Howard, Ramdas, McAuliffe and Sekhon, 2021).

A worst case over a set of attackers takes the least favourable bound, with the error
level split across attackers (Bonferroni), so the worst-case statement holds jointly.
"""
from __future__ import annotations

import math

import numpy as np

from grrc.betting import betting_lower_bound

RHO = 0.25          # normal-mixture tuning: tightest near t = 4 * RHO / (1/4) episodes, valid for all t


def _scale(x, lo, hi):
    x = np.asarray(x, float)
    if hi <= lo:
        raise ValueError("need lo < hi")
    if (x < lo - 1e-12).any() or (x > hi + 1e-12).any():
        raise ValueError("observation outside its declared bounds")
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def iid_bounds(x, lo, hi, alpha):
    """Time-uniform two-sided bounds on the mean of i.i.d. observations in ``[lo, hi]``
    (each side at ``alpha / 2``). Needs at least two observations."""
    y = _scale(x, lo, hi)
    lower = betting_lower_bound(2 * y - 1, observation_bound=1.0, alpha=alpha / 2)
    upper = -betting_lower_bound(1 - 2 * y, observation_bound=1.0, alpha=alpha / 2)
    to = lambda v: lo + (hi - lo) * (v + 1) / 2
    return float(to(lower)), float(to(upper))


def adaptive_bounds(x, lo, hi, alpha, rho=RHO):
    """Time-uniform two-sided bounds on the running average of conditional means when
    observations may depend on the past (an adaptive attacker); each side at ``alpha/2``."""
    y = _scale(x, lo, hi)
    t = len(y)
    if t < 1:
        raise ValueError("need at least one observation")
    v = t / 4 + rho
    radius = math.sqrt(2 * v * math.log(math.sqrt(v / rho) / (alpha / 2))) / t
    m = float(y.mean())
    return lo + (hi - lo) * max(m - radius, 0.0), lo + (hi - lo) * min(m + radius, 1.0)


def bounds(x, lo, hi, alpha, adaptive=False):
    return adaptive_bounds(x, lo, hi, alpha) if adaptive else iid_bounds(x, lo, hi, alpha)


def worst_case(per_attacker, alpha, higher_is_better):
    """Joint worst case over attackers. ``per_attacker`` maps an attacker name to
    ``(observations, lo, hi, adaptive)``. Each attacker gets ``alpha / k``; returns the
    least favourable certified bound and the attacker attaining it."""
    k = len(per_attacker)
    out = {a: bounds(x, lo, hi, alpha / k, adaptive)
           for a, (x, lo, hi, adaptive) in per_attacker.items()}
    if higher_is_better:
        name = min(out, key=lambda a: out[a][0])
        return out[name][0], name, out
    name = max(out, key=lambda a: out[a][1])
    return out[name][1], name, out


def episodes_to_resolve(x, lo, hi, alpha, threshold, higher_is_better, adaptive=False,
                        min_n=2):
    """First episode count at which the time-uniform bounds settle whether the mean is
    better or worse than ``threshold`` (``None`` if they never do within the data)."""
    x = np.asarray(x, float)
    for n in range(min_n, len(x) + 1):
        lower, upper = bounds(x[:n], lo, hi, alpha, adaptive)
        if lower > threshold or upper < threshold:
            return n
    return None

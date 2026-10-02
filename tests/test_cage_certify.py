import numpy as np
import pytest

from grrc.cage.certify import adaptive_bounds, episodes_to_resolve, iid_bounds, worst_case


def test_iid_bounds_cover_with_peeking_at_every_sample_size():
    """Time-uniform validity: checking after every episode and stopping at the first
    miss still misses the true mean in at most about alpha of runs."""
    rng = np.random.default_rng(0)
    alpha, p, misses, reps = 0.10, 0.3, 0, 300
    for _ in range(reps):
        x = rng.random(60) < p
        for n in range(2, 61, 2):
            lo, hi = iid_bounds(x[:n], 0, 1, alpha)
            if not lo <= p <= hi:
                misses += 1
                break
    assert misses / reps <= alpha


def test_adaptive_bounds_cover_the_running_average_of_conditional_means():
    """An adversary that switches the success probability based on past outcomes:
    the bound must cover the running average of the conditional means at every t."""
    rng = np.random.default_rng(1)
    alpha, misses, reps = 0.10, 0, 300
    for _ in range(reps):
        ys, mus, last = [], [], 0
        for t in range(80):
            mu = 0.8 if last == 0 else 0.1          # adapts to what happened last episode
            y = float(rng.random() < mu)
            ys.append(y); mus.append(mu); last = y
            lo, hi = adaptive_bounds(ys, 0, 1, alpha)
            if not lo <= np.mean(mus) <= hi:
                misses += 1
                break
    assert misses / reps <= alpha


def test_bounds_respect_the_declared_range_and_shrink():
    x = np.full(200, -10.0)
    lo, hi = iid_bounds(x, -100, 0, 0.05)
    assert -100 <= lo <= -10 <= hi <= 0
    lo2, hi2 = iid_bounds(x[:20], -100, 0, 0.05)
    assert hi - lo < hi2 - lo2
    with pytest.raises(ValueError):
        iid_bounds([1.5, 0.2], 0, 1, 0.05)


def test_worst_case_picks_the_least_favourable_attacker_with_split_alpha():
    a = (np.full(50, -5.0), -60, 0, False)
    b = (np.full(50, -20.0), -60, 0, False)
    value, name, per = worst_case({"a": a, "b": b}, 0.05, higher_is_better=True)
    assert name == "b" and value == per["b"][0] and value < -20
    assert per["a"] == iid_bounds(a[0], -60, 0, 0.025)


def test_episodes_to_resolve():
    x = np.zeros(100)                                   # never breached
    n = episodes_to_resolve(x, 0, 1, 0.05, threshold=0.2, higher_is_better=False)
    assert n is not None and n < 40
    assert episodes_to_resolve(np.full(5, 0.2), 0, 1, 0.05, 0.2, False) is None

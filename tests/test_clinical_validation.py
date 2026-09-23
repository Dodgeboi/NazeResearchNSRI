import numpy as np
import pytest

from grrc.clinical_validation import (total_variation, multinomial_gof,
                                      reconciling_gamma, observed_profile,
                                      predicted_profiles)
from grrc.cipher_bounds import CLINICAL_SERVICES


def test_total_variation_hand_values():
    assert total_variation([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.0)
    assert total_variation([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)
    assert total_variation([0.25, 0.25, 0.25, 0.25], [0.3, 0.244, 0.244, 0.212]
                           ) == pytest.approx(0.5 * (0.05 + 0.006 + 0.006 + 0.038), abs=1e-6)


@pytest.mark.parametrize("p,q", [([0.6, 0.4], [0.6, 0.5]), ([-0.1, 1.1], [0.5, 0.5])])
def test_total_variation_rejects_non_distributions(p, q):
    with pytest.raises(ValueError):
        total_variation(p, q)


def test_gof_not_significant_when_counts_match_profile():
    profile = np.array([0.25, 0.25, 0.25, 0.25])
    counts = np.array([25, 25, 25, 25.0])  # exactly the expected counts
    mc, chi, stat = multinomial_gof(counts, profile, draws=5000, seed=1)
    assert stat == pytest.approx(0.0)
    assert mc > 0.5 and chi > 0.5


def test_gof_significant_under_gross_mismatch():
    profile = np.array([0.25, 0.25, 0.25, 0.25])
    counts = np.array([100, 0, 0, 0.0])  # wildly inconsistent with uniform
    mc, chi, stat = multinomial_gof(counts, profile, draws=5000, seed=2)
    assert mc < 0.01 and chi < 0.01


def test_gof_is_approximately_calibrated_under_h0():
    """Under a true H0 the MC p-value is ~uniform, so rejection rate ~ alpha."""
    profile = np.array([0.4, 0.3, 0.2, 0.1])
    rng = np.random.default_rng(7)
    rejections = 0
    reps = 120
    for r in range(reps):
        counts = rng.multinomial(90, profile).astype(float)
        mc, _, _ = multinomial_gof(counts, profile, draws=1500, seed=1000 + r)
        rejections += mc < 0.05
    assert rejections / reps <= 0.15  # loose upper bound around alpha=0.05


def test_gof_rejects_bad_inputs():
    with pytest.raises(ValueError):
        multinomial_gof([1, 2, 3], [0.5, 0.5])            # shape mismatch
    with pytest.raises(ValueError):
        multinomial_gof([1, 2], [0.0, 1.0])               # zero expected cell with a count


def test_reconciling_gamma_zero_iff_exact_match():
    # profile equal to the observed conditional shares -> gamma 0.
    counts = [30, 20, 10, 40.0]
    total = 120  # includes an unmodelled residual of 20
    cond = np.array(counts) / sum(counts)
    assert reconciling_gamma(counts, total, cond) == pytest.approx(0.0)


def test_reconciling_gamma_grows_with_mismatch():
    counts = [30, 20, 10, 40.0]
    total = 120
    near = np.array(counts) / sum(counts)                 # exact conditional shares
    far = np.array([0.20, 0.20, 0.20, 0.40])              # moderately off, still reachable
    g_near = reconciling_gamma(counts, total, near)
    g_far = reconciling_gamma(counts, total, far)
    assert g_near == pytest.approx(0.0)
    assert np.isfinite(g_far) and g_far > g_near


def test_reconciling_gamma_infinite_when_unreachable():
    counts = [30, 20, 10, 40.0]
    total = 120
    extreme = np.array([0.05, 0.05, 0.85, 0.05])          # pharmacy share unreachable
    assert reconciling_gamma(counts, total, extreme) == float("inf")


def test_predicted_profiles_normalised():
    class _M:
        services = tuple(CLINICAL_SERVICES)
        degradation = np.array([[0.30, 0.44], [0.20, 0.40], [0.20, 0.40], [0.17, 0.35]])
    prof = predicted_profiles(_M())
    assert prof["uniform"] == pytest.approx([0.25, 0.25, 0.25, 0.25])
    assert prof["assumed"].sum() == pytest.approx(1.0)
    assert np.argmax(prof["assumed"]) == 0  # EHR-heaviest (assumed), the miscalibration

import numpy as np
import pandas as pd
import pytest

from grrc.interpretation import (PairedBank, make_bank, pairwise_standard_errors,
    covariance_difference_se, baseline_contrasts, objective_ablation,
    frontier_counts, upper_tail_mean, design_pairwise_errors, stratum_indices)


def test_fixed_strata_remove_between_entry_variance_and_retain_pairing():
    values = np.array([[1., 0.], [3., 1.], [101., 100.], [103., 101.]])
    groups = [np.array([0, 1]), np.array([2, 3])]
    paired, independent = design_pairwise_errors(values, groups)
    expected_variance = sum(.25 * np.var((values[:, 0] - values[:, 1])[ix], ddof=1) / 2 for ix in groups)
    assert paired[0, 1] ** 2 == pytest.approx(expected_variance)
    assert independent[0, 1] < pairwise_standard_errors(values)[1][0, 1]


def test_strata_require_replication():
    bank = fixture_bank()
    bank.strata = np.array(["a", "a", "a", "b"])
    with pytest.raises(ValueError, match="two scenarios"):
        stratum_indices(bank)


def fixture_bank():
    loss = np.array([[1., 0.], [3., 1.], [5., 2.], [7., 3.]])
    return PairedBank("test", ["baseline", "control"], np.arange(4), loss,
                      np.zeros((4, 2, 4)), np.zeros((4, 2)),
                      np.array([[0., 0.], [1., 1.]]), np.array([True, False]))


def test_paired_se_matches_direct_difference_and_handles_negative_covariance():
    values = np.array([[1., 2., 4.], [2., 3., 3.], [3., 4., 2.], [4., 5., 1.]])
    paired, independent = pairwise_standard_errors(values)
    for i in range(3):
        for j in range(3):
            assert paired[i, j] == pytest.approx((values[:, i] - values[:, j]).std(ddof=1) / 2)
    assert paired[0, 1] == pytest.approx(0)
    assert paired[0, 2] > independent[0, 2]


def test_bootstrap_estimator_covariance_has_no_extra_division_by_draws():
    draws = np.array([[1., 0.], [2., 1.], [4., 1.], [8., 2.]])
    paired, _ = covariance_difference_se(draws)
    assert paired[0, 1] == pytest.approx((draws[:, 0] - draws[:, 1]).std(ddof=1))


def test_simultaneous_intervals_account_for_comparison_family():
    bank = fixture_bank()
    one = baseline_contrasts(bank, 1).iloc[0]
    many = baseline_contrasts(bank, 100).iloc[0]
    assert one.mean_hours_saved == pytest.approx(2.5)
    assert many.simultaneous_lower < one.simultaneous_lower
    assert many.simultaneous_upper > one.simultaneous_upper
    assert many.pointwise_lower == one.pointwise_lower


def test_zero_observed_variance_is_not_reported_as_certain_effect():
    bank = fixture_bank()
    bank.loss[:, 1] = bank.loss[:, 0] - 1
    row = baseline_contrasts(bank, 1).iloc[0]
    assert pd.isna(row.simultaneous_lower)
    assert row.interval_status.startswith("unestimable")


def test_tail_convention_preserves_quantile_ties():
    values = np.array([[0, 0], [0, 2], [0, 2], [10, 2]], float)
    np.testing.assert_allclose(upper_tail_mean(values), [10, 2])


def test_restricted_view_counts_known_hidden_and_spurious_candidates():
    matrix = np.array([[1, 1], [2, 2], [0, 3]], float)
    counts = frontier_counts(matrix, np.array([False, True, True]))
    assert counts == {"full_frontier": 2, "restricted_frontier": 2,
                      "omitted_efficient": 1, "restricted_artifacts": 1}


def test_objective_ablation_covers_every_nonempty_subset():
    result = objective_ablation(fixture_bank())
    assert len(result) == 63
    assert result.groupby("dimensions").size().tolist() == [6, 15, 20, 15, 6, 1]


def test_bank_rejects_incomplete_pairing_and_reversed_endpoint():
    records = []
    for scenario in (1, 2):
        for portfolio in ("baseline", "control"):
            records.append({"profile": "test", "portfolio": portfolio,
                "scenario_id": scenario, "paired": 1,
                "weighted_service_hours_lost": 1, "recovered_within_horizon": 1,
                **{f"sustained_clinical_outage_k{k}": 0 for k in range(1, 5)}})
    raw = pd.DataFrame(records)
    summary = pd.DataFrame({"profile": ["test"] * 2,
        "portfolio": ["baseline", "control"], "implementation_cost_points": [0, 1],
        "operational_burden_points": [0, 1]})
    with pytest.raises(ValueError, match="incomplete"):
        make_bank(raw.iloc[:-1], summary, "test", ["baseline"])
    raw.loc[0, "sustained_clinical_outage_k4"] = 1
    with pytest.raises(ValueError, match="monotonically"):
        make_bank(raw, summary, "test", ["baseline"])

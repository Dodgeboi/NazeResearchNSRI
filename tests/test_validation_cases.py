"""Run the 12 formal validation cases as pytest tests.

These are the same functions executed by `python -m grrc.cli validate`;
running them here guarantees the validation suite itself is enforced by
`pytest`. The convergence case uses reduced sample sizes to keep the test
suite fast — the CLI runs the full 100/250/500/1000 version.
"""

import pytest

from grrc import validation as v


@pytest.mark.parametrize("check", [
    v.check_zero_spread,
    v.check_guaranteed_spread,
    v.check_disconnected_zone,
    v.check_isolated_backup,
    v.check_patch_immunity,
    v.check_isolation_blocks_spread,
    v.check_reproducibility,
    v.check_seed_variation,
    v.check_service_dependency,
    v.check_budget_respected,
    v.check_data_integrity,
], ids=lambda c: c.__name__)
def test_validation_case(check):
    result = check()
    assert result.passed, result.details


def test_convergence_reduced():
    result = v.check_convergence(sample_sizes=(50, 100, 200))
    assert result.passed, result.details

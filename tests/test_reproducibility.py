"""Reproducibility guarantees: identical seeds -> identical results."""

import numpy as np

from grrc.config import default_config
from grrc.models import TrialSpec
from grrc.simulation import run_trial
from grrc.utilities import trial_rng


def _spec(tid=1, **kw):
    defaults = dict(trial_id=tid, experiment="test",
                    facility="small_clinic", profile="intermediate_capacity",
                    portfolio="seg_plus_detection", entry_point="workstation",
                    master_seed=default_config().seed)
    defaults.update(kw)
    return TrialSpec(**defaults)


def test_trial_rng_is_deterministic():
    a = trial_rng(123, 7).random(5)
    b = trial_rng(123, 7).random(5)
    assert np.array_equal(a, b)


def test_trial_rng_streams_differ_by_trial_id():
    a = trial_rng(123, 7).random(5)
    b = trial_rng(123, 8).random(5)
    assert not np.array_equal(a, b)


def test_identical_trials_are_identical():
    cfg = default_config()
    assert run_trial(cfg, _spec()) == run_trial(cfg, _spec())


def test_different_master_seed_changes_outcome_distribution():
    cfg = default_config()
    rows_a = [run_trial(cfg, _spec(tid=t, master_seed=1))
              ["total_compromised"] for t in range(8)]
    rows_b = [run_trial(cfg, _spec(tid=t, master_seed=2))
              ["total_compromised"] for t in range(8)]
    assert rows_a != rows_b


def test_row_contains_reproduction_fields():
    cfg = default_config()
    row = run_trial(cfg, _spec())
    for field in ("trial_id", "master_seed", "facility", "profile",
                  "portfolio", "entry_point", "patch_coverage",
                  "detection_delay", "backup_strategy", "segmentation"):
        assert field in row

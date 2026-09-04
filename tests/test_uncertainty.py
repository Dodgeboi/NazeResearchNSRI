"""Tests for parameter uncertainty over unidentified coefficients.

The property that matters most is the pairing one: a parameter vector must
be shared by every candidate replaying a scenario. If it were drawn per
trial instead, two portfolios would be compared under different physics and
the common-random-numbers design — the thing that makes the whole study a
comparison rather than a collection of runs — would be silently broken.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from grrc.config import ConfigError, load_config
from grrc.uncertainty import (PARAMETER_STREAM, apply_parameters,
                              sample_parameters)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "multiobjective_portfolio.yaml"


@pytest.fixture(scope="module")
def cfg():
    return load_config(CONFIG)


def test_the_study_config_enables_uncertainty(cfg):
    assert cfg.parameter_uncertainty.enabled
    assert len(cfg.parameter_uncertainty.ordered_names()) >= 8


def test_draws_are_shared_within_a_scenario_and_differ_between(cfg):
    """The pairing property. Everything else here is secondary."""
    first = sample_parameters(cfg, 123, 7)
    again = sample_parameters(cfg, 123, 7)
    other = sample_parameters(cfg, 123, 8)
    assert first == again, (
        "two candidates replaying one scenario must see identical parameters")
    assert first != other


def test_draws_depend_on_the_master_seed(cfg):
    assert sample_parameters(cfg, 1, 7) != sample_parameters(cfg, 2, 7)


def test_every_draw_lands_inside_its_declared_range(cfg):
    ranges = {f"{section}.{name}": bounds
              for section, name, bounds in cfg.parameter_uncertainty.ordered_names()}
    for scenario in range(40):
        for key, value in sample_parameters(cfg, 99, scenario).items():
            low, high = ranges[key]
            assert low <= value <= high, (key, value, low, high)


def test_sampling_order_does_not_depend_on_yaml_key_order(cfg):
    """A reordered config must reproduce the same draws.

    Otherwise a cosmetic edit to the config silently changes every result.
    """
    shuffled = copy.deepcopy(cfg)
    shuffled.parameter_uncertainty.simulation = dict(
        reversed(list(cfg.parameter_uncertainty.simulation.items())))
    assert sample_parameters(shuffled, 5, 5) == sample_parameters(cfg, 5, 5)


def test_disabled_uncertainty_draws_nothing(cfg):
    off = copy.deepcopy(cfg)
    off.parameter_uncertainty.enabled = False
    assert sample_parameters(off, 1, 1) == {}
    assert apply_parameters(off, {}) is off


def test_apply_does_not_mutate_the_shared_config(cfg):
    """Workers share one config object; mutating it would corrupt the run."""
    before = cfg.simulation.base_spread_rate
    drawn = sample_parameters(cfg, 7, 7)
    applied = apply_parameters(cfg, drawn)
    assert cfg.simulation.base_spread_rate == before
    assert applied.simulation.base_spread_rate == pytest.approx(
        drawn["simulation.base_spread_rate"])
    assert applied is not cfg


def test_parameter_stream_is_reserved(cfg):
    """The parameter stream must not collide with a step-level event stream.

    Streams 10-15 carry spread, detection, isolation, false positives,
    residual backup failure and the isolation lapse. Reusing one would make
    parameter draws perturb those events.
    """
    assert PARAMETER_STREAM == 16


def test_unknown_field_is_rejected_at_load(tmp_path):
    config = tmp_path / "bad.yaml"
    config.write_text(
        "mode: standard\nparameter_uncertainty:\n  enabled: true\n"
        "  simulation:\n    not_a_real_field: [0.1, 0.2]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not a simulation field"):
        load_config(config)


def test_inverted_range_is_rejected_at_load(tmp_path):
    config = tmp_path / "bad.yaml"
    config.write_text(
        "mode: standard\nparameter_uncertainty:\n  enabled: true\n"
        "  simulation:\n    base_spread_rate: [0.5, 0.1]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="low 0.5 > high 0.1"):
        load_config(config)


def test_drawn_values_reach_the_result_row(cfg):
    """Every draw is recorded, so results can be re-analysed by parameter."""
    from grrc.defenses import enumerate_portfolios
    from grrc.models import TrialSpec
    from grrc.simulation import run_trial

    small = copy.deepcopy(cfg)
    small.simulation.max_steps = 30
    name = "seg-flat|patch+0|det0|iso0|bak-connected|idm0"
    portfolio = next(p for p in enumerate_portfolios() if p.name == name)
    row = run_trial(small, TrialSpec(
        trial_id=1, experiment="test", facility="regional_hospital",
        profile="resource_constrained", portfolio=name,
        entry_point="workstation", master_seed=31, scenario_id=31,
        paired=True), portfolio=portfolio)

    assert "param_simulation_base_spread_rate" in row
    assert "param_network_backup_isolation_lapse" in row
    drawn = sample_parameters(small, 31, 31)
    assert row["param_simulation_base_spread_rate"] == pytest.approx(
        drawn["simulation.base_spread_rate"], abs=1e-7)


def test_two_candidates_in_one_scenario_record_the_same_parameters(cfg):
    from grrc.defenses import enumerate_portfolios
    from grrc.models import TrialSpec
    from grrc.simulation import run_trial

    small = copy.deepcopy(cfg)
    small.simulation.max_steps = 30
    catalog = {p.name: p for p in enumerate_portfolios()}
    rows = []
    for trial, name in enumerate((
            "seg-flat|patch+0|det0|iso0|bak-connected|idm0",
            "seg-least_privilege|patch+1|det1|iso1|bak-isolated|idm1")):
        rows.append(run_trial(small, TrialSpec(
            trial_id=trial, experiment="test", facility="regional_hospital",
            profile="resource_constrained", portfolio=name,
            entry_point="workstation", master_seed=77, scenario_id=77,
            paired=True), portfolio=catalog[name]))
    keys = [k for k in rows[0] if k.startswith("param_")]
    assert keys
    for key in keys:
        assert rows[0][key] == rows[1][key], key

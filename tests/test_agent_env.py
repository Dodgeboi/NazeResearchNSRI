"""The defender environment: fidelity to the simulator, and its contracts."""

from __future__ import annotations

import pytest

from grrc.agent_env import (CONNECTED, DISCONNECT, ISLANDS, MICRO_LOCKDOWN,
                            ZONE_LOCKDOWN, DefenderEnv)
from grrc.config import default_config, load_config
from grrc.defender_agents import OnAlert, Passive, run_episode
from grrc.defenses import DefensePortfolio
from grrc.enums import CLINICAL_SERVICES
from grrc.models import TrialSpec
from grrc.simulation import run_trial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config(ROOT / "configs" / "multiobjective_portfolio.yaml")


def _spec(sid, profile="intermediate_capacity", entry="workstation"):
    return TrialSpec(trial_id=sid, scenario_id=sid, paired=True,
                     experiment="t", facility="regional_hospital",
                     profile=profile, portfolio="profile_baseline",
                     entry_point=entry, master_seed=4321)


@pytest.mark.parametrize("sid,profile,entry", [
    (1, "resource_constrained", "workstation"),
    (2, "intermediate_capacity", "vendor_connection"),
    (3, "high_capacity", "privileged_system"),
    (4, "intermediate_capacity", "medical_device"),
])
def test_passive_episode_reproduces_run_trial_exactly(sid, profile, entry):
    """The environment is the simulator, not a re-implementation of it."""
    spec = _spec(sid, profile, entry)
    expected = run_trial(CFG, spec,
                         portfolio=DefensePortfolio("profile_baseline"))
    got = run_episode(Passive(), DefenderEnv(CFG, spec))
    shared = [k for k in expected if k in got]
    assert len(shared) > 40
    assert {k: got[k] for k in shared} == {k: expected[k] for k in shared}


def test_action_sets_depend_on_architecture():
    today = DefenderEnv(CFG, _spec(5))
    today.reset()
    assert ISLANDS not in today.available_modes()
    with pytest.raises(ValueError):
        today.set_mode(ISLANDS)
    replicas = DefenderEnv(CFG, _spec(5), replicas=True)
    replicas.reset()
    assert ISLANDS in replicas.available_modes()


def test_lockdowns_cannot_self_inflict():
    """They keep the required paths, so no declared dependency is severed."""
    for mode in (ZONE_LOCKDOWN, MICRO_LOCKDOWN):
        row = run_episode(OnAlert(mode), DefenderEnv(CFG, _spec(6)))
        assert row["self_inflicted_steps"] == 0


def test_disconnect_takes_services_down_in_a_healthy_estate():
    env = DefenderEnv(CFG, _spec(7))
    env.reset()
    assert all(env.availability_under(CONNECTED)[s]
               for s in CLINICAL_SERVICES)
    assert set(env.self_inflicted(DISCONNECT)) == set(CLINICAL_SERVICES)


def test_rewards_account_for_every_compromise_and_every_clinical_hour():
    spec = _spec(8, "resource_constrained")
    for kind in ("containment", "clinical"):
        env = DefenderEnv(CFG, spec, reward=kind)
        env.reset()
        start_compromised = int(env.sim.ever_comp.sum())
        total, done = 0.0, False
        while not done:
            _, r, done = env.step(CONNECTED)
            total += r
        row = env.finish()
        if kind == "containment":
            assert total == -(row["total_compromised"] - start_compromised)
        else:
            hours = (row["time_averaged_weighted_clinical_unavailability"]
                     * row["horizon_steps"] * row["step_minutes"] / 60.0)
            assert total == pytest.approx(-hours)


def test_paired_agents_face_the_same_incident():
    a, b = DefenderEnv(CFG, _spec(9)), DefenderEnv(CFG, _spec(9))
    a.reset(), b.reset()
    assert a.sim.net.n_nodes == b.sim.net.n_nodes
    assert (a.sim.comp == b.sim.comp).all()  # same entry node


def test_unknown_reward_rejected():
    with pytest.raises(ValueError):
        DefenderEnv(default_config(), _spec(1), reward="vibes")

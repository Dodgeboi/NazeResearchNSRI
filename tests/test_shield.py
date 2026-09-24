"""The dependency-closure shield's guarantee, checked independently.

The environment counts self-inflicted unavailability itself, but a test that
reads that counter would only confirm the code agrees with itself. These tests
re-derive the property on every recorded step from the availability functions
directly, through a second monitor chained after the environment's own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grrc.agent_env import (CONNECTED, DISCONNECT, ISLANDS, ZONE_LOCKDOWN,
                            DefenderEnv)
from grrc.config import load_config
from grrc.defender_agents import OnAlert, Passive, run_episode
from grrc.enums import CLINICAL_SERVICES, Zone
from grrc.islanding import islanded_service_availability
from grrc.models import TrialSpec
from grrc.service_dependencies import service_availability
from grrc.shield import DependencyClosureShield

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config(ROOT / "configs" / "multiobjective_portfolio.yaml")


def _spec(sid, profile, entry):
    return TrialSpec(trial_id=sid, scenario_id=sid, paired=True,
                     experiment="t", facility="regional_hospital",
                     profile=profile, portfolio="profile_baseline",
                     entry_point=entry, master_seed=8080)


def _violations_by_independent_check(agent, env) -> int:
    """Run an episode, re-checking the shield property on every step."""
    violations = []
    agent.reset()
    obs = env.reset()
    own_monitor = env.sim.step_monitor
    threshold = env.cfg.simulation.service_functional_fraction

    def checked(t):
        own_monitor(t)  # the environment (and shield) act first
        sim = env.sim
        functional = sim.functional()
        reference = service_availability(sim.net, functional, threshold)
        plan = sim.island_plan
        if sim.islanded and plan is not None and plan.severs_dependencies:
            actual = islanded_service_availability(sim.net, functional,
                                                   threshold, plan)
        else:
            actual = service_availability(sim.net, functional, threshold)
        if any(reference[s] and not actual[s] for s in CLINICAL_SERVICES):
            violations.append(t)

    env.sim.step_monitor = checked
    done = False
    while not done:
        obs, _, done = env.step(agent.act(obs))
    env.finish()
    return len(violations)


CASES = [(sid, profile, entry)
         for sid, (profile, entry) in enumerate([
             ("high_capacity", "workstation"),
             ("high_capacity", "vendor_connection"),
             ("intermediate_capacity", "privileged_system"),
             ("intermediate_capacity", "medical_device"),
             ("resource_constrained", "internet_facing"),
             ("resource_constrained", "workstation")], start=100)]


@pytest.mark.parametrize("sid,profile,entry", CASES)
def test_shield_property_holds_on_every_step(sid, profile, entry):
    for mode, replicas in ((DISCONNECT, False), (ISLANDS, True)):
        env = DefenderEnv(CFG, _spec(sid, profile, entry), replicas=replicas,
                          shield=DependencyClosureShield())
        assert _violations_by_independent_check(OnAlert(mode), env) == 0


def test_unshielded_disconnect_violates_it_so_the_check_is_not_vacuous():
    total = 0
    for sid, profile, entry in CASES:
        env = DefenderEnv(CFG, _spec(sid, profile, entry))
        total += _violations_by_independent_check(OnAlert(DISCONNECT), env)
    assert total > 0


def test_shield_rejects_disconnect_in_a_healthy_estate_and_admits_lockdown():
    shield = DependencyClosureShield()
    env = DefenderEnv(CFG, _spec(1, "high_capacity", "workstation"),
                      shield=shield)
    env.reset()
    assert shield.admit(env, DISCONNECT) == CONNECTED
    assert shield.admit(env, ZONE_LOCKDOWN) == ZONE_LOCKDOWN
    assert shield.rejections == 1


def test_shield_admits_disconnect_once_identity_is_already_lost():
    """The property is state-dependent, not a ban on cutting.

    When every identity-dependent clinical service is already down, cutting
    the network cannot take down anything more, so the shield lets the
    defender cut — keeping the containment benefit and losing nothing.
    """
    shield = DependencyClosureShield()
    env = DefenderEnv(CFG, _spec(2, "high_capacity", "workstation"),
                      shield=shield)
    env.reset()
    identity = env.sim.net.nodes_in_zone(Zone.IDENTITY)
    env.sim.comp[identity] = True  # identity service is lost
    assert not any(env.availability_under(CONNECTED)[s]
                   for s in CLINICAL_SERVICES)
    assert shield.admit(env, DISCONNECT) == DISCONNECT


def test_shield_is_inert_for_agents_that_never_sever():
    spec = _spec(3, "intermediate_capacity", "workstation")
    for agent in (Passive(), OnAlert(ZONE_LOCKDOWN)):
        plain = run_episode(agent, DefenderEnv(CFG, spec))
        shielded = run_episode(agent, DefenderEnv(
            CFG, spec, shield=DependencyClosureShield()))
        assert plain == shielded

r"""Play a CAGE-2 episode with the *attacker* under external control.

The defender study (:func:`grrc.cage.env.run_episode`) registers Red as the CybORG agent
and steps Blue. To evaluate a *primitive-action attacker* -- one that issues raw CybORG Red
actions itself -- we invert control without disturbing the defender's own interface: Red is
registered as a :class:`ControllableRed` shim whose next action we set each step, and the
defender is stepped exactly as in :func:`run_episode`. Because CybORG's
``EnvironmentController.step`` executes *every* registered agent's action each step (the
stepped agent uses the passed action, the rest their ``get_action``), injecting Red's action
through the shim yields the same dynamics as registering a scripted Red directly -- which is
the correctness gate (:mod:`tests.test_cage_primitive`): replaying ``B_lineAgent``'s own
actions through this path reproduces its breach outcomes from :func:`run_episode`.

``run_defender_vs_red(defender, red_policy, steps, seed)`` returns the attacker's outcome:
``breached`` (Red ran a successful Impact on ``Op_Server0`` at least once), the per-step
Impact count, the defender's reward (negated: the attacker's gain), and the trace. The
``red_policy`` exposes ``get_action(red_obs, red_space) -> CybORG action`` and, optionally,
``reset()``; it may be a scripted agent (the oracle) or a language model.
"""
from __future__ import annotations

import random

import numpy as np

from CybORG.Agents.SimpleAgents.BaseAgent import BaseAgent
from CybORG.Shared.Actions import Sleep

from grrc.cage.env import SCENARIO, _challenge_wrapper, make_env

OP_SERVER = "Op_Server0"


class ControllableRed(BaseAgent):
    """A Red agent that plays whatever action is placed in ``next_action`` each step."""

    def __init__(self):
        self.next_action = Sleep()

    def get_action(self, observation, action_space):
        return self.next_action

    def train(self, results):
        pass

    def end_episode(self):
        self.next_action = Sleep()

    def set_initial_values(self, action_space, observation):
        pass


def _impact_on_op_server(cyborg):
    """True iff Red's last action was a successful Impact on the operational server."""
    action = cyborg.get_last_action("Red")
    if type(action).__name__ != "Impact":
        return False
    if getattr(action, "hostname", None) not in (None, OP_SERVER):
        return False
    return str(cyborg.get_observation("Red").get("success")) == "TRUE"


def run_defender_vs_red(defender, red_policy, steps, seed=None, reseed=True, scenario=SCENARIO):
    """Play one episode with ``red_policy`` driving Red against ``defender``."""
    if reseed and seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    cyborg = make_env(ControllableRed, scenario)
    shim = cyborg.environment_controller.agent_interfaces["Red"].agent
    mode = getattr(defender, "interface", "vector")
    defender.end_episode()
    if hasattr(red_policy, "reset"):
        red_policy.reset()
    if mode == "vector":
        env = _challenge_wrapper(cyborg)
        obs = env.reset()
        space = env.get_action_space("Blue")
    elif mode == "raw":
        res = cyborg.reset(agent="Blue")
        obs, space = res.observation, res.action_space
    elif mode == "table":
        from CybORG.Agents.Wrappers import BlueTableWrapper
        env = BlueTableWrapper(cyborg, output_mode="table")
        obs = env.reset(agent="Blue").observation
        space = cyborg.get_action_space("Blue")
    else:
        raise ValueError(f"unknown interface {mode!r}")
    red_space = cyborg.get_action_space("Red")
    total, impacts, trace = 0.0, 0, []
    for t in range(steps):
        red_obs = cyborg.get_observation("Red")
        shim.next_action = red_policy.get_action(red_obs, red_space)
        if mode == "table":
            blue_action = defender.get_action(obs, space, cyborg=cyborg, step=t, steps=steps)
        else:
            blue_action = defender.get_action(obs, space)
        if mode == "vector":
            obs, reward, _, _ = env.step(blue_action)
        elif mode == "raw":
            res = cyborg.step(agent="Blue", action=blue_action)
            obs, reward = res.observation, res.reward
        else:
            res = env.step(agent="Blue", action=blue_action)
            obs, reward = res.observation, res.reward
        hit = _impact_on_op_server(cyborg)
        impacts += hit
        total += reward
        trace.append(dict(blue=str(cyborg.get_last_action("Blue")),
                          red=str(cyborg.get_last_action("Red")), reward=float(reward),
                          impact=bool(hit)))
    return dict(reward=float(total), impacts=int(impacts), steps=int(steps),
                impact_fraction=impacts / steps, breached=impacts > 0), trace

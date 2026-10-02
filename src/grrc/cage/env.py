"""Episodes of CAGE Challenge 2 (CybORG Scenario 2) with any defender.

Each defender declares the interface it consumes: ``"vector"`` (the challenge's
integer-action gym view, through the winning agent's corrected ``ChallengeWrapper2``),
``"raw"`` (CybORG's own observation and action objects, as the official scripted
agents use) or ``"table"`` (the human-readable Blue table, for language-model agents).
The runner steps the environment, sums the official Blue reward, and records the
outcomes the certification protocol uses:

- ``reward``: the CAGE episode reward (a penalty, at most 0);
- ``impacts``: steps in which the attacker successfully ran *Impact* on the operational
  server (the challenge's critical asset); ``impact_fraction = impacts / steps``;
- ``breached``: whether any such impact happened in the episode.

Episodes are seeded through Python's and NumPy's global generators, which is how
CybORG draws randomness, so a (defender, attacker, seed) triple is reproducible.
"""
from __future__ import annotations

import inspect
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
CARDIFF = ROOT / "vendor/cage/cardiff"
SCENARIO = "Scenario2"


def scenario_path():
    from CybORG import CybORG
    return str(Path(inspect.getfile(CybORG)).parent / "Shared/Scenarios" / f"{SCENARIO}.yaml")


def make_env(red_agent):
    from CybORG import CybORG
    return CybORG(scenario_path(), "sim", agents={"Red": red_agent})


def _challenge_wrapper(cyborg):
    if str(CARDIFF) not in sys.path:
        sys.path.insert(0, str(CARDIFF))
    from Wrappers.ChallengeWrapper2 import ChallengeWrapper2
    return ChallengeWrapper2(env=cyborg, agent_name="Blue")


def _impact_succeeded(cyborg):
    action = cyborg.get_last_action("Red")
    if type(action).__name__ != "Impact":
        return False
    return str(cyborg.get_observation("Red").get("success")) == "TRUE"


def run_episode(defender, red_agent, steps, seed=None, reseed=True):
    """Play one episode; returns a dict of outcomes plus the per-step trace."""
    if reseed and seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    cyborg = make_env(red_agent)
    mode = getattr(defender, "interface", "vector")
    defender.end_episode()
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
    total, impacts, trace = 0.0, 0, []
    for t in range(steps):
        if mode == "table":
            action = defender.get_action(obs, space, cyborg=cyborg, step=t, steps=steps)
        else:
            action = defender.get_action(obs, space)
        if mode == "vector":
            obs, reward, _, _ = env.step(action)
        elif mode == "raw":
            res = cyborg.step(agent="Blue", action=action)
            obs, reward = res.observation, res.reward
        else:
            res = env.step(agent="Blue", action=action)
            obs, reward = res.observation, res.reward
        hit = _impact_succeeded(cyborg)
        impacts += hit
        total += reward
        trace.append(dict(blue=str(cyborg.get_last_action("Blue")),
                          red=str(cyborg.get_last_action("Red")), reward=float(reward),
                          impact=bool(hit)))
    out = dict(reward=float(total), impacts=int(impacts), steps=int(steps),
               impact_fraction=impacts / steps, breached=impacts > 0)
    extra = getattr(defender, "episode_info", None)
    if callable(extra):
        out.update(extra())
    return out, trace

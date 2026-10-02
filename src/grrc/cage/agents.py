"""Attackers and reference defenders for the CAGE Challenge 2 study.

Attackers (Red) are CybORG agent classes. Besides the two official scripted attackers
(``B_lineAgent``, which heads straight for the operational server, and
``RedMeanderAgent``, which explores the network first), two *unseen* variants test how
far a defender's guarantees transfer beyond the attackers it was built against:

- :func:`delayed` -- the same attacker after a random pause of 1..``max_delay`` steps,
  which shifts the scan pattern a defender may use to recognise its opponent;
- :func:`switching` -- explores like Meander for a few steps, then follows B_line's
  direct path to the operational server.

Both only re-sequence the official attackers' own actions; they add no new capability.

Defenders (Blue) share one interface: ``interface`` names the observation they consume
(see :mod:`grrc.cage.env`), ``get_action`` picks an action and ``end_episode`` resets.
"""
from __future__ import annotations

import random

from CybORG.Agents import B_lineAgent, RedMeanderAgent, SleepAgent
from CybORG.Agents.SimpleAgents.BaseAgent import BaseAgent
from CybORG.Agents.SimpleAgents.BlueReactAgent import BlueReactRemoveAgent, BlueReactRestoreAgent
from CybORG.Shared.Actions import Sleep


def delayed(base, max_delay=5):
    """``base`` after a uniformly random pause of 1..``max_delay`` steps (drawn per episode
    from the seeded global generator)."""

    class Delayed(BaseAgent):
        def __init__(self):
            self.inner = base()
            self.wait = random.randint(1, max_delay)
            self.initial = None

        def get_action(self, observation, action_space):
            if self.initial is None:
                self.initial = observation        # the episode's initial view (start host)
            if self.wait > 0:
                self.wait -= 1
                return Sleep()
            if self.wait == 0:                     # first real move: show the initial view
                self.wait = -1
                return self.inner.get_action(self.initial, action_space)
            return self.inner.get_action(observation, action_space)

        def train(self, results):
            pass

        def end_episode(self):
            self.inner.end_episode()
            self.wait = random.randint(1, max_delay)
            self.initial = None

        def set_initial_values(self, action_space, observation):
            pass

    Delayed.__name__ = f"Delayed{base.__name__}"
    return Delayed


def fixed_delay(base, d):
    """``base`` after a fixed pause of exactly ``d`` steps. Unlike :func:`delayed` (random
    1..max), the delay is deterministic, so a sweep over ``d`` certifies how a defender's
    breach rate depends on how long the attacker waits -- a principled family rather than a
    single hand-picked pause."""

    class FixedDelayed(BaseAgent):
        def __init__(self):
            self.inner = base()
            self.wait = d
            self.initial = None

        def get_action(self, observation, action_space):
            if self.initial is None:
                self.initial = observation
            if self.wait > 0:
                self.wait -= 1
                return Sleep()
            if self.wait == 0:
                self.wait = -1
                return self.inner.get_action(self.initial, action_space)
            return self.inner.get_action(observation, action_space)

        def train(self, results):
            pass

        def end_episode(self):
            self.inner.end_episode()
            self.wait = d
            self.initial = None

        def set_initial_values(self, action_space, observation):
            pass

    FixedDelayed.__name__ = f"Delay{d}{base.__name__}"
    return FixedDelayed


def switching(first=RedMeanderAgent, then=B_lineAgent, switch_at=4):
    """``first`` for ``switch_at`` steps, then ``then`` from its own start."""

    class Switching(BaseAgent):
        def __init__(self):
            self.a, self.b, self.t, self.initial = first(), then(), 0, None

        def get_action(self, observation, action_space):
            self.t += 1
            if self.initial is None:
                self.initial = observation
            if self.t <= switch_at:
                return self.a.get_action(observation, action_space)
            if self.t == switch_at + 1:            # the second attacker starts from the initial view
                return self.b.get_action(self.initial, action_space)
            return self.b.get_action(observation, action_space)

        def train(self, results):
            pass

        def end_episode(self):
            self.a.end_episode()
            self.b.end_episode()
            self.t, self.initial = 0, None

        def set_initial_values(self, action_space, observation):
            pass

    Switching.__name__ = f"{first.__name__}Then{then.__name__}"
    return Switching


ATTACKERS = {
    "b_line": B_lineAgent,
    "meander": RedMeanderAgent,
    "delayed_b_line": delayed(B_lineAgent),
    "meander_then_b_line": switching(),
}
SEEN = ("b_line", "meander")            # the attackers the challenge (and its winner) trained on


class _Official:
    """Wraps an official scripted Blue agent (raw CybORG observations and actions)."""

    interface = "raw"

    def __init__(self, cls, name):
        self.cls, self.name = cls, name
        self.agent = cls()

    def get_action(self, observation, action_space):
        return self.agent.get_action(observation, action_space)

    def end_episode(self):
        self.agent = self.cls()


def sleep_defender():
    return _Official(SleepAgent, "sleep")


def react_remove():
    return _Official(BlueReactRemoveAgent, "react-remove")


def react_restore():
    return _Official(BlueReactRestoreAgent, "react-restore")

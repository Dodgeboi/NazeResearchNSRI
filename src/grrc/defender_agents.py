"""Autonomous defenders for grrc.agent_env: scripted responders and a learner.

Scripted responders stand for what automated response does today: a playbook
or SOAR rule that takes one network action when an alert fires and undoes it
once alerts clear. The learning defender is tabular Q-learning over a small
observation abstraction. It is deliberately simple: the question here is not
how capable a defender can be made, but what a defender learns from the
signal it is given, and what a shield changes about that.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .agent_env import (CONNECTED, LEARNING_ACTIONS, DefenderEnv,
                        Observation)

# ---------------------------------------------------------------- scripted


class Passive:
    """Never takes a network action; node-level isolation still runs."""

    name = "passive"

    def reset(self) -> None:
        pass

    def act(self, obs: Observation) -> str:
        return CONNECTED


@dataclass
class OnAlert:
    """Apply ``mode`` from the first detection until alerts stay clear.

    Released once no detected node has been left un-isolated for
    ``quiet_decisions`` consecutive decisions. Uses only what an operations
    centre can see.
    """

    mode: str
    quiet_decisions: int = 2
    name: str = ""
    _quiet: int = 0
    _engaged: bool = False

    def __post_init__(self) -> None:
        self.name = self.name or f"on_alert_{self.mode}"

    def reset(self) -> None:
        self._quiet, self._engaged = 0, False

    def act(self, obs: Observation) -> str:
        if obs.detections_total > 0 and not self._engaged:
            self._engaged, self._quiet = True, 0
        if self._engaged:
            self._quiet = self._quiet + 1 if obs.active_alerts == 0 else 0
            if self._quiet >= self.quiet_decisions:
                self._engaged = False
        return self.mode if self._engaged else CONNECTED


# ----------------------------------------------------------------- learner

_DETECTION_EDGES = (1, 3, 10)  # buckets: 0 | 1-2 | 3-9 | 10+


def encode(obs: Observation, actions: tuple[str, ...]) -> int:
    """Abstract an observation into one of 32 * |actions| discrete states."""
    det = int(np.searchsorted(_DETECTION_EDGES, obs.detections_total,
                              side="right"))
    mode = actions.index(obs.mode) if obs.mode in actions else 0
    bits = (int(obs.clinical_down) << 2 | int(obs.identity_down) << 1
            | int(obs.active_alerts > 0))
    return ((det * 8) + bits) * len(actions) + mode


@dataclass
class QLearner:
    """Tabular Q-learning with epsilon-greedy exploration.

    Trained on the environment's reward, which is one of ``containment``,
    ``soft`` or ``clinical`` (grrc.agent_env.DefenderEnv._reward). Ties are
    broken toward ``connected`` (index 0), so an untrained or indifferent
    state takes no network action.
    """

    actions: tuple[str, ...]
    alpha: float = 0.1
    gamma: float = 0.95
    epsilon: float = 0.0
    name: str = "q_learner"
    q: np.ndarray = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.q is None:
            self.q = np.zeros((32 * len(self.actions), len(self.actions)))

    def reset(self) -> None:
        pass

    def greedy(self, state: int) -> int:
        row = self.q[state]
        return int(np.flatnonzero(row == row.max())[0])

    def act_index(self, state: int, rng: np.random.Generator) -> int:
        if self.epsilon > 0 and rng.random() < self.epsilon:
            return int(rng.integers(len(self.actions)))
        return self.greedy(state)

    def act(self, obs: Observation) -> str:
        return self.actions[self.greedy(encode(obs, self.actions))]

    def update(self, s: int, a: int, r: float, s2: int, done: bool) -> None:
        target = r if done else r + self.gamma * self.q[s2].max()
        self.q[s, a] += self.alpha * (target - self.q[s, a])

    # ------------------------------------------------------------- storage
    def save(self, path: Path, meta: dict) -> None:
        path.write_text(json.dumps({
            "actions": list(self.actions), "alpha": self.alpha,
            "gamma": self.gamma, "name": self.name, "meta": meta,
            "q": self.q.tolist()}, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "QLearner":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(actions=tuple(data["actions"]), alpha=data["alpha"],
                   gamma=data["gamma"], name=data["name"],
                   q=np.array(data["q"], dtype=float))


def train(agent: QLearner, make_env, episodes: int, seed: int,
          eps_start: float = 1.0, eps_end: float = 0.05,
          log_every: int = 0) -> list[float]:
    """Train ``agent`` on ``episodes`` environments from ``make_env(i)``.

    Epsilon decays linearly across training. Returns per-episode returns.
    """
    rng = np.random.default_rng(seed)
    returns = []
    for i in range(episodes):
        agent.epsilon = eps_start + (eps_end - eps_start) * i / max(1, episodes - 1)
        env: DefenderEnv = make_env(i)
        obs = env.reset()
        s = encode(obs, agent.actions)
        total, done = 0.0, False
        while not done:
            a = agent.act_index(s, rng)
            obs, r, done = env.step(agent.actions[a])
            s2 = encode(obs, agent.actions)
            agent.update(s, a, r, s2, done)
            s, total = s2, total + r
        returns.append(total)
        if log_every and (i + 1) % log_every == 0:
            recent = float(np.mean(returns[-log_every:]))
            print(f"  episode {i + 1}/{episodes} eps={agent.epsilon:.2f} "
                  f"mean return {recent:.2f}", flush=True)
    agent.epsilon = 0.0
    return returns


def run_episode(agent, env: DefenderEnv) -> dict:
    """Roll out one evaluation episode and return the extended metric row."""
    agent.reset()
    obs, done = env.reset(), False
    while not done:
        obs, _, done = env.step(agent.act(obs))
    return env.finish()


def learning_actions(architecture: str) -> tuple[str, ...]:
    return LEARNING_ACTIONS[architecture]

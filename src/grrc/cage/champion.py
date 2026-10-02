"""The CAGE Challenge 2 winning defender, ported to NumPy.

A faithful port of the Cardiff University agent (J. Hannay, MIT licence;
``vendor/cage/cardiff``): a PPO policy per known attacker plus greedy decoys. It plays
three fixed opening decoys, *fingerprints* the attacker from the scans it has seen
(two scans: B_line; three: Meander; otherwise it sleeps), then runs the policy trained
against that attacker. Only the torch calls are replaced: the actor network is a
3-layer MLP evaluated in NumPy from the original checkpoints, deterministic actions
take the arg-max, and "next best" actions sort the probabilities. The control flow,
decoy book-keeping and action tables are copied from ``Agents/PPOAgent.py`` and
``Agents/MainAgent.py`` at the pinned commit. Observations come from the agent's own
``Wrappers/ChallengeWrapper2``.
"""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np

from grrc.cage.torchless import load_state_dict

ROOT = Path(__file__).resolve().parents[3]
CARDIFF = ROOT / "vendor/cage/cardiff"
ACTION_SPACE = [133, 134, 135, 139, 3, 4, 5, 9, 16, 17, 18, 22, 11, 12, 13, 14, 141, 142, 143,
                144, 132, 2, 15, 24, 25, 26, 27]
GREEDY_DECOYS = {1000: [55, 107, 120, 29], 1001: [43], 1002: [44], 1003: [37, 115, 76, 102],
                 1004: [51, 116, 38, 90], 1005: [130, 91], 1006: [131],
                 1007: [54, 106, 28, 119], 1008: [61, 35, 113, 126]}
DECOY_IDS = list(range(1000, 1009))
_BASE = [28, 41, 54, 67, 80, 93, 106, 119]
RESTORE_DECOY_MAPPING = {132 + i: [x + i for x in _BASE] for i in range(13)}


class _Actor:
    """``actor`` of the original ActorCritic: Linear-ReLU-Linear-ReLU-Linear-Softmax."""

    def __init__(self, state_dict):
        self.w = [state_dict[f"actor.{i}.weight"].astype(np.float64) for i in (0, 2, 4)]
        self.b = [state_dict[f"actor.{i}.bias"].astype(np.float64) for i in (0, 2, 4)]

    def probs(self, x):
        h = np.maximum(self.w[0] @ x + self.b[0], 0)
        h = np.maximum(self.w[1] @ h + self.b[1], 0)
        z = self.w[2] @ h + self.b[2]
        z = np.exp(z - z.max())
        return z / z.sum()


class PPOAgent:
    """NumPy port of ``Agents/PPOAgent.py`` in evaluation mode (deterministic, no training)."""

    def __init__(self, ckpt):
        self.actor = _Actor(load_state_dict(ckpt))
        self.action_space = ACTION_SPACE + DECOY_IDS
        self.end_episode()

    def end_episode(self):
        self.current_decoys = {h: [] for h in DECOY_IDS}
        self.scan_state = np.zeros(10)

    def add_decoy(self, id_, host):
        if id_ not in self.current_decoys[host]:
            self.current_decoys[host].append(id_)

    def remove_decoy(self, id_, host):
        if id_ in self.current_decoys[host]:
            self.current_decoys[host].remove(id_)

    def add_scan(self, observation):
        for i, index in enumerate([0, 4, 8, 12, 28, 32, 36, 40, 44, 48]):
            if observation[index] == 1 and observation[index + 1] == 0:
                self.scan_state = [1 if x == 2 else x for x in self.scan_state]
                self.scan_state[i] = 2
                break

    def get_action(self, observation, action_space=None):
        self.add_scan(observation)
        state = np.concatenate((observation, self.scan_state)).astype(np.float64)
        action_ = self.action_space[int(np.argmax(self.actor.probs(state)))]
        if action_ in DECOY_IDS:
            action_ = self.select_decoy(action_, state)
        if action_ in RESTORE_DECOY_MAPPING:
            for decoy in RESTORE_DECOY_MAPPING[action_]:
                for host in DECOY_IDS:
                    if decoy in self.current_decoys[host]:
                        self.remove_decoy(decoy, host)
        return action_

    def select_decoy(self, host, state):
        free = [a for a in GREEDY_DECOYS[host] if a not in self.current_decoys[host]]
        if free:
            self.add_decoy(free[0], host)
            return free[0]
        # Deterministic evaluation policy: next best action, skipping full decoys and restores.
        order = np.argsort(-self.actor.probs(state), kind="stable")
        action = None
        for idx in order:
            a = self.action_space[int(idx)]
            if a in self.current_decoys:
                if len(self.current_decoys[a]) < len(GREEDY_DECOYS[a]):
                    action = self.select_decoy(a, state)
                    self.add_decoy(action, a)
                    break
            elif a not in RESTORE_DECOY_MAPPING:
                action = a
                break
        return action


class ChampionAgent:
    """NumPy port of ``Agents/MainAgent.py``: opening decoys, fingerprint, then PPO."""

    name = "champion-ppo"

    def __init__(self, cardiff_dir=CARDIFF):
        self.ckpt = {"bline": Path(cardiff_dir) / "Models/bline/model.pth",
                     "meander": Path(cardiff_dir) / "Models/meander/model.pth"}
        self.end_episode()

    def end_episode(self):
        self.scan_state = np.zeros(10)
        self.start_actions = [51, 116, 55]
        self.agent_loaded = False
        self.agent = None
        self.loaded = None

    add_scan = PPOAgent.add_scan

    def get_action(self, observation, action_space=None):
        action = None
        old_scan_state = copy.copy(self.scan_state)
        self.add_scan(observation)
        if self.start_actions:
            action = self.start_actions.pop(0)
        elif not self.agent_loaded:
            total = np.sum(self.scan_state)
            if total == 3:
                self.agent, self.loaded = PPOAgent(self.ckpt["meander"]), "meander"
            elif total == 2:
                self.agent, self.loaded = PPOAgent(self.ckpt["bline"]), "bline"
            else:
                self.agent, self.loaded = None, "sleep"
            self.agent_loaded = True
            if self.agent is not None:
                self.agent.current_decoys = {1000: [55], 1001: [], 1002: [], 1003: [],
                                             1004: [51, 116], 1005: [], 1006: [], 1007: [],
                                             1008: []}
                self.agent.scan_state = old_scan_state
        if action is None:
            action = 0 if self.agent is None else self.agent.get_action(observation)
        return action

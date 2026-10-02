#!/usr/bin/env python3
"""Check the NumPy port of the CAGE-2 winner against its published evaluation (run in
.venv-cage). Mirrors the authors' ``evaluation.py``: ``random.seed(0)`` once, then 1,000
sequential 30-step episodes per attacker. Writes ``data/cage/champion_validation.csv``
next to the published means and standard deviations from the authors' README."""
from __future__ import annotations

import random
import statistics as st
from pathlib import Path

import pandas as pd

from grrc.cage.agents import ATTACKERS
from grrc.cage.champion import ChampionAgent
from grrc.cage.env import run_episode
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = {"b_line": (-3.4108, 1.7702), "meander": (-5.539, 1.2889)}   # README, 30 steps
EPISODES, STEPS = 1000, 30


def main():
    rows = []
    for name, (mean, sd) in PUBLISHED.items():
        random.seed(0)
        agent = ChampionAgent()
        rewards = [run_episode(agent, ATTACKERS[name], STEPS, reseed=False)[0]["reward"]
                   for _ in range(EPISODES)]
        m, s = st.mean(rewards), st.stdev(rewards)
        rows.append(dict(attacker=name, episodes=EPISODES, steps=STEPS, port_mean=m, port_sd=s,
                         port_se=s / EPISODES ** 0.5, published_mean=mean, published_sd=sd,
                         difference=m - mean))
        print(rows[-1], flush=True)
    write_csv(pd.DataFrame(rows), ROOT / "data/cage/champion_validation.csv")


if __name__ == "__main__":
    main()

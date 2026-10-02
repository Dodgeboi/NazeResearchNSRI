#!/usr/bin/env python3
"""Certified evaluation of non-LLM defenders in CAGE Challenge 2 (run in .venv-cage).

Every defender plays ``--episodes`` seeded episodes of ``--steps`` steps against each
fixed attacker (two official, two unseen re-sequencings) and against an adaptive
attacker that picks among them by EXP3 across episodes. Writes one row per episode to
``data/cage/episodes.csv`` and a provenance manifest. Deterministic given the seeds.

    .venv-cage/bin/python scripts/run_cage_eval.py
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from grrc.cage.adaptive import Exp3
from grrc.cage.agents import ATTACKERS, react_remove, react_restore, sleep_defender
from grrc.cage.champion import ChampionAgent
from grrc.cage.env import run_episode
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/cage"
STEP_BOUND = -15.8          # worst reward per step in Scenario 2 (see the design note)
DEFENDERS = {
    "sleep": sleep_defender,
    "react-remove": react_remove,
    "react-restore": react_restore,
    "champion": lambda: ChampionAgent(fallback="sleep"),
    "champion+fallback": lambda: ChampionAgent(fallback="bline"),
}
SEED0 = 20261002


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=200)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for d_name, make in DEFENDERS.items():
        t0 = time.time()
        for a_name, red in ATTACKERS.items():
            defender = make()
            for i in range(args.episodes):
                out, _ = run_episode(defender, red, args.steps, seed=SEED0 + i)
                rows.append(dict(defender=d_name, attacker=a_name, adaptive=False,
                                 episode=i, seed=SEED0 + i, strategy=a_name, **_keep(out)))
        bandit = Exp3(list(ATTACKERS), horizon=args.episodes, seed=SEED0)
        defender = make()
        for i in range(args.episodes):
            a_name = bandit.choose()
            out, _ = run_episode(defender, ATTACKERS[a_name], args.steps, seed=SEED0 + 10_000 + i)
            bandit.update(min(1.0, out["reward"] / (STEP_BOUND * args.steps)))
            rows.append(dict(defender=d_name, attacker="adaptive", adaptive=True, episode=i,
                             seed=SEED0 + 10_000 + i, strategy=a_name, **_keep(out)))
        print(f"{d_name}: {time.time() - t0:.0f}s", flush=True)
    path = OUT / "episodes.csv"
    write_csv(pd.DataFrame(rows), path)
    inputs = [Path(__file__)] + [ROOT / f"src/grrc/cage/{m}.py" for m in
                                 ("adaptive", "agents", "champion", "env", "torchless")] + [
        ROOT / "requirements-cage.txt", ROOT / "scripts/setup_cage.sh",
        ROOT / "src/grrc/provenance.py", ROOT / "src/grrc/utilities.py"]
    manifest = build_manifest(
        run_id="cage-eval", stage="analysis",
        description="CAGE Challenge 2 episodes for non-LLM defenders against fixed, unseen and "
                    "adaptive attackers (inputs for the certified evaluation).",
        inputs=inputs, outputs=[path], source_state=state,
        parameters=dict(episodes=args.episodes, steps=args.steps, seed0=SEED0,
                        step_bound=STEP_BOUND, defenders=list(DEFENDERS),
                        attackers=list(ATTACKERS) + ["adaptive"],
                        cage2_commit="26ce1c1253fa9e2e73f25e6a7f2da32860c11257",
                        champion_commit="ddbf3e55d17484b1bdd62b02daff72b7774330df"))
    write_manifest(manifest, OUT / "cage_eval_manifest.json")


def _keep(out):
    return {k: out[k] for k in ("reward", "impacts", "steps", "impact_fraction", "breached")}


if __name__ == "__main__":
    main()

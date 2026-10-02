#!/usr/bin/env python3
r"""Certified evaluation on a *second* environment: CAGE Challenge 1 (CybORG Scenario1b),
run in .venv-cage.

The main study is CAGE Challenge 2 (Scenario2). To show the certified-evaluation protocol is
not specific to that scenario, this runner replays it on Scenario1b -- the earlier CAGE
Challenge 1 network -- for the generic reference defenders (the challenge winner's policy is
specific to Scenario2's topology, so it is not evaluated here) against the same fixed, unseen
and adaptive attackers. Writes one row per episode to ``data/cage/env1b/episodes.csv`` and a
provenance manifest. Deterministic given the seeds.

    .venv-cage/bin/python scripts/run_cage_env1b.py
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from grrc.cage.adaptive import Exp3
from grrc.cage.agents import ATTACKERS, react_remove, react_restore, sleep_defender
from grrc.cage.env import run_episode
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/cage/env1b"
SCENARIO = "Scenario1b"
STEP_BOUND = -15.8
DEFENDERS = {
    "sleep": sleep_defender,
    "react-remove": react_remove,
    "react-restore": react_restore,
}
SEED0 = 20261002


def _keep(out):
    return {k: out[k] for k in ("reward", "impacts", "steps", "impact_fraction", "breached")}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
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
                out, _ = run_episode(defender, red, args.steps, seed=SEED0 + i, scenario=SCENARIO)
                rows.append(dict(defender=d_name, attacker=a_name, adaptive=False,
                                 episode=i, seed=SEED0 + i, strategy=a_name, **_keep(out)))
        bandit = Exp3(list(ATTACKERS), horizon=args.episodes, seed=SEED0)
        defender = make()
        for i in range(args.episodes):
            a_name = bandit.choose()
            out, _ = run_episode(defender, ATTACKERS[a_name], args.steps,
                                 seed=SEED0 + 10_000 + i, scenario=SCENARIO)
            bandit.update(min(1.0, out["reward"] / (STEP_BOUND * args.steps)))
            rows.append(dict(defender=d_name, attacker="adaptive", adaptive=True, episode=i,
                             seed=SEED0 + 10_000 + i, strategy=a_name, **_keep(out)))
        print(f"{d_name}: {time.time() - t0:.0f}s", flush=True)
    path = OUT / "episodes.csv"
    write_csv(pd.DataFrame(rows), path)
    inputs = [Path(__file__)] + [ROOT / f"src/grrc/cage/{m}.py" for m in
                                 ("adaptive", "agents", "env")] + [
        ROOT / "requirements-cage.txt", ROOT / "scripts/setup_cage.sh",
        ROOT / "src/grrc/provenance.py", ROOT / "src/grrc/utilities.py"]
    manifest = build_manifest(
        run_id="cage-env1b", stage="analysis",
        description="CAGE Challenge 1 (Scenario1b) episodes for the generic reference defenders "
                    "against fixed, unseen and adaptive attackers -- a second environment for the "
                    "certified-evaluation protocol.",
        inputs=inputs, outputs=[path], source_state=state,
        parameters=dict(episodes=args.episodes, steps=args.steps, seed0=SEED0, scenario=SCENARIO,
                        step_bound=STEP_BOUND, defenders=list(DEFENDERS),
                        attackers=list(ATTACKERS) + ["adaptive"],
                        cage2_commit="26ce1c1253fa9e2e73f25e6a7f2da32860c11257"))
    write_manifest(manifest, OUT / "cage_env1b_manifest.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
r"""Certify the CAGE-2 winner's blind spot, and its one-line repair, across a *parameterized
family* of unseen attackers rather than a single hand-picked pause (run in .venv-cage).

The headline result evaluates the challenge winner against a delayed B\_line that waits a
random 1..5 steps. A reviewer may fairly ask whether the finding rests on that particular
choice. This runner sweeps a deterministic delay ``d = 1..D`` (and a delayed Meander) against
the winner, the one-line-repaired winner and React-restore, so the blind spot and the repair
can be certified across the whole family. Writes one row per episode to
``data/cage/family.csv`` and a provenance manifest. Deterministic given the seeds; the seeds
are paired with the main study.

    .venv-cage/bin/python scripts/run_cage_family.py            # d = 1..10, 100 episodes each
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from grrc.cage.agents import fixed_delay
from grrc.cage.champion import ChampionAgent
from grrc.cage.env import run_episode
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

from CybORG.Agents import B_lineAgent, RedMeanderAgent

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/cage"
SEED0 = 20261002            # same episode seeds as scripts/run_cage_eval.py
DEFENDERS = {
    "champion": lambda: ChampionAgent(fallback="sleep"),
    "champion+fallback": lambda: ChampionAgent(fallback="bline"),
    "react-restore": None,     # filled below (import kept local to the CybORG venv)
}


def _defenders():
    from grrc.cage.agents import react_restore
    d = dict(DEFENDERS)
    d["react-restore"] = react_restore
    return d


def _keep(out):
    return {k: out[k] for k in ("reward", "impacts", "steps", "impact_fraction", "breached")}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--max-delay", type=int, default=10)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    OUT.mkdir(parents=True, exist_ok=True)

    # The attacker family: a B_line that waits exactly d steps (d = 1..max_delay), plus a
    # delayed Meander, to ask whether the delay also fools the winner against the explorer.
    family = {f"delay{d}_b_line": fixed_delay(B_lineAgent, d) for d in range(1, args.max_delay + 1)}
    family["delay3_meander"] = fixed_delay(RedMeanderAgent, 3)

    rows = []
    for d_name, make in _defenders().items():
        t0 = time.time()
        for a_name, red in family.items():
            defender = make()
            for i in range(args.episodes):
                out, _ = run_episode(defender, red, args.steps, seed=SEED0 + i)
                rows.append(dict(defender=d_name, attacker=a_name, episode=i, seed=SEED0 + i,
                                 **_keep(out)))
        print(f"{d_name}: {time.time() - t0:.0f}s", flush=True)

    path = OUT / "family.csv"
    write_csv(pd.DataFrame(rows), path)
    inputs = [Path(__file__)] + [ROOT / f"src/grrc/cage/{m}.py" for m in
                                 ("agents", "champion", "env", "torchless")] + [
        ROOT / "requirements-cage.txt", ROOT / "scripts/setup_cage.sh",
        ROOT / "src/grrc/provenance.py", ROOT / "src/grrc/utilities.py"]
    manifest = build_manifest(
        run_id="cage-family", stage="analysis",
        description="CAGE Challenge 2 episodes sweeping a fixed-delay attacker family against "
                    "the winner, the repaired winner and React-restore (robustness of the "
                    "blind spot and its repair).",
        inputs=inputs, outputs=[path], source_state=state,
        parameters=dict(episodes=args.episodes, steps=args.steps, seed0=SEED0,
                        max_delay=args.max_delay, defenders=list(DEFENDERS),
                        attackers=list(family),
                        cage2_commit="26ce1c1253fa9e2e73f25e6a7f2da32860c11257",
                        champion_commit="ddbf3e55d17484b1bdd62b02daff72b7774330df"))
    write_manifest(manifest, OUT / "cage_family_manifest.json")


if __name__ == "__main__":
    main()

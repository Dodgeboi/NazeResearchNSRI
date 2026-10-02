#!/usr/bin/env python3
r"""Primitive-action language-model attacker in CAGE Challenge 2 (run in .venv-cage).

Unlike scripts/run_cage_attacker.py (which lets the model pick one of four ready-made attack
strategies per episode), here the model issues CybORG's own Red actions one per step and must
find the exploitation path itself (see :mod:`grrc.cage.llm_primitive_attacker`). The question:
can a language model *operate* -- scan, exploit, escalate, pivot and Impact the operational
server -- and does it find the winner's timing weakness that the strategy-selector did?

    MAX_THINKING_TOKENS=0 .venv-cage/bin/python scripts/run_cage_primitive_attacker.py \\
        --model claude-haiku-4-5 --episodes 15 --budget-usd 8

Writes ``data/cage/primitive_attacker/<model>/<defender>.jsonl`` (per episode: breach, reward,
impacts, invalid-action count, cost, and the action trace). Resumable; a shared budget stops
new episodes once the recorded spend reaches ``--budget-usd``. Each episode is independent
(the attacker holds no cross-episode state), so unlike the strategy selector no replay is needed.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/cage/primitive_attacker"
SEED0 = 20261002
STEPS = 30
DEFENDERS = ("sleep", "champion", "champion+fallback", "react-restore")


def _slug(model):
    return model.replace("/", "_").replace(":", "_")


def _spent(folder):
    total = 0.0
    for f in folder.glob("*.jsonl"):
        for line in f.read_text().splitlines():
            total += json.loads(line).get("cost_usd") or 0.0
    return total


def _make_defender(name):
    from grrc.cage.agents import react_restore, sleep_defender
    from grrc.cage.champion import ChampionAgent
    if name == "sleep":
        return sleep_defender
    if name == "champion":
        return lambda: ChampionAgent(fallback="sleep")
    if name == "champion+fallback":
        return lambda: ChampionAgent(fallback="bline")
    if name == "react-restore":
        return react_restore
    raise ValueError(name)


def _worker(args):
    model, defender_name, episodes, budget = args
    from grrc.cage.attacker_env import run_defender_vs_red
    from grrc.cage.llm_primitive_attacker import SYSTEM_PROMPT, PrimitiveAttacker
    from grrc.range.llm_agent import ClaudeCLIAgent
    folder = OUT / _slug(model)
    path = folder / f"{defender_name}.jsonl"
    done = {json.loads(line)["episode"] for line in path.read_text().splitlines()} if path.exists() else set()
    make_defender = _make_defender(defender_name)
    for i in range(episodes):
        if i in done:
            continue
        if budget is not None and _spent(folder) >= budget:
            print(f"{defender_name}: budget reached before episode {i}", flush=True)
            return
        backend = ClaudeCLIAgent(model, system_prompt=SYSTEM_PROMPT, max_call_usd=0.05)
        atk = PrimitiveAttacker(backend)
        out, trace = run_defender_vs_red(make_defender(), atk, STEPS, seed=SEED0 + i)
        rec = dict(model=model, defender=defender_name, episode=i, seed=SEED0 + i,
                   breached=out["breached"], reward=out["reward"], impacts=out["impacts"],
                   invalid=atk.invalid, cost_usd=round(atk.cost, 6),
                   actions=[s["red"].split()[0] for s in trace])
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"{defender_name} ep{i}: breached {out['breached']} impacts {out['impacts']} "
              f"invalid {atk.invalid} (spent ${_spent(folder):.2f})", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--episodes", type=int, default=15)
    parser.add_argument("--budget-usd", type=float, default=8.0)
    parser.add_argument("--defenders", nargs="*", default=list(DEFENDERS))
    args = parser.parse_args()
    (OUT / _slug(args.model)).mkdir(parents=True, exist_ok=True)
    jobs = [(args.model, d, args.episodes, args.budget_usd) for d in args.defenders]
    with mp.get_context("spawn").Pool(len(jobs)) as pool:
        pool.map(_worker, jobs)
    print(f"total spent: ${_spent(OUT / _slug(args.model)):.2f}")


if __name__ == "__main__":
    main()

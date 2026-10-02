#!/usr/bin/env python3
"""Language-model defenders in CAGE Challenge 2 (run in .venv-cage).

Plays ``--episodes`` seeded episodes against each fixed attacker with the same seeds as
``scripts/run_cage_eval.py`` (so every comparison with the non-LLM defenders is paired
episode by episode), one worker process per attacker. Each episode is appended to
``data/cage/llm/<model>/<attacker>.jsonl`` with its outcomes, cost and every reply, so
the run is resumable. A shared budget stops new episodes once the total spend recorded
across all files reaches ``--budget-usd``.

    .venv-cage/bin/python scripts/run_cage_llm.py --agent claude --model claude-haiku-4-5 \\
        --episodes 20 --budget-usd 9
    .venv-cage/bin/python scripts/run_cage_llm.py --agent ollama --model qwen2.5:7b --episodes 20
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/cage/llm"
SEED0 = 20261002            # identical to scripts/run_cage_eval.py
STEPS = 30


def _slug(model):
    return model.replace("/", "_").replace(":", "_")


def _spent(folder):
    total = 0.0
    for f in folder.glob("*.jsonl"):
        for line in f.read_text().splitlines():
            total += json.loads(line).get("cost_usd") or 0.0
    return total


def _worker(args):
    agent_kind, model, attacker, episodes, budget, host = args
    from grrc.cage.agents import ATTACKERS
    from grrc.cage.env import run_episode
    from grrc.cage.llm_defender import SYSTEM_PROMPT, LLMDefender
    from grrc.range.llm_agent import ClaudeCLIAgent, OllamaAgent
    folder = OUT / _slug(model)
    path = folder / f"{attacker}.jsonl"
    done = {json.loads(line)["episode"] for line in path.read_text().splitlines()} if path.exists() else set()
    for i in range(episodes):
        if i in done:
            continue
        if budget is not None and _spent(folder) >= budget:
            print(f"{attacker}: budget reached before episode {i}", flush=True)
            return
        if agent_kind == "claude":
            llm = ClaudeCLIAgent(model, system_prompt=SYSTEM_PROMPT, max_call_usd=0.10)
        else:
            llm = OllamaAgent(model, host=host, temperature=0.7, seed=i, num_ctx=8192)
        defender = LLMDefender(llm, model)
        t0 = time.time()
        out, trace = run_episode(defender, ATTACKERS[attacker], STEPS, seed=SEED0 + i)
        rec = dict(model=model, agent=agent_kind, attacker=attacker, episode=i, seed=SEED0 + i,
                   seconds=round(time.time() - t0, 1), **out,
                   replies=defender.log, trace=trace)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"{attacker} ep{i}: reward {out['reward']:.1f} breached {out['breached']} "
              f"invalid {out['invalid']} cost ${out['cost_usd']:.3f} ({rec['seconds']}s)", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", choices=("claude", "ollama"), default="claude")
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--budget-usd", type=float, default=None,
                        help="Claude only: stop starting episodes once this much is spent")
    parser.add_argument("--attackers", nargs="*", default=None)
    parser.add_argument("--host", default="http://localhost:11434")
    args = parser.parse_args()
    from grrc.cage.agents import ATTACKERS
    attackers = args.attackers or list(ATTACKERS)
    (OUT / _slug(args.model)).mkdir(parents=True, exist_ok=True)
    budget = args.budget_usd if args.agent == "claude" else None
    jobs = [(args.agent, args.model, a, args.episodes, budget, args.host) for a in attackers]
    with mp.get_context("spawn").Pool(len(jobs)) as pool:
        pool.map(_worker, jobs)
    print(f"total spent: ${_spent(OUT / _slug(args.model)):.2f}")


if __name__ == "__main__":
    main()

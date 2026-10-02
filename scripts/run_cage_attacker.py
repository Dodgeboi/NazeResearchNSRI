#!/usr/bin/env python3
"""Language-model adaptive attacker in CAGE Challenge 2 (run in .venv-cage).

For each fixed defender, a language model runs a sequence of attack episodes, choosing one
attack strategy per episode and adapting to the breaches it achieves (see
:mod:`grrc.cage.llm_attacker`). The question: does the model discover, on its own, that
the challenge winner is blind to a delayed start -- the weakness the scripted EXP3
adversary found? Each episode's chosen strategy runs through the same
:func:`grrc.cage.env.run_episode` as every other result, on seeds paired with the rest of
the study.

    .venv-cage/bin/python scripts/run_cage_attacker.py --agent claude --model claude-haiku-4-5 \\
        --episodes 40 --budget-usd 6

Writes ``data/cage/attacker/<model>/<defender>.jsonl`` (per episode: chosen strategy,
breach, reward, the model's reply, running cost) and a run record. Resumable; a shared
budget stops new episodes once the recorded spend reaches ``--budget-usd``.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/cage/attacker"
SEED0 = 20261002            # same episode seeds as scripts/run_cage_eval.py
STEPS = 30
DEFENDERS = ("champion", "champion+fallback", "react-restore")


def _slug(model):
    return model.replace("/", "_").replace(":", "_")


def _spent(folder):
    total = 0.0
    for f in folder.glob("*.jsonl"):
        for line in f.read_text().splitlines():
            total += json.loads(line).get("cost_usd") or 0.0
    return total


def _make_defender(name):
    from grrc.cage.agents import react_restore
    from grrc.cage.champion import ChampionAgent
    if name == "champion":
        return lambda: ChampionAgent(fallback="sleep")
    if name == "champion+fallback":
        return lambda: ChampionAgent(fallback="bline")
    if name == "react-restore":
        return react_restore
    raise ValueError(name)


def _worker(args):
    agent_kind, model, defender_name, episodes, budget, host = args
    from grrc.cage.agents import ATTACKERS
    from grrc.cage.env import run_episode
    from grrc.cage.llm_attacker import SYSTEM_PROMPT, SelectorAgent
    from grrc.range.llm_agent import ClaudeCLIAgent, OllamaAgent
    folder = OUT / _slug(model)
    path = folder / f"{defender_name}.jsonl"
    done = {json.loads(line)["episode"] for line in path.read_text().splitlines()} if path.exists() else set()
    make_defender = _make_defender(defender_name)
    if agent_kind == "claude":
        backend = ClaudeCLIAgent(model, system_prompt=SYSTEM_PROMPT, max_call_usd=0.05)
    else:
        backend = OllamaAgent(model, host=host, num_ctx=4096)
    selector = SelectorAgent(backend, seed=SEED0)
    # Replay prior episodes so the selector's adaptation state is consistent on resume.
    prior = sorted((json.loads(line) for line in path.read_text().splitlines()),
                   key=lambda r: r["episode"]) if path.exists() else []
    for rec in prior:
        selector.record(rec["strategy"], rec["breached"], rec["reward"])
    for i in range(episodes):
        if i in done:
            continue
        if budget is not None and _spent(folder) >= budget:
            print(f"{defender_name}: budget reached before episode {i}", flush=True)
            return
        before = selector.cost
        strategy, reply = selector.choose()
        out, _ = run_episode(make_defender(), ATTACKERS[strategy], STEPS, seed=SEED0 + i)
        selector.record(strategy, out["breached"], out["reward"])
        rec = dict(model=model, agent=agent_kind, defender=defender_name, episode=i,
                   seed=SEED0 + i, strategy=strategy, reply=reply,
                   cost_usd=round(selector.cost - before, 6), breached=out["breached"],
                   reward=out["reward"], impacts=out["impacts"])
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"{defender_name} ep{i}: {strategy} -> breached {out['breached']} "
              f"reward {out['reward']:.1f} (spent ${_spent(folder):.2f})", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", choices=("claude", "ollama"), default="claude")
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--episodes", type=int, default=40)
    parser.add_argument("--budget-usd", type=float, default=None)
    parser.add_argument("--defenders", nargs="*", default=list(DEFENDERS))
    parser.add_argument("--host", default="http://localhost:11434")
    args = parser.parse_args()
    (OUT / _slug(args.model)).mkdir(parents=True, exist_ok=True)
    budget = args.budget_usd if args.agent == "claude" else None
    jobs = [(args.agent, args.model, d, args.episodes, budget, args.host) for d in args.defenders]
    with mp.get_context("spawn").Pool(len(jobs)) as pool:
        pool.map(_worker, jobs)
    print(f"total spent: ${_spent(OUT / _slug(args.model)):.2f}")


if __name__ == "__main__":
    main()

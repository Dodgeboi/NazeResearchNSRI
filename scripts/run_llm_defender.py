#!/usr/bin/env python3
"""Evaluate a local language-model defender in the certified cyber range (free, offline).

Runs a model served by Ollama (https://ollama.com) on the user's own machine through
the range's agent-agnostic API, on a fixed, pre-declared set of regimes, and scores it
with the same certificate as the reference defenders. Nothing is sent anywhere except
to the local Ollama server.

    python scripts/run_llm_defender.py --dry-run                 # seconds, no Ollama
    python scripts/run_llm_defender.py --model qwen2.5:7b        # the evaluation
    python scripts/run_llm_defender.py --model qwen2.5:7b --quick

Outputs go to ``data/llm_defender/<model>/``: ``episodes.jsonl`` (one line per episode
with the full transcript), ``summary.csv`` (one row per episode, joined to the reference
defenders' costs) and ``run_record.json`` (versions, hashes, options). The run is
resumable: episodes already in ``episodes.jsonl`` are skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import pandas as pd

from grrc.attack_graph import build_graph, load_bundle
from grrc.hospital_attack_model import build_model
from grrc.range import DefenseRange, default_regimes
from grrc.range.llm_agent import (SYSTEM_PROMPT, OllamaAgent, ScriptedAgent, ollama_metadata,
                                  run_episode)
from grrc.range.policies import greedy_order

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
GAP = ROOT / "data/defense_range/optimality_gap.csv"
OUT = ROOT / "data/llm_defender"
# Pre-declared before any LLM result existed (2026-09-24). Typical regimes span easy to
# hard; the adaptive ones mix one certifiable regime (exact optimum 4, greedy 26) with
# regimes no portfolio can certify, to test whether the agent recognises impossibility.
REGIMES = [("typical", 0.10, 1), ("typical", 0.05, 1), ("typical", 0.05, 2),
           ("typical", 0.01, 4), ("adaptive", 0.10, 3), ("adaptive", 0.10, 2),
           ("adaptive", 0.05, 3), ("adaptive", 0.05, 1)]
QUICK = [("typical", 0.05, 1), ("typical", 0.01, 4), ("adaptive", 0.10, 3), ("adaptive", 0.05, 1)]
SEEDS = (1, 2, 3)
TEMPERATURE = 0.7
MAX_STEPS = 30
NUM_CTX = 16384


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _slug(model):
    return model.replace("/", "_").replace(":", "_")


def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model tag")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--quick", action="store_true", help="4 regimes x 1 seed")
    parser.add_argument("--dry-run", action="store_true",
                        help="replay the reference greedy defender instead of an LLM")
    args = parser.parse_args()

    regimes_wanted = QUICK if args.quick else REGIMES
    seeds = SEEDS[:1] if (args.quick or args.dry_run) else SEEDS
    name = "dry-run-greedy" if args.dry_run else args.model
    out = OUT / _slug(name)
    out.mkdir(parents=True, exist_ok=True)
    episodes_path = out / "episodes.jsonl"

    meta = None
    if not args.dry_run:
        try:
            meta = ollama_metadata(args.model, host=args.host)
        except OSError as exc:
            raise SystemExit(f"Cannot reach Ollama at {args.host} ({exc}). Start it with "
                             f"'ollama serve' and pull the model with 'ollama pull {args.model}'.")

    print("building the range (ATT&CK v17.1)...", flush=True)
    model = build_model(build_graph(load_bundle(BUNDLE)))
    by_label = {r.label: r for r in default_regimes(model)}
    done = set()
    if episodes_path.exists():
        for line in episodes_path.read_text().splitlines():
            rec = json.loads(line)
            done.add((rec["regime"], rec["seed"]))

    total = len(regimes_wanted) * len(seeds)
    n = 0
    for adversary, eps, k in regimes_wanted:
        label = f"{adversary}|assumed|eps={eps:.2f}|k={k}"
        for seed in seeds:
            n += 1
            if (label, seed) in done:
                print(f"[{n}/{total}] {label} seed={seed}: already done", flush=True)
                continue
            env = DefenseRange(model, by_label[label])
            if args.dry_run:
                agent = ScriptedAgent([env.graph.mitigations[i] for i in greedy_order(env)])
            else:
                agent = OllamaAgent(args.model, host=args.host, temperature=TEMPERATURE, seed=seed,
                                    num_ctx=NUM_CTX)
            metrics, traj = run_episode(env, agent, max_steps=MAX_STEPS)
            rec = dict(regime=label, adversary=adversary, epsilon=eps, k=k, seed=seed,
                       model=name, **metrics, transcript=traj)
            with episodes_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"[{n}/{total}] {label} seed={seed}: {metrics['stop_reason']}, "
                  f"cost={metrics['cost_to_certify']}, steps={metrics['steps']}, "
                  f"invalid={metrics['invalid_actions']}", flush=True)

    # Summary joined to the reference defenders (committed benchmark).
    rows = [json.loads(line) for line in episodes_path.read_text().splitlines()]
    gap = pd.read_csv(GAP)
    gap = gap[gap.degradation_source == "assumed"]
    summary = []
    for r in rows:
        ref = gap[(gap.adversary == r["adversary"]) & (gap.epsilon == r["epsilon"])
                  & (gap.k == r["k"])].iloc[0]
        summary.append({key: r[key] for key in (
            "model", "regime", "adversary", "epsilon", "k", "seed", "certified",
            "cost_to_certify", "steps", "invalid_actions", "stop_reason", "final_cost",
            "final_cat_worst", "prompt_tokens", "completion_tokens")} | dict(
            certifiable=bool(ref.all_certifies), optimal_size=int(ref.optimal_size),
            optimal_computed=bool(ref.optimal_computed), greedy_cost=int(ref.greedy_cost),
            coverage_cost=int(ref.coverage_cost), random_cost=int(ref.random_cost)))
    summary = pd.DataFrame(summary).sort_values(["adversary", "epsilon", "k", "seed"],
                                                ascending=[False, False, True, True])
    summary.to_csv(out / "summary.csv", index=False)

    record = dict(
        model=name, ollama=meta, temperature=None if args.dry_run else TEMPERATURE,
        seeds=list(seeds), max_steps=MAX_STEPS, num_ctx=NUM_CTX, quick=args.quick, dry_run=args.dry_run,
        regimes=[f"{a}|assumed|eps={e:.2f}|k={k}" for a, e, k in regimes_wanted],
        git_commit=_git_commit(), python=sys.version.split()[0], platform=platform.system(),
        system_prompt_sha256=hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        inputs={str(p.relative_to(ROOT)): _sha(p) for p in [
            Path(__file__), ROOT / "src/grrc/range/llm_agent.py",
            ROOT / "src/grrc/range/environment.py", ROOT / "src/grrc/range/adversary.py",
            ROOT / "src/grrc/range/regimes.py", BUNDLE, GAP]},
        outputs={str(p.relative_to(ROOT)): _sha(p) for p in [episodes_path, out / "summary.csv"]})
    (out / "run_record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    cert = summary.groupby("adversary").certified.mean()
    print(f"\nwrote {out.relative_to(ROOT)}: {len(summary)} episodes; certified share by "
          f"adversary: {cert.round(2).to_dict()}")


if __name__ == "__main__":
    main()

"""Train tabular Q-learning defenders on the hospital cyber range.

One defender per (reward, architecture). Training scenarios come from their
own bank (seed TRAIN_SEED), disjoint from the evaluation bank, and cycle
through every (profile, entry point) cell. Each defender trains in its own
process with no shared state; run one invocation per defender:

    python scripts/train_defenders.py --reward containment --arch today

Rewards (grrc.agent_env.DefenderEnv._reward):
  containment  -new compromises per decision: what autonomous cyber-defence
               benchmarks optimise
  soft         containment minus lambda x clinical hours: a CAGE-4-style
               availability penalty
  clinical     -clinical hours: the true objective, which a real defender
               never observes this directly
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grrc.agent_env import DefenderEnv  # noqa: E402
from grrc.config import load_config  # noqa: E402
from grrc.defender_agents import QLearner, learning_actions, train  # noqa: E402
from grrc.models import TrialSpec  # noqa: E402

CONFIG = ROOT / "configs" / "multiobjective_portfolio.yaml"
OUT = ROOT / "data" / "agentic" / "models"
TRAIN_SEED = 20260923
TRAIN_OFFSET = 70_000_000
INTERVAL = 12  # one decision per simulated hour (12 x 5-minute steps)
SOFT_LAMBDA = 1.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reward", required=True,
                    choices=["containment", "soft", "clinical"])
    ap.add_argument("--arch", required=True, choices=["today", "replicas"])
    ap.add_argument("--episodes", type=int, default=3000)
    args = ap.parse_args()

    cfg = load_config(CONFIG)
    profiles = list(cfg.optimization.profiles)
    entries = list(cfg.experiment.entry_points)
    actions = learning_actions(args.arch)
    name = f"q_{args.reward}_{args.arch}"
    agent = QLearner(actions=actions, name=name)

    def make_env(i: int) -> DefenderEnv:
        cell = i % (len(profiles) * len(entries))
        spec = TrialSpec(
            trial_id=i, scenario_id=TRAIN_OFFSET + i, paired=True,
            experiment="defender_training",
            facility=cfg.optimization.facility,
            profile=profiles[cell % len(profiles)],
            portfolio="profile_baseline",
            entry_point=entries[cell // len(profiles)],
            master_seed=TRAIN_SEED)
        return DefenderEnv(cfg, spec, interval=INTERVAL,
                           replicas=args.arch == "replicas",
                           reward=args.reward, soft_lambda=SOFT_LAMBDA)

    started = time.time()
    returns = train(agent, make_env, args.episodes,
                    seed=TRAIN_SEED + zlib.crc32(name.encode()) % 1000,
                    log_every=max(1, args.episodes // 20))
    OUT.mkdir(parents=True, exist_ok=True)
    agent.save(OUT / f"{name}.json", meta={
        "reward": args.reward, "architecture": args.arch,
        "episodes": args.episodes, "interval_steps": INTERVAL,
        "soft_lambda": SOFT_LAMBDA, "train_seed": TRAIN_SEED,
        "train_scenario_offset": TRAIN_OFFSET,
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "mean_return_first_10pct": float(
            sum(returns[:len(returns) // 10]) / max(1, len(returns) // 10)),
        "mean_return_last_10pct": float(
            sum(returns[-(len(returns) // 10):]) / max(1, len(returns) // 10)),
        "wall_seconds": round(time.time() - started, 1)})
    (OUT / f"{name}_returns.json").write_text(json.dumps(returns),
                                               encoding="utf-8")
    print(f"saved {name}", flush=True)


if __name__ == "__main__":
    main()

"""Evaluate autonomous defenders, with and without the shield, on paired scenarios.

Every condition replays the same evaluation bank (seed EVAL_SEED, disjoint
from the training bank), so any two conditions differ only in the defender's
decisions. Each condition is checkpointed on its own; run one subset per
process (no process pool — see scripts/run_islanding_experiment.py for why):

    python scripts/evaluate_defenders.py --conditions passive,disconnect
    python scripts/evaluate_defenders.py --assemble

EXPLORATORY: no protocol was frozen before this run.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CRLF, LF = bytes([13, 10]), bytes([10])

import pandas as pd  # noqa: E402

from grrc.agent_env import DefenderEnv  # noqa: E402
from grrc.config import load_config  # noqa: E402
from grrc.defender_agents import OnAlert, Passive, QLearner, run_episode  # noqa: E402
from grrc.models import TrialSpec  # noqa: E402
from grrc.shield import DependencyClosureShield  # noqa: E402

CONFIG = ROOT / "configs" / "multiobjective_portfolio.yaml"
MODELS = ROOT / "data" / "agentic" / "models"
OUT = ROOT / "data" / "agentic" / "raw"
EVAL_SEED = 20260924
EVAL_OFFSET = 60_000_000
INTERVAL = 12


def _learned(name):
    return lambda: QLearner.load(MODELS / f"{name}.json")


#: name -> (agent factory, replica architecture, shielded, kind)
CONDITIONS = {
    "passive": (Passive, False, False, "scripted"),
    "passive_replicas": (Passive, True, False, "scripted"),
    "disconnect": (lambda: OnAlert("disconnect"), False, False, "scripted"),
    "disconnect_shielded": (lambda: OnAlert("disconnect"), False, True,
                            "scripted"),
    "zone_lockdown": (lambda: OnAlert("zone_lockdown"), False, False,
                      "scripted"),
    # Upper bound only: the model cannot price the intra-zone dependencies
    # this breaks, so it is never offered to a learning defender.
    "micro_lockdown_upper_bound": (lambda: OnAlert("micro_lockdown"), False,
                                   False, "scripted"),
    "islands": (lambda: OnAlert("islands"), True, False, "scripted"),
    "islands_shielded": (lambda: OnAlert("islands"), True, True, "scripted"),
}
for _reward in ("containment", "soft", "clinical"):
    for _arch in ("today", "replicas"):
        _name = f"q_{_reward}_{_arch}"
        CONDITIONS[_name] = (_learned(_name), _arch == "replicas", False,
                             "learned")
        CONDITIONS[f"{_name}_shielded"] = (_learned(_name),
                                           _arch == "replicas", True,
                                           "learned")


def build_specs(cfg, scenarios: int) -> list[TrialSpec]:
    specs = []
    for p_idx, profile in enumerate(cfg.optimization.profiles):
        for e_idx, entry in enumerate(cfg.experiment.entry_points):
            for rep in range(scenarios):
                sid = EVAL_OFFSET + p_idx * 100_000 + e_idx * 10_000 + rep
                specs.append(TrialSpec(
                    trial_id=sid, scenario_id=sid, paired=True,
                    experiment="defender_evaluation",
                    facility=cfg.optimization.facility, profile=profile,
                    portfolio="profile_baseline", entry_point=entry,
                    master_seed=EVAL_SEED))
    return specs


def run_condition(cfg, name: str, scenarios: int) -> pd.DataFrame:
    factory, replicas, shielded, kind = CONDITIONS[name]
    rows = []
    for spec in build_specs(cfg, scenarios):
        agent = factory()
        env = DefenderEnv(cfg, spec, interval=INTERVAL, replicas=replicas,
                          shield=DependencyClosureShield() if shielded else None)
        row = run_episode(agent, env)
        rows.append({"condition": name, "kind": kind,
                     "architecture": "replicas" if replicas else "today",
                     "shielded": int(shielded), "scenario_id": spec.scenario_id,
                     "profile": spec.profile, "entry_point": spec.entry_point,
                     **row})
    return pd.DataFrame(rows)


def _source_sha256() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src" / "grrc").glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes().replace(CRLF, LF))
    return digest.hexdigest()


def assemble(cfg, scenarios: int) -> None:
    parts = OUT / "parts"
    missing = [n for n in CONDITIONS
               if not (parts / f"{n}.csv.gz").exists()]
    if missing:
        raise SystemExit(f"missing conditions: {missing}")
    # round_trip: the default float parser is inexact (see the islanding
    # runner), and exactness is what makes the combined file reproducible.
    raw = pd.concat([pd.read_csv(parts / f"{n}.csv.gz",
                                 float_precision="round_trip")
                     for n in CONDITIONS], ignore_index=True)
    path = OUT / "defender_evaluation.csv.gz"
    raw.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
    models = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(MODELS.glob("q_*.json"))
              if not p.name.endswith("_returns.json")}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--", "src"], cwd=ROOT,
            text=True).strip())
    except Exception:  # pragma: no cover - provenance only
        commit, dirty = "unknown", True
    manifest = {
        "status": "EXPLORATORY - no protocol frozen before this run",
        "config": "configs/multiobjective_portfolio.yaml",
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "eval_seed": EVAL_SEED, "eval_scenario_offset": EVAL_OFFSET,
        "scenarios_per_cell": scenarios, "decision_interval_steps": INTERVAL,
        "conditions": {n: {"architecture": "replicas" if c[1] else "today",
                           "shielded": c[2], "kind": c[3]}
                       for n, c in CONDITIONS.items()},
        "model_sha256": models, "rows": int(len(raw)),
        "raw_text_sha256": hashlib.sha256(
            gzip.decompress(path.read_bytes())).hexdigest(),
        "git_commit": commit, "git_dirty": dirty,
        "source_sha256": _source_sha256(),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                       encoding="utf-8")
    print(f"wrote {len(raw)} rows to {path}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--conditions", default="")
    ap.add_argument("--scenarios", type=int, default=40)
    ap.add_argument("--assemble", action="store_true")
    args = ap.parse_args()
    cfg = load_config(CONFIG)
    if args.assemble:
        assemble(cfg, args.scenarios)
        return
    names = [c for c in args.conditions.split(",") if c] or list(CONDITIONS)
    unknown = sorted(set(names) - set(CONDITIONS))
    if unknown:
        raise SystemExit(f"unknown conditions: {unknown}")
    (OUT / "parts").mkdir(parents=True, exist_ok=True)
    for name in names:
        part = OUT / "parts" / f"{name}.csv.gz"
        if part.exists():
            print(f"[{name}] checkpoint present, skipping", flush=True)
            continue
        t0 = time.time()
        frame = run_condition(cfg, name, args.scenarios)
        tmp = part.with_suffix(".tmp")
        frame.to_csv(tmp, index=False,
                     compression={"method": "gzip", "mtime": 0})
        tmp.replace(part)
        print(f"[{name}] {len(frame)} episodes in {time.time() - t0:.0f}s",
              flush=True)


if __name__ == "__main__":
    main()

"""Exploratory paired experiment: dependency-closed controlled islanding.

EXPLORATORY. No protocol was frozen before this run, so nothing it produces
may be reported as confirmatory. study/ISLANDING_SPECIFICATION.md section 6
states what a confirmatory run would require.

Design. Every condition replays the same bank of paired scenarios: the same
topology, entry node, event random fields and per-scenario parameter draws
(configs/multiobjective_portfolio.yaml, the study's primary design, with its
declared parameter uncertainty). Each profile keeps its own exogenous posture
(``profile_baseline``); islanding is the only thing layered on top. So every
contrast below is a within-scenario difference.

Conditions, and the question each answers:

  none           no islanding — the reference
  zone           the closest prior art: tighten to least privilege on
                 detection. Does the method beat what already exists?
  crude3         sever 3 islands WITHOUT replicas — what health systems do
                 when they disconnect a site. Is disconnection alone enough?
  dcci3          the method, 3 islands
  dcci2, dcci4   island count. Does the k >= 1/(1 - theta) rule hold?
  *_theta45      service threshold 0.45 instead of 0.60. Isolates the
                 island-count rule from the spread confound (see CONDITIONS).
  dcci3_nolocal  no restoration inside contained islands. How much of the
                 effect runs through structural assumption S1?
  none_ungated,  structural assumption S1 switched off (restoration not
  zone_ungated,  gated on containment). Does the ranking survive the
  dcci3_ungated  alternative the study's own sensitivity analysis runs?
  micro          the strongest segmentation comparator the model can express:
                 a lockdown that also cuts every intra-zone edge, for free.
                 Does the method beat it?
  dcci3_micro    islands with that lockdown inside each one. Does islanding
                 add anything ON TOP of the strongest segmentation?

Each condition is checkpointed to data/islanding/raw/parts/ as it finishes,
and ``--resume`` skips conditions already there, so an interrupted run loses
at most the condition in flight. The parts are left in place (gitignored)
after the combined file and manifest are written. Write progress to a log
file, not a pipe: the progress bar's carriage-return updates can fill a pipe
that is only drained at end of line, and a blocked parent then leaves every
worker idle.

On some Windows machines ProcessPoolExecutor's shared queues fail
mid-run (a frozen pool, or ``WinError 6`` on the queue lock). The results
do not depend on how trials are scheduled, because every trial is determined
by its spec, so the robust alternative is one single-process job per
condition with no shared queues at all:

    python scripts/run_islanding_experiment.py --conditions dcci4 --workers 1

then a final ``--resume`` pass, which finds every checkpoint and only
assembles the combined file and manifest.

Usage:
    python scripts/run_islanding_experiment.py [--scenarios N] [--resume]
        [--conditions a,b,...] [--workers W]
"""

from __future__ import annotations

import argparse
import dataclasses
import gzip
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from grrc.config import load_config  # noqa: E402
from grrc.defenses import DefensePortfolio  # noqa: E402
from grrc.experiments import run_specs  # noqa: E402
from grrc.models import TrialSpec  # noqa: E402

CONFIG = ROOT / "configs" / "multiobjective_portfolio.yaml"
OUT = ROOT / "data" / "islanding"
#: A fresh scenario bank. Deliberately not the confirmatory seed: this run
#: must not be mistaken for, or contaminate, the frozen confirmatory bank.
MASTER_SEED = 20260922
ID_OFFSET = 90_000_000
CRLF, LF = bytes([13, 10]), bytes([10])

BASE = DefensePortfolio("profile_baseline")
ISLANDED = DefensePortfolio("profile_baseline_islanded", islanding=True)

#: name -> (portfolio, simulation overrides)
CONDITIONS: dict[str, tuple[DefensePortfolio, dict]] = {
    "none": (BASE, {}),
    "zone": (ISLANDED, {"island_partition": "zone"}),
    "crude3": (ISLANDED, {"island_count": 3,
                          "island_dependency_closed": False}),
    "dcci3": (ISLANDED, {"island_count": 3}),
    "dcci2": (ISLANDED, {"island_count": 2}),
    "dcci4": (ISLANDED, {"island_count": 4}),
    "dcci3_nolocal": (ISLANDED, {"island_count": 3,
                                 "island_local_restore": False}),
    "none_ungated": (BASE, {"restore_requires_containment": False}),
    "zone_ungated": (ISLANDED, {"island_partition": "zone",
                                "restore_requires_containment": False}),
    "dcci3_ungated": (ISLANDED, {"island_count": 3,
                                 "restore_requires_containment": False}),
    # The island-count rule, isolated from the spread confound. Fewer islands
    # also cut fewer edges, so dcci2 vs dcci3 alone cannot tell the capacity
    # rule from weaker containment. But the edge cut does not depend on the
    # service threshold, and the rule does: k_min = 3 at theta = 0.60 and 2 at
    # theta = 0.45. So the rule predicts that dcci2 recovers most of dcci3's
    # benefit at theta = 0.45 and much less at 0.60, with the spread effect
    # held fixed across both.
    "none_theta45": (BASE, {"service_functional_fraction": 0.45}),
    "dcci2_theta45": (ISLANDED, {"island_count": 2,
                                 "service_functional_fraction": 0.45}),
    "dcci3_theta45": (ISLANDED, {"island_count": 3,
                                 "service_functional_fraction": 0.45}),
    # Added after the first 13 conditions had run, and appended rather than
    # inserted so every earlier condition keeps its index and trial ids. A
    # zone comparator that leaves every intra-zone edge open is too weak to
    # carry a "beats prior art" claim. So the claim is tested against the
    # strongest segmentation lockdown this model can express, and islanding
    # is tested ON TOP of it.
    "micro": (ISLANDED, {"island_partition": "zone_micro"}),
    "dcci3_micro": (ISLANDED, {"island_count": 3,
                               "island_micro_within": True}),
}


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # pragma: no cover - provenance only
        return "unknown"


def _git_dirty() -> bool:
    try:
        return bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--", "src", "configs"],
            cwd=ROOT, text=True).strip())
    except Exception:  # pragma: no cover - provenance only
        return True


def _source_sha256() -> str:
    """Hash of the simulator source actually executed.

    Recorded because the commit alone cannot identify the code when the run
    happens on an uncommitted tree: with ``git_dirty`` true, this hash is the
    only thing that pins which simulator produced the data. Line endings are
    normalized so the hash does not depend on the checkout platform.
    """
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src" / "grrc").glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes().replace(CRLF, LF))
    return digest.hexdigest()


def build_specs(cfg, scenarios: int, condition_index: int,
                portfolio: DefensePortfolio) -> list[TrialSpec]:
    """One spec per scenario. Scenario ids are identical across conditions."""
    specs = []
    for p_idx, profile in enumerate(cfg.optimization.profiles):
        for e_idx, entry in enumerate(cfg.experiment.entry_points):
            for rep in range(scenarios):
                scenario_id = (ID_OFFSET + p_idx * 100_000
                               + e_idx * 10_000 + rep)
                specs.append(TrialSpec(
                    trial_id=scenario_id * 16 + condition_index,
                    scenario_id=scenario_id, paired=True,
                    experiment="islanding_exploratory",
                    facility=cfg.optimization.facility, profile=profile,
                    portfolio=portfolio.name, entry_point=entry,
                    master_seed=MASTER_SEED))
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenarios", type=int, default=100,
                        help="scenarios per (profile, entry point) cell")
    parser.add_argument("--resume", action="store_true",
                        help="skip conditions already checkpointed")
    parser.add_argument("--conditions", default="",
                        help="comma-separated subset of conditions to run")
    parser.add_argument("--workers", type=int, default=None,
                        help="override worker count (1 = no process pool)")
    args = parser.parse_args()
    selected = ([c for c in args.conditions.split(",") if c]
                or list(CONDITIONS))
    unknown = sorted(set(selected) - set(CONDITIONS))
    if unknown:
        raise SystemExit(f"unknown conditions: {unknown}")

    base_cfg = load_config(CONFIG)
    parts = OUT / "raw" / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    started = time.time()
    for index, (name, (portfolio, overrides)) in enumerate(CONDITIONS.items()):
        part = parts / f"{index:02d}_{name}.csv.gz"
        if name not in selected:
            continue
        if args.resume and part.exists():
            print(f"[{name}] checkpoint present, skipping", flush=True)
            continue
        cfg = dataclasses.replace(base_cfg, simulation=dataclasses.replace(
            base_cfg.simulation, islanding_enabled=True, **overrides))
        if args.workers is not None:
            cfg = dataclasses.replace(cfg, experiment=dataclasses.replace(
                cfg.experiment, workers=args.workers))
        cfg.validate()
        specs = build_specs(cfg, args.scenarios, index, portfolio)
        t0 = time.time()
        frame = run_specs(cfg, specs, portfolios={portfolio.name: portfolio},
                          desc=f"islanding:{name}")
        frame.insert(0, "condition", name)
        tmp = part.with_suffix(".tmp")
        frame.to_csv(tmp, index=False,
                     compression={"method": "gzip", "mtime": 0})
        tmp.replace(part)  # atomic: a part is either complete or absent
        print(f"[{name}] {len(frame)} rows in {time.time() - t0:.0f}s",
              flush=True)

    missing = [name for i, name in enumerate(CONDITIONS)
               if not (parts / f"{i:02d}_{name}.csv.gz").exists()]
    if missing:
        print(f"checkpointed; still missing: {missing}", flush=True)
        return
    # round_trip: pandas' default float parser is not exact. Reading the
    # checkpoints with it once perturbed 19 values in the last digit, which
    # is harmless to any result but breaks byte-for-byte reproducibility.
    frames = [pd.read_csv(parts / f"{i:02d}_{name}.csv.gz",
                          float_precision="round_trip")
              for i, name in enumerate(CONDITIONS)]
    if any(len(f) != len(frames[0]) for f in frames):
        raise RuntimeError("conditions have different row counts; "
                           "delete data/islanding/raw/parts and rerun")
    raw = pd.concat(frames, ignore_index=True)
    raw_path = OUT / "raw" / "islanding_experiment.csv.gz"
    # mtime=0 in the gzip header keeps the file byte-reproducible.
    raw.to_csv(raw_path, index=False,
               compression={"method": "gzip", "mtime": 0})

    manifest = {
        "status": "EXPLORATORY - no protocol frozen before this run",
        "specification": "study/ISLANDING_SPECIFICATION.md",
        "config": str(CONFIG.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "master_seed": MASTER_SEED,
        "scenario_id_offset": ID_OFFSET,
        "scenarios_per_cell": args.scenarios,
        "profiles": list(base_cfg.optimization.profiles),
        "entry_points": list(base_cfg.experiment.entry_points),
        "conditions": {name: {"portfolio": p.name, "overrides": o}
                       for name, (p, o) in CONDITIONS.items()},
        "rows": int(len(raw)),
        "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        # The gzip header can carry the output filename, so identical data
        # can differ in compressed bytes. This hash is of the CSV text.
        "raw_text_sha256": hashlib.sha256(
            gzip.decompress(raw_path.read_bytes())).hexdigest(),
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "source_sha256": _source_sha256(),
        "wall_seconds": round(time.time() - started, 1),
    }
    (OUT / "raw" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # Checkpoints are deliberately left in place. Deleting them here once
    # removed most of them and then failed on Windows (WinError 6), and a
    # later --resume took the gaps as unfinished work and began re-simulating.
    # They are gitignored; delete data/islanding/raw/parts by hand.
    print(f"wrote {len(raw)} rows to {raw_path}")


if __name__ == "__main__":
    main()

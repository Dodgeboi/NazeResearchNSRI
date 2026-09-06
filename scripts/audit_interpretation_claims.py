#!/usr/bin/env python3
"""Evaluate registered claims and a finite retrospective fault suite.

--write records a report. It never treats an unsupported assertion as a pass.
This script does not certify arbitrary prose or independent scientific truth.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pandas as pd

from grrc.claim_contracts import evaluate

ROOT = Path(__file__).resolve().parents[1]


def load_sources(registry):
    sources = {}
    for name, spec in registry["sources"].items():
        sources[name] = (pd.read_csv(ROOT / spec["path"]), spec["units"])
    return sources


def audit():
    registry = json.loads((ROOT / "study/interpretation_contracts.json").read_text())
    sources = load_sources(registry)
    current = [evaluate(claim, sources) for claim in registry["current"]]
    historical = [evaluate(claim, sources) for claim in registry["historical"]]
    mutations = []
    for item in registry["mutations"]:
        original = next(c for c in registry["current"] if c["id"] == item["base"])
        changed = copy.deepcopy(original)
        changed.update(item["replace"])
        changed["id"] = item["id"]
        observed = evaluate(changed, sources)
        observed["expected"] = item["expected"]
        mutations.append(observed)
    ok = (all(r["status"] == "pass" for r in current)
          and all(r["status"] == "fail" for r in historical)
          and all(r["status"] == r["expected"] for r in mutations))
    return {"scope": "finite retrospective cases from one project; no unseen-paper accuracy estimate",
            "all_expected_outcomes": ok, "current": current,
            "historical": historical, "mutations": mutations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    report = audit()
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for key in ("current", "historical", "mutations"):
        print(key + ": " + ", ".join(f"{r['id']}={r['status']}" for r in report[key]))
    print("interpretation audit " + ("passed" if report["all_expected_outcomes"] else "FAILED"))
    return 0 if report["all_expected_outcomes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

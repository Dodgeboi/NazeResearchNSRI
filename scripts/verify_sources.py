#!/usr/bin/env python3
"""Verify every archived source against its registry entry. Fails loudly.

A source whose hash does not match is not usable evidence, so this exits
non-zero rather than warning. It also re-derives the counts the registry
records, which catches the subtler failure: a file whose bytes are intact
but whose analysis code has drifted underneath the recorded numbers.

Run in CI and before any manuscript build.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from grrc.provenance import sha256_file
from grrc.utilities import REPO_ROOT

MANIFEST = REPO_ROOT / "data" / "observed" / "raw" / "source_manifest.json"


def derive_threat_counts(path: Path) -> dict[str, object]:
    frame = pd.read_csv(path)
    attacked = frame[frame["attacked"] == 1]
    key = ["medicare_id", "threat_id", "attack_date"]
    deduped = attacked.drop_duplicates(subset=key)
    per_event = deduped.groupby("threat_id")["medicare_id"].nunique()
    return {
        "attacked_rows": int(len(attacked)),
        "records_after_deduplication": int(len(deduped)),
        "distinct_medicare_ids": int(attacked["medicare_id"].nunique()),
        "events": int(per_event.size),
        "single_hospital_events": int((per_event == 1).sum()),
        "multi_hospital_events": int((per_event > 1).sum()),
        "events_with_at_least_four_hospitals": int((per_event >= 4).sum()),
        "median_hospitals_per_event": int(per_event.median()),
        "mean_hospitals_per_event": round(float(per_event.mean()), 3),
        "max_hospitals_per_event": int(per_event.max()),
        "er_diversion_records": int(deduped["er_diversion"].sum()),
        "cancel_delay_records": int(deduped["cancel_delay"].sum()),
    }


def derive_kev_counts(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    vulns = payload["vulnerabilities"]
    tagged = [v for v in vulns
              if str(v.get("knownRansomwareCampaignUse", "")).lower() == "known"]
    return {"records": len(vulns), "ransomware_tagged": len(tagged)}


DERIVERS = {
    "threat_openicpsr_v1": derive_threat_counts,
    "cisa_kev_2026_09_01": derive_kev_counts,
}


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []
    for source in manifest["sources"]:
        path = MANIFEST.parent / source["local_file"]
        label = source["id"]
        if not path.exists():
            problems.append(f"{label}: archived file is missing ({path.name})")
            continue

        actual_hash = sha256_file(path)
        if actual_hash != source["sha256"]:
            problems.append(
                f"{label}: sha256 {actual_hash[:12]}… != recorded "
                f"{source['sha256'][:12]}…")
        actual_bytes = path.stat().st_size
        if source.get("bytes") not in (None, actual_bytes):
            problems.append(
                f"{label}: {actual_bytes} bytes != recorded {source['bytes']}")

        deriver = DERIVERS.get(label)
        recorded = source.get("derived_counts") or {}
        if deriver and recorded:
            for name, value in deriver(path).items():
                if name in recorded and recorded[name] != value:
                    problems.append(
                        f"{label}: derived {name} = {value} but the registry "
                        f"records {recorded[name]}")
        print(f"{'ok ' if not problems else '   '}{label}: "
              f"{actual_bytes:,} bytes, sha256 {actual_hash[:12]}…")

    if problems:
        print("\nSOURCE VERIFICATION FAILED", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print("\nall archived sources verify, and every recorded count "
          "re-derives from the file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

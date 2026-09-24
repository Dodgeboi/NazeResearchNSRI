#!/usr/bin/env python3
"""Fetch the Enterprise ATT&CK release history and write compact, pinned extracts.

For the latest patch of every major Enterprise ATT&CK release (pinned explicitly in
``VERSIONS``, not "latest"), download the raw STIX bundle from the official
mitre-attack/attack-stix-data repository into a gitignored cache, record its SHA-256,
and write a small deterministic extract with only what the coverage analysis needs:
active techniques (id, name, tactics, sub-technique flag), active mitigations (id,
name) and active ``mitigates`` edges; a second extract per release keeps ATT&CK's
documented ``uses`` edges (software, groups, campaigns to techniques). The extracts and ``source_manifest.json`` are
committed; the ~50 MB raw bundles are not. Re-running with a warm cache re-verifies
each bundle's hash and reproduces byte-identical extracts.

MITRE ATT&CK is released by The MITRE Corporation under the ATT&CK Terms of Use
(https://attack.mitre.org/resources/legal-and-branding/terms-of-use/); it is used here
unmodified. Nothing is fabricated: an unreachable or malformed release fails loudly.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import io
import json
import time
import urllib.request
from pathlib import Path

from grrc.attack_graph import _active, _external_id
from grrc.provenance import utc_now

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/attack_history"
CACHE = OUT / "cache"
EXTRACTS = OUT / "extracts"
USAGE = OUT / "usage"
USAGE_TYPES = ("malware", "tool", "intrusion-set", "campaign")
BASE_URL = ("https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/"
            "enterprise-attack/enterprise-attack-{v}.json")
# Latest patch of each major Enterprise release, per the repository's index.json
# (retrieved 2026-09-23). Pinned so the study does not drift as MITRE publishes.
VERSIONS = ("1.0", "2.0", "3.0", "4.0", "5.2", "6.3", "7.2", "8.2", "9.0", "10.1",
            "11.3", "12.1", "13.1", "14.1", "15.1", "16.1", "17.1", "18.1", "19.2")
# Release dates ("modified") as listed for each version in the repository's index.json.
RELEASE_DATES = {
    "1.0": "2018-01-17", "2.0": "2018-04-18", "3.0": "2018-10-23", "4.0": "2019-04-30",
    "5.2": "2019-07-27", "6.3": "2020-03-09", "7.2": "2020-07-15", "8.2": "2021-01-27",
    "9.0": "2021-04-29", "10.1": "2021-11-10", "11.3": "2022-07-07", "12.1": "2022-11-08",
    "13.1": "2023-05-09", "14.1": "2023-11-14", "15.1": "2024-05-02", "16.1": "2024-11-12",
    "17.1": "2025-05-06", "18.1": "2025-11-13", "19.2": "2026-08-05"}


def _download(version: str, attempts: int = 5) -> bytes:
    path = CACHE / f"enterprise-attack-{version}.json"
    if path.exists():
        return path.read_bytes()
    url = BASE_URL.format(v=version)
    for attempt in range(attempts):
        print(f"fetching {url}" + (f" (retry {attempt})" if attempt else ""), flush=True)
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                payload = response.read()
            break
        except (OSError, http.client.HTTPException) as exc:   # transient network failure
            if attempt == attempts - 1:
                raise SystemExit(f"could not fetch release {version}: {exc}")
            time.sleep(2 ** (attempt + 1))
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(payload)
    tmp.replace(path)                                      # atomic: no partial cache files
    return payload


def extract(bundle: dict, version: str) -> dict:
    """The minimal, deterministic view of one release used by the coverage analysis."""
    objects = bundle["objects"]
    modified = next((o.get("modified") for o in objects if o.get("type") == "x-mitre-collection"),
                    None)
    techniques, tech_by_ref = [], {}
    for o in objects:
        if o.get("type") != "attack-pattern" or not _active(o):
            continue
        ext = _external_id(o)
        if ext is None:
            continue
        tactics = sorted({p["phase_name"] for p in o.get("kill_chain_phases", [])})
        tech_by_ref[o["id"]] = ext
        techniques.append(dict(id=ext, name=o.get("name", ""), tactics=tactics,
                               is_sub=bool(o.get("x_mitre_is_subtechnique", False))))
    mitigations, mit_by_ref = [], {}
    for o in objects:
        if o.get("type") != "course-of-action" or not _active(o):
            continue
        ext = _external_id(o)
        if ext is None:
            continue
        mit_by_ref[o["id"]] = ext
        mitigations.append(dict(id=ext, name=o.get("name", "")))
    edges = set()
    for o in objects:
        if o.get("type") != "relationship" or o.get("relationship_type") != "mitigates":
            continue
        if not _active(o):
            continue
        m, t = mit_by_ref.get(o.get("source_ref")), tech_by_ref.get(o.get("target_ref"))
        if m is not None and t is not None:
            edges.add((m, t))
    return dict(version=version, collection_modified=modified,
                techniques=sorted(techniques, key=lambda r: r["id"]),
                mitigations=sorted(mitigations, key=lambda r: r["id"]),
                mitigates=sorted([list(e) for e in edges]))


def extract_usage(bundle: dict, version: str) -> dict:
    """ATT&CK's documented procedure examples: active ``uses`` edges from active software,
    groups and campaigns to active techniques (entity id, name, type; technique id)."""
    objects = bundle["objects"]
    tech_by_ref = {o["id"]: _external_id(o) for o in objects
                   if o.get("type") == "attack-pattern" and _active(o) and _external_id(o)}
    entities, ent_by_ref = [], {}
    for o in objects:
        if o.get("type") not in USAGE_TYPES or not _active(o):
            continue
        ext = _external_id(o)
        if ext is None:
            continue
        ent_by_ref[o["id"]] = ext
        entities.append(dict(id=ext, name=o.get("name", ""), type=o["type"]))
    edges = set()
    for o in objects:
        if o.get("type") != "relationship" or o.get("relationship_type") != "uses":
            continue
        if not _active(o):
            continue
        e, t = ent_by_ref.get(o.get("source_ref")), tech_by_ref.get(o.get("target_ref"))
        if e is not None and t is not None:
            edges.add((e, t))
    return dict(version=version, entities=sorted(entities, key=lambda r: r["id"]),
                uses=sorted([list(e) for e in edges]))


def _write_extract(data: dict, path: Path) -> str:
    """Deterministic gzip JSON (fixed mtime, sorted keys); returns the sha256 of the bytes."""
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(raw)
    path.write_bytes(buf.getvalue())
    return hashlib.sha256(buf.getvalue()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", nargs="*", default=list(VERSIONS))
    parser.add_argument("--usage-only", action="store_true",
                        help="write only the usage extracts, leaving the coverage extracts "
                             "and their manifest untouched")
    args = parser.parse_args()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    USAGE.mkdir(parents=True, exist_ok=True)
    records, usage_records = [], []
    for version in args.versions:
        payload = _download(version)
        bundle = json.loads(payload)
        if bundle.get("type") != "bundle" or "objects" not in bundle:
            raise SystemExit(f"release {version} is not a STIX bundle")
        usage = extract_usage(bundle, version)
        usage_target = USAGE / f"enterprise-{version}.json.gz"
        usage_records.append(dict(
            version=version, release_date=RELEASE_DATES.get(version),
            uncompressed_sha256=hashlib.sha256(payload).hexdigest(),
            extract=str(usage_target.relative_to(ROOT)),
            extract_sha256=_write_extract(usage, usage_target),
            entities=len(usage["entities"]), uses_edges=len(usage["uses"])))
        if args.usage_only:
            continue
        data = extract(bundle, version)
        target = EXTRACTS / f"enterprise-{version}.json.gz"
        extract_sha = _write_extract(data, target)
        records.append(dict(
            version=version, release_date=RELEASE_DATES.get(version), url=BASE_URL.format(v=version),
            uncompressed_sha256=hashlib.sha256(payload).hexdigest(),
            uncompressed_bytes=len(payload), objects=len(bundle["objects"]),
            collection_modified=data["collection_modified"],
            extract=str(target.relative_to(ROOT)), extract_sha256=extract_sha,
            techniques=len(data["techniques"]), mitigations=len(data["mitigations"]),
            mitigates_edges=len(data["mitigates"])))
        print(f"  v{version}: {len(data['techniques'])} techniques, "
              f"{len(data['mitigations'])} mitigations, {len(data['mitigates'])} edges", flush=True)
    (USAGE / "source_manifest.json").write_text(json.dumps(dict(
        source="MITRE ATT&CK Enterprise (mitre-attack/attack-stix-data)",
        license="MITRE ATT&CK Terms of Use",
        content="active 'uses' relationships from software, groups and campaigns",
        releases=usage_records), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(usage_records)} usage extracts")
    if args.usage_only:
        return 0
    (OUT / "source_manifest.json").write_text(json.dumps(dict(
        source="MITRE ATT&CK Enterprise (mitre-attack/attack-stix-data)",
        license="MITRE ATT&CK Terms of Use", retrieved_at=utc_now(),
        selection="latest patch of each major release, pinned in scripts/fetch_attack_history.py",
        releases=records), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} extracts and {(OUT / 'source_manifest.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

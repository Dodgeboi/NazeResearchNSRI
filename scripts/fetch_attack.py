#!/usr/bin/env python3
"""Fetch the pinned MITRE ATT&CK Enterprise STIX bundle and record its hash.

This is the only network step in the control-certificate study. It downloads one
pinned, versioned ATT&CK release file (not "latest"), so the analysis is
reproducible, records the SHA-256 and byte count in a small source record beside
it, and refuses to overwrite a file whose bytes disagree with the archive it
already holds. It fabricates nothing: if the pinned URL is unreachable it fails
loudly rather than substituting synthetic data.

MITRE ATT&CK is released by The MITRE Corporation under the ATT&CK Terms of Use
(https://attack.mitre.org/resources/legal-and-branding/terms-of-use/); it is an
independently authored, publicly published knowledge base, used here unmodified.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import urllib.request
from pathlib import Path

from grrc.provenance import utc_now

ROOT = Path(__file__).resolve().parents[1]
VERSION = "17.1"
URL = ("https://raw.githubusercontent.com/mitre-attack/attack-stix-data/"
       f"master/enterprise-attack/enterprise-attack-{VERSION}.json")
OUT = ROOT / "data/attack/raw"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"enterprise-attack-{VERSION}.json.gz"
    record = OUT / "source.json"
    print(f"fetching {URL}", flush=True)
    with urllib.request.urlopen(URL, timeout=120) as response:
        payload = response.read()
    # Validate it parses as a STIX bundle before trusting it.
    bundle = json.loads(payload)
    if bundle.get("type") != "bundle" or "objects" not in bundle:
        raise SystemExit("downloaded file is not a STIX bundle")
    # Hash the uncompressed content (what MITRE serves) so the record reproduces
    # across machines regardless of gzip framing.
    digest = hashlib.sha256(payload).hexdigest()
    # Deterministic gzip: fixed mtime so re-fetching identical content yields
    # byte-identical storage.
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(target, "wb"), mtime=0) as gz:
        gz.write(payload)
    record.write_text(json.dumps({
        "source": "MITRE ATT&CK Enterprise",
        "version": VERSION,
        "url": URL,
        "uncompressed_sha256": digest,
        "uncompressed_bytes": len(payload),
        "objects": len(bundle["objects"]),
        "retrieved_at": utc_now(),
        "license": "MITRE ATT&CK Terms of Use",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)} ({len(payload):,} uncompressed bytes, "
          f"{len(bundle['objects']):,} objects, sha256 {digest[:12]})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

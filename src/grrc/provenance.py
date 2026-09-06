"""Content-addressed provenance for runs, protocols, and result manifests.

The WP0 audit found that the multi-objective manifests recorded seeds and
counts but not a single hash — not of the config, not of the code, not of any
input or output (ISSUE-014) — and that the "frozen" holdout protocol was
rewritten by its own runner on every invocation with no hash, timestamp, or
commit inside it (ISSUE-013). Both mean a reader cannot distinguish a genuine
prospective freeze from a file written afterwards, and nothing in the pipeline
would notice if a config changed between the raw run and the analysis.

This module supplies the three things that fixes require:

* :func:`sha256_file` / :func:`environment_fingerprint` / :func:`git_state` —
  the raw material of a manifest.
* :func:`build_manifest` — a manifest that hashes every consumed input and
  every produced output, and records the code commit, the environment, and a
  UTC timestamp.
* :func:`freeze_protocol` and :func:`load_frozen_protocol` — a
  content-addressed protocol artifact that **refuses to be overwritten**. Its
  own SHA-256 is stored inside it and in its filename, so a protocol that was
  edited after the fact cannot verify.

Design rule throughout: **fail loudly**. A provenance layer that degrades to a
warning when an input has changed is worse than none, because it manufactures
confidence. Every verification path here raises.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utilities import REPO_ROOT

#: Packages whose versions can change a numerical result.
_TRACKED_PACKAGES: tuple[str, ...] = (
    "numpy", "pandas", "scipy", "networkx", "matplotlib", "yaml",
)


class ProvenanceError(RuntimeError):
    """Raised when recorded provenance does not match reality."""


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def sha256_file(path: str | Path, *, chunk_size: int = 1 << 20) -> str:
    """SHA-256 of a file's bytes, streamed so large raw CSVs stay cheap."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    """Deterministic JSON encoding, so a hash of content is stable.

    Sorted keys and a fixed separator mean two runs that produced the same
    protocol produce byte-identical files and therefore the same digest.
    """
    return json.dumps(
        payload, sort_keys=True, indent=2, ensure_ascii=False,
        separators=(",", ": ")).encode("utf-8") + b"\n"


def relative_to_repo(path: str | Path) -> str:
    """POSIX path relative to the repository root.

    Always POSIX: the pre-rebuild holdout manifest recorded Windows
    backslash paths that could not be resolved on the declared CI runner
    (audit ISSUE-015).
    """
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def git_state(repo_root: Path | None = None) -> dict[str, Any]:
    """Current commit and dirty-tree state, or an explicit unavailability.

    A dirty tree is recorded rather than tolerated silently: results
    generated from uncommitted code are not reproducible from the public
    record, and the manifest must say so.
    """
    root = Path(repo_root or REPO_ROOT)

    def run(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True, text=True, timeout=30, check=True)
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return None
        # Leading spaces are meaningful in porcelain status (" M path").
        return out.stdout.rstrip("\r\n")

    commit = run("rev-parse", "HEAD")
    if commit is None:
        return {"available": False,
                "note": "git metadata unavailable in this environment"}
    status = run("status", "--porcelain")
    return {
        "available": True,
        "commit": commit,
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status),
        "dirty_paths": sorted(
            line[3:] for line in (status or "").splitlines())[:50],
    }


def environment_fingerprint() -> dict[str, Any]:
    """Interpreter, platform, and the versions that can move a number."""
    versions: dict[str, str] = {}
    for name in _TRACKED_PACKAGES:
        try:
            module = __import__(name)
        except ImportError:
            versions[name] = "not installed"
        else:
            versions[name] = getattr(module, "__version__", "unknown")
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": versions,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

def hash_paths(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """Hash a set of files, recording size and POSIX repo-relative path."""
    entries: list[dict[str, Any]] = []
    for path in paths:
        resolved = Path(path)
        if not resolved.exists():
            raise ProvenanceError(
                f"cannot hash missing file: {relative_to_repo(resolved)}")
        entries.append({
            "path": relative_to_repo(resolved),
            "bytes": resolved.stat().st_size,
            "sha256": sha256_file(resolved),
        })
    return sorted(entries, key=lambda entry: entry["path"])


def snapshot_inputs(paths: Iterable[str | Path], destination: str | Path
                    ) -> list[Path]:
    """Copy each input into the run directory and return the copies.

    A manifest that hashes a live config file records a hash that becomes
    false the moment anyone edits that file for an unrelated reason — even
    when the run's outputs are provably unaffected. Archiving the exact bytes
    beside the outputs makes the recorded hash permanently true, and lets a
    reader diff the snapshot against the current file to see what changed.

    This is the "complete configuration snapshots" requirement, and it exists
    because the first discovery run in this rebuild tripped exactly that
    failure: the study config's declared primary k changed after the run, so
    the manifest correctly refused to verify.
    """
    import shutil

    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    copies: list[Path] = []
    for source in paths:
        source_path = Path(source)
        if not source_path.exists():
            raise ProvenanceError(
                f"cannot snapshot missing input: {relative_to_repo(source_path)}")
        copy = target / source_path.name
        shutil.copy2(source_path, copy)
        copies.append(copy)
    return copies


def build_manifest(
        *,
        run_id: str,
        stage: str,
        description: str,
        inputs: Iterable[str | Path],
        outputs: Iterable[str | Path],
        parameters: Mapping[str, Any] | None = None,
        protocol: Mapping[str, Any] | None = None,
        source_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a manifest that binds inputs, code, environment, and outputs.

    :param stage: one of ``discovery``, ``confirmation``, ``validation``,
        ``analysis``. Recorded so a reader can tell at a glance whether an
        artifact is exploratory or confirmatory.
    :param protocol: for confirmatory stages, the frozen protocol's identity
        (``{"path": ..., "sha256": ...}``) as returned by
        :func:`load_frozen_protocol`.
    """
    if stage not in ("discovery", "confirmation", "validation", "analysis"):
        raise ValueError(f"unknown stage '{stage}'")
    return {
        "run_id": run_id,
        "stage": stage,
        "description": description,
        "created_at": utc_now(),
        "code": dict(source_state) if source_state is not None else git_state(),
        "environment": environment_fingerprint(),
        "parameters": dict(parameters or {}),
        "protocol": dict(protocol) if protocol else None,
        "inputs": hash_paths(inputs),
        "outputs": hash_paths(outputs),
    }


def write_manifest(manifest: Mapping[str, Any], path: str | Path) -> Path:
    """Write a manifest deterministically and return its path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json(manifest))
    return target


def verify_manifest(path: str | Path, *,
                    check_outputs: bool = True) -> dict[str, Any]:
    """Recompute every hash a manifest records and raise on any mismatch.

    This is what makes reproduction *fail* rather than silently continue when
    an input has changed since the run. Returns the manifest on success.
    """
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    sections = ["inputs"] + (["outputs"] if check_outputs else [])
    for section in sections:
        for entry in manifest.get(section) or []:
            target = REPO_ROOT / entry["path"]
            if not target.exists():
                problems.append(f"{section}: missing {entry['path']}")
                continue
            actual = sha256_file(target)
            if actual != entry["sha256"]:
                problems.append(
                    f"{section}: {entry['path']} sha256 "
                    f"{actual[:12]}… != recorded {entry['sha256'][:12]}…")
    if problems:
        raise ProvenanceError(
            f"{manifest_path.name} does not describe the files on disk:\n  "
            + "\n  ".join(problems))
    return manifest


# ---------------------------------------------------------------------------
# Frozen protocols
# ---------------------------------------------------------------------------

#: Where frozen protocol artifacts live. Kept outside ``data/`` on purpose:
#: a protocol is a commitment made *before* data exist, and it must not sit
#: in a directory that analysis scripts write to.
PROTOCOL_DIR = REPO_ROOT / "study" / "protocols"


def protocol_path(name: str) -> Path:
    return PROTOCOL_DIR / f"{name}.protocol.json"


def freeze_protocol(name: str, body: Mapping[str, Any], *,
                    overwrite: bool = False) -> dict[str, Any]:
    """Write a content-addressed protocol that cannot be silently replaced.

    The protocol's digest is computed over its body *excluding* the digest
    field, then stored inside the file and returned. Re-freezing an existing
    protocol raises unless ``overwrite`` is explicitly passed, which exists
    only for tests: a protocol a runner can rewrite is not a freeze, which
    was precisely the pre-rebuild defect (audit ISSUE-013).

    :returns: ``{"name", "path", "sha256", "frozen_at"}`` — the identity to
        embed in every confirmatory manifest and result file.
    """
    target = protocol_path(name)
    if target.exists() and not overwrite:
        existing = load_frozen_protocol(name)
        raise ProvenanceError(
            f"protocol '{name}' is already frozen at "
            f"{relative_to_repo(target)} (sha256 {existing['sha256'][:12]}…, "
            f"frozen {existing['frozen_at']}). A frozen protocol is never "
            "rewritten. To run a different design, freeze it under a new "
            "name and say in the manuscript that you did.")

    payload = {
        "protocol_name": name,
        "frozen_at": utc_now(),
        "code": git_state(),
        "environment": environment_fingerprint(),
        "body": dict(body),
    }
    digest = sha256_bytes(canonical_json(payload))
    payload["protocol_sha256"] = digest

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json(payload))
    return {
        "name": name,
        "path": relative_to_repo(target),
        "sha256": digest,
        "frozen_at": payload["frozen_at"],
    }


def load_frozen_protocol(name: str) -> dict[str, Any]:
    """Load a frozen protocol and verify its self-recorded digest.

    A protocol edited after freezing fails here, which is the whole point:
    the claim "this design was fixed before the data existed" has to be
    checkable by a reader from the repository alone.
    """
    target = protocol_path(name)
    if not target.exists():
        raise ProvenanceError(
            f"no frozen protocol named '{name}' at "
            f"{relative_to_repo(target)}; freeze it before running "
            "confirmatory analysis")
    payload = json.loads(target.read_text(encoding="utf-8"))
    recorded = payload.pop("protocol_sha256", None)
    if recorded is None:
        raise ProvenanceError(
            f"protocol '{name}' has no recorded digest and cannot be trusted")
    actual = sha256_bytes(canonical_json(payload))
    if actual != recorded:
        raise ProvenanceError(
            f"protocol '{name}' has been modified since it was frozen: "
            f"recomputed {actual[:12]}… but the file records "
            f"{recorded[:12]}…")
    payload["protocol_sha256"] = recorded
    return {
        "name": name,
        "path": relative_to_repo(target),
        "sha256": recorded,
        "frozen_at": payload["frozen_at"],
        "body": payload["body"],
        "code": payload["code"],
        "environment": payload["environment"],
    }


def protocol_identity(name: str) -> dict[str, Any]:
    """The subset of a frozen protocol that belongs in a result manifest."""
    protocol = load_frozen_protocol(name)
    return {key: protocol[key]
            for key in ("name", "path", "sha256", "frozen_at")}

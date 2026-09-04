"""Tests for content-addressed provenance and protocol freezing.

Covers audit ISSUE-013 (the "frozen" protocol was rewritten by its own runner
on every invocation, with no hash, commit, or timestamp inside it),
ISSUE-014 (manifests recorded no hash of any consumed input or produced
output), and ISSUE-015 (manifest paths were recorded with Windows separators
and were unresolvable on the declared CI runner).

The governing principle under test is **fail loudly**: a provenance layer
that degrades to a warning when an input has changed is worse than none,
because it manufactures confidence in results it can no longer vouch for.
Every verification path here must raise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from grrc import provenance
from grrc.provenance import (
    ProvenanceError,
    build_manifest,
    canonical_json,
    environment_fingerprint,
    freeze_protocol,
    git_state,
    hash_paths,
    load_frozen_protocol,
    protocol_identity,
    protocol_path,
    relative_to_repo,
    sha256_bytes,
    sha256_file,
    verify_manifest,
    write_manifest,
)


@pytest.fixture
def isolated_protocol_dir(tmp_path, monkeypatch):
    """Redirect protocol storage so tests never touch study/protocols."""
    directory = tmp_path / "protocols"
    directory.mkdir()
    monkeypatch.setattr(provenance, "PROTOCOL_DIR", directory)
    return directory


@pytest.fixture
def isolated_repo(tmp_path, monkeypatch):
    """Point manifest path resolution at a scratch tree."""
    monkeypatch.setattr(provenance, "REPO_ROOT", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def test_sha256_file_matches_hash_of_bytes(tmp_path):
    target = tmp_path / "payload.bin"
    payload = b"ransomware simulation raw output\n" * 1000
    target.write_bytes(payload)
    assert sha256_file(target) == sha256_bytes(payload)


def test_canonical_json_is_order_independent():
    a = canonical_json({"b": 2, "a": 1})
    b = canonical_json({"a": 1, "b": 2})
    assert a == b
    assert sha256_bytes(a) == sha256_bytes(b)


def test_canonical_json_is_stable_across_calls():
    payload = {"z": [3, 2, 1], "a": {"nested": True}}
    assert canonical_json(payload) == canonical_json(payload)


def test_relative_paths_are_always_posix(isolated_repo):
    nested = isolated_repo / "data" / "multiobjective" / "raw.csv"
    nested.parent.mkdir(parents=True)
    nested.write_text("x", encoding="utf-8")
    recorded = relative_to_repo(nested)
    assert "\\" not in recorded, (
        "manifest paths must be POSIX; the pre-rebuild manifest recorded "
        "Windows separators that CI could not resolve")
    assert recorded == "data/multiobjective/raw.csv"


def test_environment_fingerprint_records_versions_that_move_numbers():
    fingerprint = environment_fingerprint()
    assert fingerprint["python"]
    for package in ("numpy", "pandas", "scipy"):
        assert package in fingerprint["packages"]


def test_git_state_reports_dirtiness_rather_than_hiding_it():
    state = git_state()
    assert "available" in state
    if state["available"]:
        assert isinstance(state["dirty"], bool)
        assert len(state["commit"]) == 40


def test_hashing_a_missing_file_raises(tmp_path):
    with pytest.raises(ProvenanceError, match="missing file"):
        hash_paths([tmp_path / "absent.csv"])


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

def make_files(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    config = root / "config.yaml"
    config.write_text("mode: test\n", encoding="utf-8")
    result = root / "result.csv"
    result.write_text("a,b\n1,2\n", encoding="utf-8")
    return config, result


def test_manifest_hashes_every_input_and_output(isolated_repo):
    config, result = make_files(isolated_repo / "run")
    manifest = build_manifest(
        run_id="r1", stage="confirmation", description="d",
        inputs=[config], outputs=[result])
    assert len(manifest["inputs"]) == 1
    assert len(manifest["outputs"]) == 1
    assert manifest["inputs"][0]["sha256"] == sha256_file(config)
    assert manifest["outputs"][0]["sha256"] == sha256_file(result)
    assert manifest["inputs"][0]["bytes"] == config.stat().st_size
    assert manifest["code"] and manifest["environment"]
    assert manifest["created_at"].endswith("+00:00")


def test_manifest_rejects_an_unknown_stage(isolated_repo):
    config, result = make_files(isolated_repo / "run")
    with pytest.raises(ValueError, match="unknown stage"):
        build_manifest(run_id="r", stage="whenever", description="d",
                       inputs=[config], outputs=[result])


def test_verify_manifest_passes_on_untouched_files(isolated_repo):
    config, result = make_files(isolated_repo / "run")
    path = write_manifest(
        build_manifest(run_id="r", stage="analysis", description="d",
                       inputs=[config], outputs=[result]),
        isolated_repo / "run" / "manifest.json")
    assert verify_manifest(path)["run_id"] == "r"


def test_verify_manifest_fails_when_an_input_changes(isolated_repo):
    """The whole point: reproduction must fail, not continue quietly."""
    config, result = make_files(isolated_repo / "run")
    path = write_manifest(
        build_manifest(run_id="r", stage="analysis", description="d",
                       inputs=[config], outputs=[result]),
        isolated_repo / "run" / "manifest.json")
    config.write_text("mode: tampered\n", encoding="utf-8")
    with pytest.raises(ProvenanceError, match="sha256"):
        verify_manifest(path)


def test_verify_manifest_fails_when_an_output_is_deleted(isolated_repo):
    config, result = make_files(isolated_repo / "run")
    path = write_manifest(
        build_manifest(run_id="r", stage="analysis", description="d",
                       inputs=[config], outputs=[result]),
        isolated_repo / "run" / "manifest.json")
    result.unlink()
    with pytest.raises(ProvenanceError, match="missing"):
        verify_manifest(path)


def test_manifest_is_written_deterministically(isolated_repo):
    config, result = make_files(isolated_repo / "run")
    manifest = build_manifest(run_id="r", stage="analysis", description="d",
                              inputs=[config], outputs=[result])
    first = write_manifest(manifest, isolated_repo / "a.json").read_bytes()
    second = write_manifest(manifest, isolated_repo / "b.json").read_bytes()
    assert first == second


# ---------------------------------------------------------------------------
# Protocol freezing
# ---------------------------------------------------------------------------

def test_freezing_records_a_verifiable_self_digest(isolated_protocol_dir):
    identity = freeze_protocol("study_v1", {"stage": "confirmation", "n": 150})
    loaded = load_frozen_protocol("study_v1")
    assert loaded["sha256"] == identity["sha256"]
    assert loaded["body"]["n"] == 150
    assert loaded["frozen_at"] == identity["frozen_at"]
    assert protocol_path("study_v1").exists()


def test_a_frozen_protocol_cannot_be_silently_rewritten(isolated_protocol_dir):
    """The pre-rebuild defect: the runner rewrote its own 'freeze' each run."""
    freeze_protocol("study_v1", {"stage": "confirmation", "n": 150})
    with pytest.raises(ProvenanceError, match="already frozen"):
        freeze_protocol("study_v1", {"stage": "confirmation", "n": 999})
    # The original survives the attempt untouched.
    assert load_frozen_protocol("study_v1")["body"]["n"] == 150


def test_editing_a_frozen_protocol_is_detected(isolated_protocol_dir):
    """A protocol edited after freezing must fail to load."""
    freeze_protocol("study_v1", {"stage": "confirmation", "n": 150})
    target = protocol_path("study_v1")
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["body"]["n"] = 20  # a smaller, more convenient study
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with pytest.raises(ProvenanceError, match="modified since it was frozen"):
        load_frozen_protocol("study_v1")


def test_a_protocol_without_a_digest_is_rejected(isolated_protocol_dir):
    target = protocol_path("hand_written")
    target.write_text(
        json.dumps({"protocol_name": "hand_written", "frozen_at": "now",
                    "body": {}}), encoding="utf-8")
    with pytest.raises(ProvenanceError, match="no recorded digest"):
        load_frozen_protocol("hand_written")


def test_loading_a_missing_protocol_says_to_freeze_one(isolated_protocol_dir):
    with pytest.raises(ProvenanceError, match="freeze it before running"):
        load_frozen_protocol("never_frozen")


def test_protocol_identity_is_the_subset_a_manifest_should_carry(
        isolated_protocol_dir):
    freeze_protocol("study_v1", {"stage": "confirmation"})
    identity = protocol_identity("study_v1")
    assert set(identity) == {"name", "path", "sha256", "frozen_at"}
    assert "body" not in identity


def test_overwrite_flag_exists_only_for_tests(isolated_protocol_dir):
    freeze_protocol("study_v1", {"n": 1})
    freeze_protocol("study_v1", {"n": 2}, overwrite=True)
    assert load_frozen_protocol("study_v1")["body"]["n"] == 2


# ---------------------------------------------------------------------------
# The real study protocols in the repository must verify
# ---------------------------------------------------------------------------

def test_every_committed_protocol_verifies():
    """Any protocol in study/protocols must still match its own digest."""
    directory = Path(__file__).resolve().parents[1] / "study" / "protocols"
    if not directory.exists():
        pytest.skip("no frozen protocols committed yet")
    protocols = sorted(directory.glob("*.protocol.json"))
    if not protocols:
        pytest.skip("no frozen protocols committed yet")
    for path in protocols:
        name = path.name.removesuffix(".protocol.json")
        loaded = load_frozen_protocol(name)
        assert loaded["sha256"], name
        assert loaded["body"], name


# ---------------------------------------------------------------------------
# Committed archives
#
# The confirmatory bank is committed gzipped and unpacked before verification.
# For one commit the archive was the superseded 137,600-execution bank while
# the file beside it was the 160,000-execution one, and every check passed:
# the unpack step decided currency by mtime, so in the tree where the study had
# just been re-run it did nothing, and nothing else ever opened the archive.
# A fresh clone would have unpacked the wrong data.
#
# These tests pin the repaired contract: currency is decided by content, and a
# disagreement is an error rather than a silent overwrite in either direction.
# ---------------------------------------------------------------------------

import gzip
import os
import subprocess
import sys

from grrc.utilities import REPO_ROOT


def _run_unpack(root: Path, *args: str) -> subprocess.CompletedProcess:
    """Run scripts/unpack_raw.py against an arbitrary directory as its root.

    The script resolves its own repository root at import time, so the only
    way to exercise it against a fixture tree is to rebind that constant. The
    substitution keeps the module's real body — the point is to test the
    shipped logic, not a copy of it that could drift away from it.
    """
    script = (REPO_ROOT / "scripts" / "unpack_raw.py").read_text(encoding="utf-8")
    substituted = script.replace(
        "from grrc.utilities import REPO_ROOT",
        f"import pathlib\nREPO_ROOT = pathlib.Path({str(root)!r})")
    assert substituted != script, "unpack_raw.py no longer imports REPO_ROOT"
    copy = root / "_unpack_under_test.py"
    copy.write_text(substituted, encoding="utf-8")
    return subprocess.run([sys.executable, str(copy), *args],
                          capture_output=True, text=True, cwd=REPO_ROOT)


def _make_bank(root: Path, csv_bytes: bytes, gz_bytes: bytes) -> Path:
    target = root / "data" / "stage" / "results.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(csv_bytes)
    with gzip.open(target.with_suffix(".csv.gz"), "wb") as sink:
        sink.write(gz_bytes)
    return target


def test_matching_archive_is_left_alone(tmp_path):
    body = b"profile,value\nhigh,1\n"
    target = _make_bank(tmp_path, body, body)
    result = _run_unpack(tmp_path)
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == body


def test_missing_file_is_restored_from_the_archive(tmp_path):
    body = b"profile,value\nhigh,1\n"
    target = _make_bank(tmp_path, body, body)
    target.unlink()
    result = _run_unpack(tmp_path)
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == body


def test_a_stale_archive_is_an_error_not_a_silent_overwrite(tmp_path):
    """The exact defect: archive and file disagree, and neither is trusted."""
    fresh = b"profile,value\nhigh,160000\n"
    stale = b"profile,value\nhigh,137600\n"
    target = _make_bank(tmp_path, fresh, stale)
    result = _run_unpack(tmp_path)
    assert result.returncode == 1
    assert "disagree" in result.stderr
    # The freshly computed bank must survive: overwriting it on a guess would
    # discard hours of compute that cannot be recovered from the repository.
    assert target.read_bytes() == fresh


def test_restore_takes_the_archive_when_told_to(tmp_path):
    fresh = b"profile,value\nhigh,160000\n"
    stale = b"profile,value\nhigh,137600\n"
    target = _make_bank(tmp_path, fresh, stale)
    result = _run_unpack(tmp_path, "--restore")
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == stale


def test_a_mtime_touch_does_not_make_a_stale_archive_look_current(tmp_path):
    """Currency is content, not timestamps. This is what regressed before."""
    fresh = b"profile,value\nhigh,160000\n"
    stale = b"profile,value\nhigh,137600\n"
    target = _make_bank(tmp_path, fresh, stale)
    os.utime(target, (1 << 31, 1 << 31))  # far newer than the archive
    assert _run_unpack(tmp_path).returncode == 1

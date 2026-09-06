# Reproducing the interpretation audit

## Environment and scope

Use Python 3.12 and `requirements-revision.txt` for the new retrospective analysis. Install this package with `pip install -e . --no-deps` after installing that file. On PowerShell activate `.venv/Scripts/Activate.ps1`; on POSIX shells use `source .venv/bin/activate`.

The new run used NumPy 2.3.5 and pandas 3.0.1. The earlier simulation-run pins remain in `requirements.txt` (NumPy 2.5.1 and pandas 3.0.3). Neither this revision nor dependency pinning alone establishes cross-platform byte-identical numerical behavior. We verify original raw-byte hashes and recompute recorded objective summaries within rtol=1e-8, atol=1e-7. The manifests record the actual interpreter, platform, package versions, code and data hashes.

`.gitattributes` disables checkout newline conversion because provenance hashes refer to exact committed bytes. This prevents Windows CRLF conversion from making intact source snapshots appear corrupt.

## Read-only audit

```bash
python scripts/unpack_raw.py
python scripts/run_full_audit.py
```

The harness runs tests, behavioral checks, source verification, protocol and run-manifest verification, current manuscript checks, historical macro cross-checks, and validation reporting. The current manuscript checker independently re-derives generated TeX, checks explicit assertions and citations, and reproduces the old auditor's pass on the archived manuscript. It does not parse arbitrary prose.

```bash
python scripts/audit_interpretation_claims.py
python scripts/generate_interpretation_paper.py --check
```

The finite assertion demonstration has eight correct controls, three known historical contradictions and eight single-field mutations. Invalid assertions fail closed. These are retrospective regression cases, not a held-out accuracy benchmark.

## Regenerate the analysis

Start from a clean, committed checkout with raw files restored. Capture the source state before writing outputs; this avoids a generated output making its own source manifest appear dirty.

```bash
python scripts/analyze_interpretation.py
```

The default uses 1,000 stratified bootstrap draws, seed 2026090601 with successive profile offsets, and 500 heterogeneous weight draws with seed 2026090602. Entry categories are fixed strata (80 scenarios in each of five categories per confirmation profile). Resampling retains all candidate and endpoint pairings. The finite candidate shortlist remains fixed. Initial unstratified diagnostics are preserved in commit 543c5e1 and explicitly superseded by the design correction; the amendment is not disguised as preregistration.

Review and commit regenerated analysis outputs, then generate reporting artifacts:

```bash
python scripts/generate_interpretation_paper.py
```

The scripts reject dirty source trees unless `--allow-dirty` is explicitly supplied for development. Final manifests should record a clean source state. A generated manifest legitimately points to the source commit before the output files were added; it is not expected to point to the commit that contains itself. Its listed source-file hashes permit later changes to be checked.

Historical manifests and their dirty states are not rewritten. The old generated-number manifest is retained for the archived manuscript; current macros and figures use `docs/manuscript/methods_manifest.json`. Historic source identifiers can be translated using `audit/attribution-commit-map.csv`. This preserves evidence, but cannot reconstruct uncommitted historical code.

## Build the PDFs

The paper uses IEEEtran 1.8b with `[conference,compsoc]`, US letter. With Tectonic 0.17.0, from the repository root:

```bash
tectonic --untrusted docs/manuscript/main.tex
tectonic --untrusted docs/manuscript/anonymous.tex
```

Tectonic fetches its TeX bundle on the initial build. No shell escape is required. A standard LaTeX installation with IEEEtran, BibTeX, and the listed packages is an alternative. Inspect the rendered pages as well as the build log; successful TeX compilation alone does not establish readable layout or correct claims.

The anonymous PDF hides author names, affiliation and the identified artifact URL. It is a review draft: an anonymous artifact link/package and author-verified LLM statement remain to be completed before double-blind submission.

## Original simulation pipeline

The [preserved reproduction guide](audit/baseline_manuscript/REPRODUCIBILITY.md) describes discovery, protocol freezing, confirmation, external validation, parameter and structural sensitivity. Existing scripts remain available. This revision does not rerun or alter the original simulator trials and does not treat reanalysis as an independent replication.

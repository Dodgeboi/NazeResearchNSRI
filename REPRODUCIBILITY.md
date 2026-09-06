# Reproducing the final research project

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

The interval-certificate evaluation has its own committed plan and source manifest. After committing any regenerated interpretation results, run it from a clean checkout:

```bash
python scripts/analyze_frontier_certificates.py
```

This uses the unchanged RE21/RE22 Python functions archived from upstream commit 7876b4e465eac381a256e461d1310b8bb2b92846. Candidate sampling uses seed 2026090603 plus problem offsets; perturbations use seed 2026090604 plus successive setting offsets. Every planned radius, including inconclusive settings, is reported. It uses no live download. The independent sorting oracle and exact corner checks test the certificate; they do not validate hospital mechanisms. The retained MIT license and source hashes are in [vendor/reproblems](vendor/reproblems).

Review and commit all regenerated result tables, then generate reporting artifacts:

```bash
python scripts/generate_interpretation_paper.py
```

The scripts reject dirty source trees unless `--allow-dirty` is explicitly supplied for development. Final manifests should record a clean source state. A generated manifest legitimately points to the source commit before the output files were added; it is not expected to point to the commit that contains itself. Its listed source-file hashes permit later changes to be checked.

Historical manifests and their dirty states are not rewritten. The old generated-number manifest is retained for the archived manuscript; current macros and figures use `docs/manuscript/methods_manifest.json`. Historic source identifiers can be translated using `audit/attribution-commit-map.csv`. This preserves evidence, but cannot reconstruct uncommitted historical code.

## Joint stability and external construct audit

From a clean checkout, run:

    python scripts/analyze_joint_stability.py

The default uses 1,000 resamples per profile, seeds 2026090610 through
2026090612, and radii 0, 0.10, 0.25, 0.50, 0.75. Both price regions use
the same draws. The positive-gap extension was recorded after the initial
run in study/JOINT_STABILITY_EXTENSION.md. Every original-region value
reproduces commit 1ddd261 exactly. The separate Hoeffding screen includes
276,048 ordered mean contrasts and all three planned alpha levels.
Per-candidate frequencies and all draw counts are in data/joint_stability.

After committing any regenerated joint results, run the external audit
from a clean checkout:

    python scripts/analyze_cipher_coverage.py

The unchanged CIPHER v1.0.1 CSV and its CC BY 4.0 license are archived
under data/cipher/raw. Its SHA-256 is checked before aggregation. The
script reports all categories, missingness, exact duplicates, the label
correction, and reference influence. No live download is needed.

After committing regenerated analysis tables, run:

    python scripts/generate_interpretation_paper.py
    python scripts/generate_interpretation_paper.py --check

This generator includes the joint-stability and CIPHER tables and central
figure, alongside earlier supplementary graphics. No script silently
stages or commits its outputs.

## Final bound and coefficient comparison

From clean committed source, after restoring the unchanged confirmation bank:

    python scripts/analyze_final_comparison.py

The recorded plan is study/FINAL_COMPARISON_PLAN.md. The calculation compares
Hoeffding, Maurer-Pontil Theorem 11 empirical Bernstein, and approximate
stratified paired t margins at alpha 0.05 for the same 276,048 ordered
mean contrasts. The t method substitutes a Hoeffding margin when estimated
variance is zero and is still labeled approximate. All candidate retention
and baseline comparison rows are released.

For each coefficient and entry stratum, low and high regimes select 26 of
80 scenarios. The 60 regimes retain candidate pairing and equal entry weights.
The 1,000 matched random subsets per profile use seeds 2026090700 through
2026090702, sampling without replacement. These are finite-bank reference
distributions, not confidence intervals or tests. Released membership tables
record actual regime cutoffs through every selected parameter value.

Commit regenerated comparison tables before the final paper generator. It
verifies comparison_manifest.json and generates all additional numeric macros,
tables, coefficient plots, and the explanatory model diagram. The earlier
joint analysis was regenerated after the decimal-price fix and all its CSVs
match release 3.2.0 byte for byte. Original simulation inputs, trial banks,
and frozen protocols remain unchanged.

## Build the PDFs

The paper uses IEEEtran 1.8b with `[conference,compsoc]`, US letter. With Tectonic 0.17.0, from the repository root:

```bash
tectonic --untrusted docs/manuscript/main.tex
tectonic --untrusted docs/manuscript/anonymous.tex
```

Tectonic fetches its TeX bundle on the initial build. No shell escape is required. A standard LaTeX installation with IEEEtran, BibTeX, and the listed packages is an alternative. Inspect the rendered pages as well as the build log; successful TeX compilation alone does not establish readable layout or correct claims.

The anonymous PDF omits author names, affiliation, and the identified artifact URL. It contains the same final research content and concise assistance statement. The public repository and its history remain identified; the PDF alone is an anonymous manuscript copy.

## Original simulation pipeline

The [preserved reproduction guide](audit/baseline_manuscript/REPRODUCIBILITY.md) describes discovery, protocol freezing, confirmation, external validation, parameter and structural sensitivity. Existing scripts remain available. This revision does not rerun or alter the original simulator trials and does not treat reanalysis as an independent replication.

# Reproducible Values, Unstable Conclusions

A retrospective interpretation audit of a synthetic hospital ransomware simulation.

The project now asks how correct, reproducible simulation numbers can support incorrect conclusions about outcome frequency, uncertainty, and portfolio choice. The simulator, original raw trial banks, historical protocols, and earlier model work are preserved. The current paper is a working methods/experience-paper draft, not a validated hospital risk model or a submitted publication.

## Current paper and evidence

- [Named paper](docs/manuscript/main.pdf) and [LaTeX source](docs/manuscript/main.tex)
- [Anonymous review draft](docs/manuscript/anonymous.pdf): manuscript only; an anonymous artifact package is still pending
- [Revision analysis](data/interpretation) and [retrospective plan, including the design amendment](study/INTERPRETATION_ANALYSIS_PLAN.md)
- [Explicit interpretation assertions](study/interpretation_contracts.json)
- [Research positioning and primary sources](docs/manuscript/RESEARCH_POSITIONING.md)
- [Resolved findings and author actions](docs/manuscript/REVISION_REVIEW.md)
- [Preserved preceding manuscript and audit](audit/baseline_manuscript)

The original study evaluates 400 profile-candidates on 400 confirmation scenarios per profile: 160,000 executions, paired across candidates and balanced across five entry categories. The revision resamples whole scenarios within those categories. It adds endpoint and objective sensitivity, conditional shortlist diagnostics, heterogeneous cost/burden stress, covariance-aware comparisons, and a small deterministic assertion evaluator.

The strongest profile's event frequency changes by 14.34 percentage points between k=1 and k=4, even though its estimated Pareto frontier is unchanged. The observed shortlist misses 38 efficient candidates. These are within-model findings; full numerical results and conditional uncertainty are generated into the paper from the committed CSVs.

## Reproduce and verify

Use Python 3.12. The revision environment differs from the historical simulator-run environment; both are preserved and documented.

```bash
python -m venv .venv
# Activate .venv for your shell.
pip install -r requirements-revision.txt
pip install -e . --no-deps
python scripts/unpack_raw.py
python scripts/run_full_audit.py
```

[REPRODUCIBILITY.md](REPRODUCIBILITY.md) explains clean-source generation, hashes, the original pipeline, and PDF compilation. Passing checks means the specified relationships passed; it is not a certificate that every sentence or model assumption is correct.

## Scope

The modeled network has no malware, exploit code, scanning, or connection to real infrastructure. Public evidence constrains context and some incident quantities; it does not identify hospital-specific control effects. Costs and burden are declared normalized points. The model cannot estimate patient harm, months of institutional recovery, or regional disruption. Failed external benchmarks remain reported.

Human author review, contributions, and final disclosure of assistance are pending. No automated tool can supply those attestations. The revision does not claim new independent clinical validation or general claim-checker accuracy.

## Historical work

The [previous README](audit/baseline_manuscript/README.md) records the model rebuild and prior experiments. The [forensic audit](audit/baseline_forensic_report.md), [deviation log](study/DEVIATIONS.md), and archived raw outputs preserve earlier defects and repairs. Older self-scores and narrative interpretations are historical, superseded assessments. Commit metadata was corrected separately; [the attribution map](audit/attribution-commit-map.csv) resolves old source identifiers without changing historical file trees.

Authors: Ashish Agrawal, Mukil Dharanidharan, and Naman Upadhyay. MIT license; see [LICENSE](LICENSE) and [CITATION.cff](CITATION.cff).

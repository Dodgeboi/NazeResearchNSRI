# Multi-objective hospital ransomware defense portfolios

A synthetic, partially calibrated decision model for exploring trade-offs
between hospital cyber-defense portfolios — and, just as importantly, a record
of what it cannot tell you.

The question is narrow: **which defense portfolios stay Pareto-efficient
across mean disruption, tail disruption, sustained clinical outage,
non-recovery, normalized cost, and normalized operational burden, when every
resolved candidate is evaluated on a fresh paired scenario bank under a
protocol frozen beforehand?**

This project is not meant to be an estimate of any hospital's ransomware risk, and it is not
evidence that any control achieves any effect in a real hospital. No internal
transition coefficient in this model is identified by hospital data, and the
repository says so at each parameter rather than once in a limitations
paragraph.

## This version corrects its predecessor

An earlier version of this study reported a six-objective frontier with a
frozen holdout. A full audit — `audit/baseline_forensic_report.md`, with a
machine-readable ledger at `audit/issue_ledger.csv` — found defects severe
enough that those results could not be repaired by re-analysis.

| Defect | Consequence |
|---|---|
| The sustained-outage endpoint was defined in prose as needing four clinical services and computed as needing one | One of six objectives was inverted, propagating into the frontier, the stability estimates, the finalist rule, and every reported outage percentage |
| Per-service outage durations were never written to raw output | The endpoint could not be recomputed at any other service count from the published data, so a fresh run was the only option |
| Capacity profiles were overwritten by portfolios at zero cost | A high-capacity hospital could "buy" flat segmentation and connected backups for nothing; four of seven frozen high-capacity finalists were such free downgrades |
| The holdout frontier ranged over 57 discovery-selected finalists | A candidate that looked mediocre in discovery and excellent on fresh scenarios could not appear |
| The "frozen" protocol was rewritten by its own runner every invocation | Its claim to be prospective could not be checked from the public record, and is not repeated |

**A 70-test suite passed throughout**, because no test asserted the
manuscript's definition of anything. That is the failure this rebuild is
organized around.

Superseded data are retained under
`data/multiobjective/archive_pre_rebuild/`, marked uncitable. Every change,
including one justification that was drafted and then **withdrawn on the
data**, is recorded in [`study/DEVIATIONS.md`](study/DEVIATIONS.md).

## What the model is

A generated directed graph of 200–300 synthetic hospital assets across
workstations, EHR, laboratory, pharmacy, imaging, medical devices,
administration, identity, vendor access, and backup. Nodes move through
healthy, compromised, detected, isolated, restoring, and restored states.
There is no malware, exploit code, scanning, or connection to real
infrastructure.

Seven modeled services depend on core and supporting nodes. **Service
availability is binary at each step**, so the model cannot represent degraded
operation, downtime procedures, or manual workarounds — a limitation that
turns out to drive one of its most notable behaviours.

Capacity profiles are exogenous; portfolios are additive upgrades. Two rules
enforce that, and both were absent before:

- **Upgrade-only precedence.** For every posture ladder, the effective
  setting is the stronger of the profile baseline and the portfolio target.
  A portfolio can raise a profile's posture, never lower it.
- **Increment pricing.** A portfolio is priced on the rungs it actually buys.
  A downgrade costs zero rather than refunding, and a profile is never
  charged for a rung it already has.

Together these guarantee exactly one free candidate per profile — the
profile's own untouched posture — which the test suite asserts.

## What the external validation says

Of nine frozen external benchmarks, **two can be scored**. The rest are
recorded as unaddressable or unscoreable with the structural reason, because
the model has no output of that construct: it runs one facility, over a
72-hour horizon, with binary per-step service availability.

Neither scorable benchmark passes cleanly, and how they fail is the most
useful result here. Against the one directly observed large-scale technical
hospital outage the restoration engine is far too **slow**; against the
ransomware incident record the same engine is far too **fast**, finishing
inside 72 hours where the public distribution has most of its mass beyond a
week. It is anchored to neither. And it assigns probability zero to the
roughly one quarter of observed events that affected more than one hospital.

Those failures are reported, not corrected. The registry
(`study/external_validation_benchmarks.json`) fixes every target and
criterion before any comparison runs, and the runner exits zero when
benchmarks fail, because a failed external check is a finding.

## Repository guide

| Path | Contents |
|---|---|
| [`audit/`](audit) | Forensic baseline report and machine-readable issue ledger |
| [`study/`](study) | Model specification, frozen protocols, deviations, validation registry |
| [`src/grrc`](src/grrc) | Simulator, endpoint registry, provenance layer, analysis |
| [`tests`](tests) | Unit, invariant, capacity, endpoint, provenance, and falsification tests |
| [`configs`](configs) | Frozen configurations |
| [`data/multiobjective/discovery`](data/multiobjective/discovery) | Exploratory bank, precision analysis, config snapshot |
| [`data/multiobjective/confirmatory`](data/multiobjective/confirmatory) | Full-space confirmatory bank and external validation |
| [`data/multiobjective/archive_pre_rebuild`](data/multiobjective/archive_pre_rebuild) | Superseded results, retained and uncitable |
| [`data/observed`](data/observed) | Hash-verified public sources with reuse terms and derived counts |
| [`docs/manuscript`](docs/manuscript) | Paper, generated number macros, bibliography, figures |
| [`docs/evidence`](docs/evidence) | Source map, THREAT reconciliation, assumption audit |

## Run the checks

Python 3.12 or newer. Each exits non-zero on failure.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .

pytest                                   # 165 tests, 1 expected xfail
python scripts/verify_sources.py         # hashes and re-derived counts
python -m grrc.cli validate --no-report  # behavioral checks
```

The expected xfail asserts that an "isolated" backup can still fail, which
the current model does not allow. It is a real defect (ISSUE-006), and the
failing test keeps it visible in every run rather than only in a document.

Full reproduction, including the ~4-hour confirmatory bank, is in
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

## What would actually improve this

Not more simulations. The binding constraint is identification, and it is
relieved only by data this project does not have: de-identified telemetry
from several hospitals, with denominators. Failing that, structured expert
elicitation with calibration questions and pooled uncertainty beats point
estimates that look empirical.

## Manuscript

- [PDF](docs/manuscript/main.pdf) · [LaTeX source](docs/manuscript/main.tex) · [bibliography](docs/manuscript/references.bib)

The manuscript contains **no hand-typed result value**. Every number arrives
through a macro generated from a committed results table, and
`scripts/audit_manuscript_claims.py` fails the build on bare numerals,
orphaned macros, endpoint definitions that disagree with the code, red-line
claims, or missing disclosures.

## AI use

Claude, ChatGPT, and Codex were used for code suggestions, debugging,
organization, literature-search terms, and language revision. An AI system
also performed the audit that identified the defects above and implemented
the corrections, under human direction. AI output was not used as evidence.
Numerical claims are generated from committed data by script, and literature
claims were checked against cited sources. The authors remain responsible for
understanding the model, approving the text, and correcting errors. No AI
system is an author.

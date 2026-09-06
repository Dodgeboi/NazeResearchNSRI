# Defense Portfolio Stability Under Shared Costs and Sampling Uncertainty

**Final research manuscript, version 3.2.0.**

This student research project asks which simulated defense decisions remain
efficient when outcome definitions, shared component prices, and scenario
samples change together. The application is one synthetic hospital network
with pathway-specific controls and six decision objectives.

## Paper and results

- [Final paper](docs/manuscript/main.pdf), [editable source](docs/manuscript/main.tex), and [anonymous copy](docs/manuscript/anonymous.pdf)
- [Joint stability results](data/joint_stability), [analysis plan](study/JOINT_STABILITY_PLAN.md), and [recorded price-region extension](study/JOINT_STABILITY_EXTENSION.md)
- [Public CIPHER construct audit](docs/evidence/CIPHER_COVERAGE.md), [licensed raw dataset](data/cipher/raw), and [processed counts](data/cipher/processed)
- [Original endpoint certificates and witnesses](data/frontier_certificates), [paired interpretation analysis](data/interpretation), and [executable assertions](study/interpretation_contracts.json)
- [Model specification](study/MODEL_SPECIFICATION.md), [evidence parameter register](study/PUBLIC_EVIDENCE_PARAMETER_REGISTER.csv), and [published engineering checks](study/FRONTIER_CERTIFICATE_PLAN.md)
- [Research positioning](docs/manuscript/RESEARCH_POSITIONING.md), [revision record](docs/manuscript/REVISION_REVIEW.md), and [current release status](audit/CURRENT_RELEASE_STATUS.md)

## Main findings

The confirmation experiment contains 400 profile-candidates and 400 scenarios
per profile: 160,000 executions, paired across candidates and balanced across
five entry categories.

1. Changing the outage definition moves high-capacity event frequency by
   14.34 percentage points without changing its observed frontier.
2. Varying only that endpoint guarantees retention of 72 of 95 efficient
   portfolios. Adding ±50% shared cost and burden uncertainty reduces the
   count to 21. Keeping every upgrade at least half as costly as its nominal
   increment raises it to 27, so the decline is not solely a free-upgrade effect.
3. With all four stochastic objectives recomputed from paired stratified
   resamples, 8 or 12 of the original certificates persist in at least 95%
   of draws, respectively. These are conditional frequencies, not confidence levels.
4. A separate simultaneous bounded-mean screen certifies only free baselines:
   two in the broader price region and three with positive upgrade floors
   at ±50% prices. Failure to certify does not establish inefficiency.
5. In CIPHER's 316 coded records from 36 reference links, 85 concern domains
   without an explicit modeled service and 97 have Week 2 or First Month
   annotations. These records identify construct gaps, not recovery durations
   or independent incident rates.

The original structural experiment, 6,000 engineering perturbations, 512
exact corner checks, and historical interpretation corrections remain
available. All findings concern their stated experiments. The model has no
identified hospital control effects or independently validated clinical predictions.

## Reproduce and verify

Use Python 3.12 and the recorded environment:

    python -m venv .venv
    # Activate .venv for your shell.
    pip install -r requirements-revision.txt
    pip install -e . --no-deps
    python scripts/unpack_raw.py
    python scripts/run_full_audit.py

[REPRODUCIBILITY.md](REPRODUCIBILITY.md) gives clean-source generation,
seeds, hash checks, and PDF compilation commands. Original simulator trials
and frozen protocols are preserved. Added analyses are retrospective and
their design notes record when each choice was made.

## Authors, licenses, and history

Authors: **Ashish Agrawal, Mukil Dharanidharan, and Naman Upadhyay**.
AI tools assisted with literature review, code development and revision,
verification, and manuscript preparation.

Project code is MIT licensed. The [benchmark license](vendor/reproblems/LICENSE.txt)
and [CIPHER data license](data/cipher/raw/LICENSE.txt) govern their respective
external materials. See [CITATION.cff](CITATION.cff).

The [archived manuscript](audit/baseline_manuscript), [forensic report](audit/baseline_forensic_report.md),
and [deviation log](study/DEVIATIONS.md) preserve earlier findings and corrections.
Historical checklists and scores describe earlier versions. The
[attribution map](audit/attribution-commit-map.csv) resolves source identifiers
after the earlier metadata-only commit attribution correction.

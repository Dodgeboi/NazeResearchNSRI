# Interpretable Defense Portfolios for Synthetic Hospital Ransomware

**Final research manuscript, version 3.1.0:** *Separating Outcome Sensitivity from Decision Stability.*

This student research project models hospital digital-service disruption and compares defense portfolios across six objectives. It connects an explicit evidence and parameter framework, pathway-specific defense mechanisms, paired simulation, and checks of which portfolio decisions survive changes in assumptions.

## Paper and evidence

- [Final paper](docs/manuscript/main.pdf) and [editable source](docs/manuscript/main.tex)
- [Anonymous manuscript copy](docs/manuscript/anonymous.pdf)
- [Model specification](study/MODEL_SPECIFICATION.md) and [public-evidence parameter register](study/PUBLIC_EVIDENCE_PARAMETER_REGISTER.csv)
- [Interval-certificate results and competing-candidate witnesses](data/frontier_certificates)
- [Published benchmark evaluation plan](study/FRONTIER_CERTIFICATE_PLAN.md) and [archived upstream source and license](vendor/reproblems)
- [Paired interpretation analysis](data/interpretation), [analysis plan and design amendment](study/INTERPRETATION_ANALYSIS_PLAN.md), and [executable assertions](study/interpretation_contracts.json)
- [Research positioning](docs/manuscript/RESEARCH_POSITIONING.md) and [revision record](docs/manuscript/REVISION_REVIEW.md)

## Main findings

The experiment evaluates 400 profile-candidates on 400 confirmation scenarios per profile: 160,000 executions, paired across candidates and balanced across five entry categories.

- Changing the outage-service threshold shifts high-capacity candidate-average event frequency by 14.34 percentage points, while its observed efficient set remains unchanged.
- The interval certificate guarantees retention of **72 of 95 observed efficient portfolios** throughout candidate-specific k=4-to-k=1 endpoint intervals, with five other objectives fixed. All nine high-capacity frontier members remain efficient; seven other candidates could join them.
- Two independently defined engineering problems, RE21 and RE22, provide 6,000 perturbation checks and 512 exact corner matrices. All inclusion checks pass. Five of six settings have no guaranteed candidate, showing when the declared bounds are too broad to certify a particular choice.
- A separate preserved structural experiment changes frontier membership when restoration can precede containment. Endpoint retention does not cover that structural change.
- The frozen shortlist omits 38 efficient candidates in the observed confirmation bank; stratified resampling shows why exact shortlist counts are conditional.

All findings are within the declared experiments. The interval result is a deterministic guarantee for its stated objective box, not a guarantee of clinical effectiveness.

## Reproduce and verify

Use Python 3.12 and the recorded revision environment:

```bash
python -m venv .venv
# Activate .venv for your shell.
pip install -r requirements-revision.txt
pip install -e . --no-deps
python scripts/unpack_raw.py
python scripts/run_full_audit.py
```

[REPRODUCIBILITY.md](REPRODUCIBILITY.md) covers clean-source generation, benchmark seeds, hash checks, and PDF compilation. The original simulator, raw trial banks, and protocols are preserved.

## Scope and history

This is a synthetic research model with declared technical assumptions and normalized cost/burden points. It does not estimate patient harm or identify hospital-specific procurement effects. Failed external comparisons remain reported. The engineering benchmarks use independent published problem definitions but the same evaluation workflow.

The [archived manuscript](audit/baseline_manuscript), [forensic report](audit/baseline_forensic_report.md), and [deviation log](study/DEVIATIONS.md) preserve earlier findings and corrections. Earlier scores and editorial worksheets are historical assessments. The [attribution map](audit/attribution-commit-map.csv) resolves old source identifiers after a metadata-only commit attribution correction.

Authors: **Ashish Agrawal, Mukil Dharanidharan, and Naman Upadhyay**.
AI tools assisted with literature search, manuscript editing, and development and checking of additional analyses.
MIT license; see [LICENSE](LICENSE), the [third-party benchmark license](vendor/reproblems/LICENSE.txt), and [CITATION.cff](CITATION.cff).

# Modeling hospital service disruption during ransomware

We started this project with a question that sounded simple: if the same synthetic hospital network is exposed to the same ransomware-like event, how much difference does a layered set of defenses make?

The answer turned out to be less simple than the first results suggested.

Our model compares a flat reference configuration with a layered portfolio that combines basic segmentation, faster detection and isolation, and protected backups. In a fresh bank of 500 paired scenarios, the layered portfolio produced less modeled service disruption in 451 cases, tied in 48, and performed worse in one. The mean fell from 193.4 to 33.9 weighted service-hours lost.

That is the encouraging part. The important warning is that the size of the benefit changed when we shortened the simulation time step. The direction survived every joint stress setting we tested; the percentage reduction did not. This repository includes that failed numerical check because it changed what we believe the study can honestly claim.

> **Our conclusion:** layered controls were directionally favorable inside this synthetic model. The reported hours and percentages are not estimates of real hospital risk or real control effectiveness.

![Distribution of paired effects. Negative values favor the layered portfolio.](results/figures/fine_step_paired_effect_distribution.png)

## What is being modeled

The simulator generates a directed network of synthetic hospital assets across functions such as workstations, clinical applications, identity, medical devices, administration, vendor access, and backup systems. A node can move through healthy, compromised, detected, isolated, restoring, and restored states.

We measure disruption as service-hours lost across seven modeled services:

- electronic health record
- laboratory
- pharmacy
- imaging
- scheduling
- identity
- backup and recovery

This is a defensive research model. It contains no malware, exploit code, scanning, credentials, or connection to a real network. A “compromised” node is only a state inside a generated graph.

## Main result

| Result | Flat reference | Layered controls |
|---|---:|---:|
| Mean weighted service-hours lost | 193.4 | 33.9 |
| Sustained-outage indicator | 90.2% | 41.2% |
| Paired scenarios | 500 | 500 |

The paired mean change was **-159.5 weighted service-hours** with a 95% bootstrap interval from **-166.1 to -152.7**. These are conditional simulation results. The scenario bank was deliberately severe, and the service thresholds and weights are modeling choices rather than clinical standards.

Across 128 joint stress settings, the layered portfolio had the lower mean every time. The median setting-specific reduction was 28.7%, but the fifth percentile was only 3.1%. That lower tail is one reason we describe the result as directional instead of advertising the largest percentage.

## What went wrong—and why it is included

Our original 15-minute diagnostic contained two design mistakes: time-step variants did not share the same scenario identifiers, and the five-minute rapid-response configuration did not preserve the intended clock time. We retained those files, documented the problem, and reran only the affected diagnostics.

The corrected analysis exposed a deeper issue. Coarser steps gave the layered portfolio fewer propagation rounds before a fixed response time and made the defense look more effective. A new five-minute replication reduced this problem but did not eliminate it. We would move to an event-driven continuous-time model before treating exact hours or percentages as operational estimates.

The reference recovery model also recovered much faster than the multi-week disruptions reported in public studies. We report that mismatch as an external-validity failure.

## How this differs from related work

Hospital ransomware simulation is not a new field, and layered defense is not a new idea. Previous studies have modeled patient flow and recovery strategies, trauma-room processes, financial loss, infrastructure interdependencies, and regional ambulance operations.

Our narrower contribution is the combination of:

- directed within-hospital asset propagation;
- dependencies for seven digital services;
- paired scenarios with event-indexed random values;
- simultaneous stress testing of 13 assumptions;
- independent reconstruction of derived metrics; and
- explicit reporting of the time-step and recovery-duration failures.

The manuscript compares the closest studies directly and avoids claiming to be the first ransomware, hospital-resilience, or segmentation simulation.

## Repository guide

| Path | Contents |
|---|---|
| [`src/grrc`](src/grrc) | Simulator and analysis package |
| [`tests`](tests) | Unit, invariant, paired-design, and behavioral tests |
| [`configs`](configs) | Frozen configurations for the public-evidence and five-minute studies |
| [`study`](study) | Protocols, parameter register, and retained deviations |
| [`data/public_validation`](data/public_validation) | Fifteen-minute validation data and corrected diagnostics |
| [`data/fine_step_replication`](data/fine_step_replication) | Frozen five-minute primary and joint-stress data |
| [`results`](results) | Compact result summaries and figures |
| [`docs/manuscript`](docs/manuscript) | Compiled paper, editable LaTeX, bibliography, and figures |
| [`docs/evidence`](docs/evidence) | Source map, literature-search record, and assumption audit |

## Run the checks

Python 3.11 or newer is required.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS or Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
pytest
python -m grrc.cli validate --no-report
```

The expected result is **56 passing tests** and **12/12 behavioral validation checks**.

## Reproduce the fresh studies

The full study takes considerably longer than the test suite. The configurations, seeds, raw outputs, and processed summaries are already committed so the reported values can be audited without rerunning thousands of simulations.

```bash
# Frozen five-minute replication
python scripts/run_fine_step_replication.py
python scripts/analyze_fine_step_replication.py

# Public-evidence validation and diagnostics
python scripts/run_public_validation.py
python scripts/analyze_public_validation.py

# Independently reconstruct exported metrics
python scripts/audit_derived_metrics.py \
  --raw-dir data/fine_step_replication/raw \
  --output data/fine_step_replication/processed/derived_metric_audit.csv
```

Before rerunning a frozen study, read the matching protocol and [`study/DEVIATIONS.md`](study/DEVIATIONS.md). Do not overwrite retained diagnostic files or combine development, corrected, and replication results.

## Manuscript

- [Read the current PDF](docs/manuscript/main.pdf)
- [Edit the LaTeX source](docs/manuscript/main.tex)
- [Review the bibliography](docs/manuscript/references.bib)
- [Read the originality and author-voice audit](docs/manuscript/ORIGINALITY_AND_VOICE_AUDIT.md)

The manuscript is labeled **pre-external-validation**. Hospital IT, clinical-operations, and simulation reviewers have not yet evaluated the model.

## Data and privacy boundary

All networks and trajectories in this repository are synthetic. The project does not need patient data, credentials, IP addresses, vulnerability details, network diagrams, security logs, or active-incident information. Future expert review should remain at a high level unless an organization independently approves a formal, privacy-protected data-sharing process.

## Authors

Ashish Agrawal, Mukil Dharanidharan, and Naman Upadhyay developed this project together. A detailed contribution statement will be added only after the authors agree on wording that accurately reflects the work.

This is an independent student research project. The repository does not represent or speak for a hospital, employer, or school.

## AI use

Claude, ChatGPT, and Codex were used substantially for code suggestions, debugging, literature-search assistance, analysis checks, organization, and language revision. Their output was not used as evidence. Numerical claims were regenerated from code and CSV files, and literature claims were checked against the cited sources. The authors remain responsible for understanding the model, approving the text, and correcting errors.

## Questions and corrections

You do not need a special project email to contact us. Open a [GitHub issue](https://github.com/Dodgeboi/NazeResearchNSRI/issues) for reproducibility problems, suspected errors, or public methodological questions. Please do not post sensitive hospital or security information.

## License

The software is released under the [MIT License](LICENSE). The manuscript and cited publications retain their respective rights.

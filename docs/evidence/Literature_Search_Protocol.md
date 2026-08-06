# Literature search protocol — draft

## Purpose

Identify empirical studies, simulation models, exercises, and authoritative reports that can inform healthcare ransomware outcomes, model structure, uncertainty ranges, and validation targets. This is a structured evidence search for model development; it should not be called a completed systematic review until the full screening and documentation process is performed.

## Review questions

1. What operational and patient-care effects have been measured during healthcare ransomware or severe IT outages?
2. What healthcare cyberattack or outage simulations have been published, and how were they calibrated and validated?
3. What evidence exists for detection, containment, restoration, service dependency, diversion, and recovery timelines?
4. Which control combinations and failure modes are supported by authoritative healthcare cybersecurity guidance?

## Sources to search

### Scholarly databases

- PubMed/MEDLINE.
- IEEE Xplore.
- ACM Digital Library.
- Scopus or Web of Science if available through school or a library.
- Google Scholar only as a supplementary discovery and citation-tracing tool.

### Authoritative gray literature

- NIST and NCCoE.
- CISA and StopRansomware.gov.
- HHS/ASPR/405(d).
- ENISA.
- National audit offices and public incident investigations.
- Publicly available after-action reports from healthcare organizations or government agencies.

Do not mix guidance documents with empirical studies when rating numerical evidence. Guidance can justify control definitions and mechanisms but usually cannot supply efficacy probabilities.

## Core search concepts

### Concept A: event

`ransomware OR cyberattack OR "cyber attack" OR "information technology outage" OR "electronic health record downtime"`

### Concept B: setting

`hospital OR healthcare OR "health care" OR clinic OR "emergency department" OR "emergency medical services"`

### Concept C: method or outcome

`simulation OR model OR "discrete event" OR "agent based" OR "system dynamics" OR downtime OR disruption OR recovery OR restoration OR diversion OR "patient flow" OR throughput`

## Example database query

`(ransomware OR cyberattack OR "cyber attack") AND (hospital OR healthcare OR "health care") AND (simulation OR model OR downtime OR disruption OR recovery OR "patient flow")`

Adapt controlled vocabulary and syntax for each database. Save every exact query, search date, filter, and result count.

## Date and language scope

- Primary search period: 2016 onward, covering the modern healthcare ransomware period.
- Include older foundational healthcare simulation or cyber-risk modeling papers when directly relevant.
- English-language sources for the initial review; record this as a limitation.

## Inclusion criteria

Include a source if it provides at least one of:

- Empirical operational or patient-care outcomes associated with a healthcare ransomware/cyber incident.
- Incident or exercise timelines relevant to detection, containment, downtime, restoration, or recovery.
- A healthcare cyberattack, IT-outage, service-dependency, or patient-flow simulation with sufficiently described methods.
- An attack-graph, infrastructure-interdependency, or portfolio-optimization method that directly informs the model design.
- Authoritative control or recovery guidance relevant to portfolio definitions or failure modes.

## Exclusion criteria

Exclude from the core evidence set:

- News stories without access to an underlying report or dataset.
- Commentary that supplies no original data, model, or formal guidance.
- Malware-detection classifiers that do not connect to healthcare operations or the model’s research question.
- Offensive exploitation studies unrelated to defensive modeling.
- Duplicate reports of the same study unless one provides additional methods or data.
- Sources whose methods or provenance cannot be evaluated.

## Screening

1. Deduplicate records.
2. Two authors independently screen titles and abstracts.
3. Retrieve full text for potentially eligible sources.
4. Two authors independently make full-text decisions.
5. Resolve disagreements through discussion; use a third reviewer if needed.
6. Record one explicit exclusion reason for every full-text exclusion.

## Data extraction fields

- Full citation and DOI/URL.
- Study type and setting.
- Incident, organization, or simulation population.
- Sample size and observation period.
- Data source.
- Outcomes and operational definitions.
- Numerical estimates and uncertainty.
- Model type, time step, horizon, and unit of analysis.
- Parameter sources and calibration method.
- Verification and validation methods.
- Control or recovery scenarios.
- Limitations, bias, and transferability.
- Potential use in NAZE: context, parameter bound, mechanism, calibration, or held-out validation.

## Evidence-use rules

- Do not convert a reported association into a mechanistic transition probability without a defensible mapping.
- Do not treat guidance as measured effectiveness.
- Do not average heterogeneous incident durations without examining definitions and censoring.
- Prefer ranges or distributions over unsupported point estimates.
- Reserve some incidents or exercises for validation rather than using every source for calibration.
- Record when no defensible evidence exists; use explicit stress tests instead of false precision.

## Citation tracing

For each included scholarly paper:

- Review references for earlier comparable work.
- Review later papers that cite it.
- Search the authors’ related studies and supplementary materials.
- Record how each additional source was found.

## Required search log fields

| Field | Example |
|---|---|
| Database/site | PubMed |
| Date searched | YYYY-MM-DD |
| Exact query | Full copied query |
| Filters | Date, language, document type |
| Results | Number returned |
| Export file | Filename |
| Searcher | Author initials |
| Notes | Syntax changes or problems |

## Completion criteria

The search is ready to support the paper when:

- Every database query and date is recorded.
- Duplicate removal and screening counts are available.
- Full-text exclusion reasons are documented.
- Included sources have complete extraction fields.
- Parameter decisions link to specific evidence records.
- At least one relevant expert checks for obvious missing literature.

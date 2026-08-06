# External validation handoff - stop point

The public-data, software-verification, fresh-simulation, analysis, and
manuscript-revision work is complete. No hospital, employee, expert, or outside
organization has been contacted. This is the agreed stopping point.

## Reviewers needed next

1. A hospital IT or cybersecurity professional who understands segmentation,
   identity, detection, isolation, backups, and restoration.
2. A clinical-operations or patient-safety reviewer who understands what
   degraded EHR, laboratory, pharmacy, and imaging service means in practice.
3. Ideally, a simulation/statistics reviewer who can assess stochastic design,
   time discretization, uncertainty, and validation.

## What to ask them

Ask for high-level face validation, not sensitive architecture details:

- Are the modeled states and sequence of detection, isolation, and restoration
  plausible at this level of abstraction?
- Which service dependencies are missing or misleading?
- Is binary “available/unavailable” too crude, and what degraded-service states
  should exist?
- Which timing ranges are implausible even as stress tests?
- Does “isolated backup” omit important credentials, management planes,
  immutability, testing, reconnection, or reinfection pathways?
- Which outputs would actually inform a tabletop or investment discussion?
- Which claims would they refuse to make from this model?

## What not to request or record

- No real network diagrams, IP addresses, credentials, vulnerabilities, vendor
  weaknesses, or active incident details.
- No patient data, identifiable employee statements, or confidential security
  procedures.
- No claim that a reviewer “validated the model” unless the review method,
  scope, disagreements, and changes are documented.

Before collecting interview data for research, check school, competition,
institutional, privacy, consent, and ethics requirements. Keep reviewer notes
non-sensitive and record dissent rather than forcing consensus.

## Decision after review

Freeze a versioned change log. If reviewers identify structural errors, revise
the model and run another fresh scenario bank. If they judge the abstraction
reasonable, describe the process as face validation only. Empirical predictive
validation would still require suitable withheld incident or exercise data.

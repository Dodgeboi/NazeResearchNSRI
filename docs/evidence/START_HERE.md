# NAZE research upgrade: start here

## What the next study is

The current simulation is a completed exploratory study. The next paper should be a **prospective, evidence-informed validation study**. It should preserve the useful paired Monte Carlo framework while replacing unsupported point assumptions with documented ranges, expert-reviewed scenarios, or explicit stress-test values.

The next paper must not describe the new analysis as preregistered until the protocol is finalized, timestamped, and posted before any new validation results are examined.

## Locked research question

> Which feasible combinations of cybersecurity and recovery controls most consistently preserve modeled healthcare-service availability across evidence-informed ransomware scenarios, and which conclusions remain stable when uncertain assumptions vary?

## Proposed contribution

An auditable paired-simulation workflow for identifying defense portfolios whose comparative benefits remain stable across evidence-based uncertainty. The contribution is the decision method, not a claim that the simulator predicts ransomware risk at a real hospital.

## The first four weeks

### Week 1: evidence and definitions

1. Read the high-priority sources in `Evidence_Source_Map.csv`.
2. Complete missing fields in `Current_Assumption_Audit.csv`.
3. Decide which current parameters can be evidence-informed and which must remain stress-test assumptions.
4. Ask a statistics or simulation mentor to review `Prospective_Validation_Protocol.md`.

### Week 2: expert review

1. Recruit at least one healthcare-IT or clinical-operations reviewer and one cybersecurity or incident-response reviewer.
2. Use `Expert_Review_Guide.md` for a structured 30–45 minute review.
3. Record only non-sensitive, appropriately authorized information.
4. Check school, competition, and research-ethics rules before collecting identifiable interview responses as research data.

### Week 3: model repair and calibration

1. Reconcile the three previously excluded metrics.
2. Add automated invariant tests for every reported metric.
3. Add a separate evidence-informed configuration; do not overwrite the archived exploratory configuration.
4. Freeze the parameter distributions, portfolio definitions, and analysis code.

### Week 4: registration and fresh validation

1. Finalize the protocol and disclose that its hypotheses were informed by the earlier exploratory study.
2. Timestamp or register the protocol before generating fresh validation results.
3. Generate a new scenario bank with new seeds.
4. Run the predeclared analyses without changing the plan after seeing outcomes.

## Immediate decisions for the authors

- Target: science fair/student journal, workshop, or conventional peer-reviewed journal.
- Deadline.
- Whether expert reviewers are available.
- Whether any anonymized operational data can be used legally and ethically.
- Whether the next model will remain asset/service-level or add a patient-flow layer.

## Definition of success

The upgraded study succeeds if another researcher can trace every reported conclusion from: **source or elicitation → parameter distribution → frozen code/configuration → stochastic executions → analysis → manuscript claim**.

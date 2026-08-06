# Prospective validation protocol — draft 0.1

**Project:** Layered ransomware resilience in synthetic healthcare networks
**Status:** Planning draft; not preregistered
**Date:** 2026-08-03
**Relationship to prior work:** The authors have already examined results from the exploratory and confirmatory simulations in the existing repository. This protocol therefore governs a new prospective validation phase. It must not be represented as a preregistration of the already completed analyses.

## 1. Research question

Which feasible combinations of cybersecurity and recovery controls most consistently preserve modeled healthcare-service availability across evidence-informed ransomware scenarios, and which conclusions remain stable when uncertain assumptions vary?

## 2. Study objective

Evaluate whether the comparative advantage of a layered portfolio—segmentation, detection/response, and protected recovery—persists in a newly generated scenario bank whose uncertain inputs are derived from public empirical evidence, structured expert review, or clearly labeled stress-test assumptions.

## 3. Claims the study may and may not support

### Eligible claims

- Comparative differences between modeled portfolios under the declared scenario distribution.
- Sensitivity of rankings to parameter, topology, cost, and outcome assumptions.
- Reproducibility and computational behavior of the proposed workflow.
- Qualitative consistency or inconsistency with held-out incident and exercise patterns.

### Ineligible claims without stronger data

- The probability that a real hospital will experience ransomware.
- The expected duration or clinical harm of a real incident.
- A universal purchasing recommendation.
- Causal effectiveness of a control in deployed hospitals.
- Clinical validation of the two-hour outage or 60% support thresholds.

## 4. Design

Prospective paired Monte Carlo simulation with common random numbers. Within each latent scenario, all portfolios receive the same generated topology, entry point, exogenous event fields, and parameter draw. Only the modeled portfolio changes.

The previous exploratory results will not be pooled with the new validation results. New seeds, a frozen validation configuration, and a versioned analysis manifest will be used.

## 5. Unit of analysis

The primary unit is a latent scenario–portfolio pair. A latent scenario contains one synthetic facility topology, profile-independent evidence-informed parameter draw, entry point, and random event field. Comparisons are paired within scenario.

## 6. Population represented

The model represents abstract healthcare delivery networks, not a statistically representative sample of hospitals. Facility labels will describe synthetic network scales only unless the topology is calibrated to authorized organizational data. Labels such as “small clinic” or “high capacity” will not be treated as real-world categories without supporting evidence.

## 7. Portfolios

### Primary comparator

- Reference posture: frozen evidence-informed baseline configuration.

### Primary intervention

- Affordable layered portfolio: segmentation, improved detection/response, and protected backups/recovery.

### Secondary comparators

- Individual controls.
- Alternative layered portfolios.
- Full-defense stress-test portfolio.

Portfolio contents and costs must be frozen before validation. Normalized cost points are scenario assumptions unless replaced with documented implementation-effort ranges; they are not dollars.

## 8. Outcomes

### Primary outcome

Paired difference in weighted service-hours lost: intervention minus reference. Negative values favor the intervention.

Service weights must be supported by a documented elicitation procedure or tested as uncertain distributions. The analysis will also report unweighted service-specific downtime so that the weighted score does not conceal which services drive a result.

### Secondary outcomes

- Service-specific outage duration.
- Proportion of scenarios with prespecified sustained critical-service outage definitions.
- Recovery within the simulation horizon, treated with appropriate censoring.
- Backup compromise in explicitly defined backup-access scenarios.
- Portfolio rank and probability of ranking first under resampling.
- If a patient-flow layer is added: patient throughput, diversion, waiting time, and process delay.

### Temporarily ineligible outcomes

`pct_compromised`, `pct_clinical_capacity_lost`, and `pct_services_restored` remain ineligible for inferential reporting until their definitions, denominators, terminal-state behavior, and reproducibility tests are fully reconciled.

## 9. Evidence and parameterization

Each influential input will be classified as one of:

1. **Empirically estimated:** derived from a suitable dataset with an uncertainty interval.
2. **Evidence-informed:** range constrained by published incident, exercise, or simulation evidence but not directly estimated for this model.
3. **Expert elicited:** distribution obtained using a documented structured procedure.
4. **Stress-test assumption:** intentionally hypothetical value used to test robustness.

No stress-test assumption will be described as a measured hospital parameter. The decision record will be maintained in `Current_Assumption_Audit.csv`.

## 10. Calibration strategy

1. Extract operational impact and duration evidence from public incidents and healthcare studies.
2. Use authoritative guidance to define plausible controls and failure modes, not numerical efficacy probabilities.
3. Obtain expert review of topology, service dependencies, detection/containment sequence, backup access, and restoration logic.
4. Fit or bound only parameters that the evidence can legitimately inform.
5. Preserve broad uncertainty when sources are heterogeneous or incomplete.
6. Do not tune parameters to reproduce the desired portfolio ranking.

## 11. Validation strategy

### Verification

- Unit and invariant tests for state transitions and every reported metric.
- Extreme-condition tests.
- Seed reproducibility and configuration hashing.
- Independent recomputation of summary statistics from raw outputs.

### Face and structural validity

- Structured review by cybersecurity/incident-response and healthcare-operations experts.
- Document disagreements and resulting changes.
- Verify that modeled dependencies and control failure modes are plausible at the intended abstraction level.

### Empirical pattern validity

Reserve incidents, exercises, or published operational patterns that were not used to set parameters. Evaluate whether the model can reproduce the direction and plausible scale of effects such as service reduction, diversion, spillover, or prolonged recovery. Failure to reproduce a pattern will be reported and investigated rather than hidden.

This is pattern validation, not proof of predictive accuracy.

## 12. Sampling and Monte Carlo precision

A blinded pilot may be used only to estimate variance and runtime. It will not be used to test hypotheses. The number of validation scenarios will be selected before the main run so that:

- Monte Carlo standard error for the primary paired mean difference is no more than 2% of the reference mean disruption; and
- the confidence-interval half-width for the proportion of settings favoring the layered portfolio is no more than 0.03 when feasible.

The calculation and final scenario count will be added to the registered version.

## 13. Primary analysis

1. Compute the within-scenario difference in weighted service-hours lost.
2. Report paired means, medians, proportional reductions, and scenario-clustered bootstrap 95% intervals.
3. Report the distribution of effects rather than only an average.
4. Summarize robustness across frozen parameter settings, including the fifth percentile of proportional improvement and the fraction of settings favoring the intervention.
5. Report absolute outcomes alongside differences, while emphasizing that absolute values are conditional on the model.

The exact success threshold for a “robust” result must be finalized before the validation run. Because the prior study already observed favorable results, the registered protocol will disclose that the hypothesis is informed by earlier findings.

## 14. Secondary and sensitivity analyses

- Alternative horizons and sustained-outage definitions.
- Alternative service weights and functional thresholds.
- Alternative topology families and dependency structures.
- Imperfect isolation and credential/management-plane access to backups.
- Cost distributions and independent cost perturbations.
- Detection-model form and restoration-capacity constraints.
- Analysis with and without individual facility scales.
- Rank uncertainty and held-out portfolio reevaluation.

Exploratory analyses added after registration will be labeled exploratory.

## 15. Missing, censored, and failed runs

- Simulation failures will be logged with configuration, seed, exception, and stage.
- Failed runs will not be silently replaced.
- Recovery time beyond the horizon will be treated as censored rather than as an observed recovery time.
- Any exclusions will be applied by prespecified rules and summarized in a run-accounting table.

## 16. Code and data integrity

- Freeze a tagged code version and environment lock file.
- Publish configuration files, seeds, manifests, raw outputs, and analysis scripts when safe and permitted.
- Generate tables and figures directly from archived analysis outputs.
- Preserve sufficient step-level audit data to reproduce every numerator and denominator.
- Record all post-registration deviations.

## 17. Ethics and safety

The simulation must remain defensive and contain no malware or exploitation tooling. Public incident data will be cited. Before collecting expert or organizational information, the team will follow school, competition, institutional, privacy, and research-ethics requirements. No sensitive network diagram, credential information, vulnerability detail, or identifiable incident-response weakness will be requested or published.

## 18. Reporting standards

The final report will use the STRESS simulation-reporting checklist and clearly separate empirical observations, expert judgments, model assumptions, and simulated outcomes.

## 19. Required approvals before registration

- All authors confirm that they understand every model assumption and analysis.
- Statistics/simulation review completed.
- Cybersecurity review completed.
- Healthcare-operations review completed.
- Parameter register frozen.
- Primary success criterion finalized.
- Sample-size/precision calculation completed.
- Exclusion and deviation rules finalized.

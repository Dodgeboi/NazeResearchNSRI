# Public-evidence validation protocol

**Version:** 1.0
**Frozen:** 2026-08-03, before generation of `data/public_validation`
**Status:** local prospective protocol; not externally preregistered
**Prior knowledge:** the investigators had already seen the exploratory and
confirmatory results in this repository. This is therefore a fresh replication
informed by earlier findings, not a preregistration of the original study.

## Question and claim boundary

We ask whether an affordable layered portfolio (segmentation, faster
detection/response, and protected backups) reduces weighted service-hours lost
relative to a flat reference posture across a fresh, paired scenario bank and
across broad joint uncertainty.

Eligible conclusions concern comparisons within the declared synthetic model.
The study cannot estimate the probability, duration, or patient harm of a real
hospital ransomware incident, prove causal control effectiveness in deployed
hospitals, or justify a universal purchasing recommendation.

## Design

Every comparison uses common random numbers. A latent scenario fixes the
generated topology, entry point, patch draws, and stochastic event field; each
portfolio is then applied to that same scenario. The primary cell is a
200--300-node synthetic network under the intermediate posture. Labels describe
model settings, not classes of real hospitals.

### Primary comparison

- Reference: `baseline_flat`
- Intervention: `seg_detect_backup`
- Secondary: `full_defense`
- Primary outcome: within-scenario difference in weighted service-hours lost
- Primary horizon: 72 modeled hours at 15-minute steps
- Primary sample: 500 paired scenarios

The sample was selected using the earlier confirmatory run only as planning
data. Its paired-difference standard deviation was 73.90 weighted service-hours
and its reference mean was 169.97. The protocol target was a Monte Carlo
standard error no greater than 2% of the reference mean (3.40 hours), giving
`ceil((73.90 / 3.40)^2) = 473`; this was rounded up to 500.

### Replication and robustness

1. Cross-setting replication: 100 scenarios in every combination of three
   neutral network scales and three synthetic postures.
2. Joint uncertainty: 128 Latin-hypercube settings, 20 paired scenarios per
   setting, and the same three portfolios. Mechanistic ranges are stress-test
   ranges, not empirical estimates.
3. Numerical convergence: 5-, 15-, and 30-minute steps after hazard,
   duration, restoration, and threshold conversions that preserve modeled
   clock time.
4. Recovery-horizon sensitivity: 72 hours, 7 days, and 21 days.

## Success and interpretation rules

The layered portfolio will be described as robust only if:

1. its primary paired bootstrap 95% interval lies below zero;
2. it has lower mean weighted service-hours in at least 95% of the 128 joint
   stress settings; and
3. the fifth percentile of setting-specific proportional reduction is above
   zero.

These are computational success rules. Meeting them does not establish
external validity.

## Statistical analysis

- Report paired mean and median differences, percentile bootstrap 95%
  intervals resampling complete scenarios, the fraction of scenarios improved,
  and the distribution of proportional changes.
- For joint uncertainty, average within each parameter setting before
  comparing portfolios. Report the fraction of settings favoring each
  intervention with a Wilson interval and the median and fifth percentile of
  proportional improvement.
- Report absolute outcomes alongside differences but identify them as
  conditional on the model.
- Treat recovery beyond a horizon as right-censored; do not substitute the
  horizon as an observed recovery time.
- Do not use the historical aliases `pct_compromised`,
  `pct_clinical_capacity_lost`, or `pct_services_restored` in new inference.

## Parameter provenance

Public observational studies constrain operational patterns and time windows:
care delivery is often disrupted, acute impacts can last days, recovery may
extend for weeks, and adjacent facilities can experience spillovers. Guidance
identifies relevant controls and failure modes. Neither evidence class provides
a universal per-edge spread probability, isolation-success probability, or
control-effectiveness coefficient for this model. Those inputs therefore remain
broad stress assumptions. The 60% functional threshold, service weights, and
two-hour sustained-outage indicator remain transparent outcome definitions, not
clinical standards.

## Verification and exclusions

All automated unit, reproducibility, and behavioral validation tests must pass
before the run. Each output row records the seed, scenario, configuration
setting, horizon, time step, numerators, and final service flags needed to
recompute reported metrics. Failed runs are logged and are not silently
replaced. Any deviation from this protocol must be dated and described.

## Stop point

This public-data phase ends after code verification, fresh simulation,
analysis, and manuscript revision. External face validation by hospital IT,
incident-response, and clinical-operations reviewers is intentionally not
performed without the authors' authorization and appropriate privacy/ethics
preparation. That review is the next required phase before real-world use or a
strong publication claim.

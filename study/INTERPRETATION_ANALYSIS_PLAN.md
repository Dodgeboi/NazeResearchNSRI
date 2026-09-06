# Retrospective interpretation audit

## Sampling-design amendment (before manuscript generation)

Code inspection after the initial diagnostics confirmed that entry categories
are cycled, not randomly sampled: five strata of 80 scenarios per profile in
confirmation. The final analysis resamples whole scenarios within each
stratum, preserving its size. Mean-difference variance sums within-stratum
variance contributions with squared allocation weights; approximate t
intervals use Satterthwaite degrees of freedom and the same 397-contrast
Bonferroni adjustment. Both matched uncertainty diagnostics preserve this
allocation. Initial unstratified outputs remain in Git commit 543c5e1 and are
superseded. This correction follows the design, not selection of a favorable
outcome. Neither version is independent confirmation. All resampling
references below mean stratified resampling for the final analysis.

This analysis extends the already observed v2 study. It is exploratory and
retrospective, not a new preregistered confirmation. Both external reviews
and the authors' earlier results informed these questions. This document is
committed with the analysis implementation before the expanded outputs are
generated. That records a workflow boundary, not independence from outcomes.

## Scope and questions

Keep the simulator, latent scenario bank, primary k=4 endpoint, and all
historical raw data unchanged. The setting is one synthetic facility, not
an identified hospital population. Analyze the 12,000-trial discovery bank
and 160,000-trial confirmation bank separately.

1. How much does changing the required clinical-service count k alter
   event frequencies and the six-objective frontier within each profile?
2. How do candidate-weighted pooling and equal-profile averaging differ?
3. How does using paired covariance change the previous one-standard-error
   separation diagnostic? This diagnostic is not a significance test.
4. How variable are the full-space frontier and the number of omitted
   candidates when the confirmation scenarios are resampled?
5. How much does frontier membership depend on the number of included
   objectives and on declared component cost/burden weights?
6. Which specified interpretation failures can explicit machine-readable
   assertions detect beyond the original manuscript's number/regex audit?

## Estimands and analysis choices

For each stage/profile, report the mean k=1,...,4 event frequency over the
resolved candidate set. A candidate-average is not an incident prevalence.
The k1-minus-k4 difference is reported in percentage points. Bootstrap
whole scenario IDs, keeping every candidate and endpoint paired; do not
resample the many candidate executions as independent observations.

Use 1,000 bootstrap draws and fixed seed 2026090601. Report conditional
percentile resampling ranges for frontier counts and omitted candidates.
These are not confidence intervals for a uniquely true Pareto set or for
new hospitals; the discovery-selected finalist labels remain fixed.

For mean loss, event frequencies, and non-recovery, compute pairwise SEs
using covariance over shared scenarios. For empirical upper-tail mean
(historical CVaR90 convention: mean at or above the empirical 90th
percentile, including ties), use a shared-scenario bootstrap covariance.
Compare the old and corrected one-SE diagnostics on all four stochastic
objectives. Do not label either diagnostic proof of equality or difference.

Compare every nonfree portfolio against its profile's free baseline on
mean service-hours. Give paired t intervals with Bonferroni coverage across
all 397 candidate-versus-baseline contrasts (alpha=0.05), explicitly noting
the approximate mean-inference assumptions and within-model scope.
Also retain pointwise intervals as descriptive output, clearly labeled.
No observed best portfolio is presented as an unselected hypothesis.

Enumerate all 63 nonempty subsets of the six objectives as a descriptive
dimension ablation. Report distributions by dimension and the four
stochastic objectives plus cost, burden, and both. Do not claim an
independence-based theoretical null for these correlated objectives.

For sensitivity to declared weights, independently multiply each of the
eight cost and eight burden coefficients by Uniform(0.5,1.5) in 500 draws,
using seed 2026090602, keeping these draws shared across candidates and
profiles. Reject tariff draws in which least-privilege segmentation costs
less than basic segmentation or protected backups cost less than periodic
backups, for either cost or burden; report the rejection count. These
ranges are analyst-chosen stress conditions, not a prior
or empirical probability distribution. Preserve each profile's original
budget when reporting affordable membership. Test positive uniform unit
scaling separately: it cannot change Pareto dominance mathematically.

## Interpretation assertions and evaluation

Assertions explicitly identify source, stage, grouping, units, estimator,
comparison, and allowed relation. They check selected factual implications,
not unrestricted natural language or scientific truth. Thresholds attached
to an old statement operationalize that statement for an audit; they are
not new clinical thresholds.

Preserve the original manuscript and claim-audit script. Evaluate known
contradictions and controlled one-change mutations of clean assertions.
Include correct negative controls, exact-boundary cases, missing-data cases,
and unsupported-operation cases. Report detection for this finite,
retrospectively constructed suite; do not estimate sensitivity, specificity,
or performance on unseen papers. Multiple defects in one project are not
independent replications. Further independent review remains necessary.

## Provenance and reporting

Capture source Git state before writing any output. Require clean tracked
inputs/code at the start of final generation, hash the implementation and
raw inputs, preserve the old dirty manifests as historical artifacts, and
record output hashes afterwards. Preserve the original-to-corrected commit
map following the attribution-only history rewrite. Do not rewrite old
timestamps or pretend a new manifest proves when old experiments occurred.

Publish all planned analyses, including null/unstable findings. Document
implementation changes or failed analyses in the deviations log. No
acceptance odds, causal hospital claims, or invented author approvals.

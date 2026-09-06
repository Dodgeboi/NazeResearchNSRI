# Bound comparison and coefficient-conditioned frontier analysis

Recorded on 2026-09-06 after review of release 3.2.0 and before running the
analyses below. This is a retrospective extension. The original scenario bank,
endpoint findings, and shared-price results were already known. No original
protocol or simulation output is replaced.

## Statistical comparison

Compare one-sided Hoeffding, Maurer and Pontil (2009, Theorem 11) empirical
Bernstein, and approximate stratified paired t bounds at family alpha 0.05.
Use the same 276,048 ordered mean contrasts, including all three profiles and
mean loss, worst-endpoint outage difference, and nonrecovery. Use the original
381.6-hour loss bound and binary bounds. The empirical Bernstein calculation
uses pooled paired sample variance; Theorem 11 permits independent observations
with different distributions, as required by the fixed entry allocation.
The t comparison uses within-entry variance and Welch-Satterthwaite degrees of
freedom. When its estimated variance is zero, substitute the Hoeffding margin;
zero observed variance is not proof of a constant population outcome.

Report margins, baseline mean-loss comparisons, and sufficient population
retention under the original population screen at price radii zero and 0.5,
with positive upgrade floors. The t calculation is an approximation, not a
finite-sample certificate. Each method has its own family allocation; choosing
the smallest observed margin across methods is not a joint 95% procedure.
Tail loss remains unrestricted in the sufficient screen. Report all outcomes,
including no additional certificates. Do not assume the new bound is narrow.

## Coefficient-conditioned decisions

Use all ten recorded unidentified coefficients. Within each profile and each
of the five entry categories, select the lowest and highest 26 of 80 coefficient
draws, with stable scenario order for ties. Each regime therefore contains 130
paired scenarios, with equal entry weights. This yields 20 regimes per profile.
Recompute all six original objectives, including the tail with its historical
quantile-and-ties convention, using every candidate. Report frontier Jaccard,
additions, removals, endpoint certificates, and joint certificates at radius 0.5
with positive upgrade floors. Publish regime membership and candidate objectives.

For comparison, draw 1,000 random subsets of 26 scenarios per entry without
replacement (seed 2026090700 plus profile index). Recompute the same statistics.
These subsets describe finite-bank, matched-size variability; their quantiles
and descriptive percentiles are not confidence intervals or hypothesis tests.
The regimes are conditional empirical subsets, not coefficient interventions,
independent hospital evidence, or a guarantee over a joint coefficient box.
Remaining coefficients and stochastic events can differ across subsets.
Nonlinear propagation precludes extending the linear price proof to these
coefficients without a separate argument. Preserve every result, including
weak differentiation from random subsets.

## Software and reporting

Fix decimal tariff boundary cancellation with scale-aware numerical tolerance;
test feasible singleton boxes and genuinely infeasible regions across scales.
Regenerate the existing joint analysis and compare its CSVs with release 3.2.0.
Add independent numerical checks of paired moments and bound formulas. Generate
all new manuscript result values from committed tables, document method limits
once where they matter, and add a diagram checked against the actual node states
and control pathways. Preserve accurate dates and a concise assistance disclosure.

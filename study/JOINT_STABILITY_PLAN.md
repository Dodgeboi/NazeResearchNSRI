# Joint decision stability analysis

Recorded 2026-09-06 before running the additional analyses below. This is a
retrospective extension using the existing confirmation bank, not a new
confirmatory experiment or an independent evaluation. The earlier results
(72 endpoint certificates, 95 nominal efficient candidates, and substantial
tariff sensitivity) were already known when this plan was written.

## Questions and fixed design

1. Which endpoint-retained candidates also survive changes in the *shared*
   component tariffs used to calculate both cost and burden?
2. How do these counts change when all four stochastic objectives are
   recomputed from paired, entry-stratified resamples?
3. Does a conservative simultaneous finite-sample bound support any
   population-level retention claim from the available 400 scenarios?

Use all 288, 96, and 16 candidates, with no shortlist or post hoc exclusions.
Keep original simulations, controls, objective definitions, strata, and
service weights unchanged. Use tariff radii 0, 0.10, 0.25, 0.50, and 0.75.
Each of the eight cost coefficients and eight burden coefficients lies within
its nominal value times [1-radius, 1+radius]. Within each price family,
basic segmentation cannot exceed least-privilege segmentation and periodic
backups cannot exceed protected backups. A coefficient is shared by every
candidate and profile. Cost and burden families vary independently.

For a fixed rival-candidate pair, minimize its cost difference over the
tariff polytope exactly. Do the same independently for burden. Combine these
with the endpoint interval from candidate-specific k=4 to k=1. A candidate
is guaranteed efficient if no rival can weakly improve all six coordinates
and strictly improve at least one. Pairwise minimization is sufficient for
this universal retention question. It does not establish an exact possibly
efficient set under coupled tariffs. Verify price minima with an independent
linear-programming oracle and small frontier instances with enumeration.

Run 1,000 bootstrap draws per profile with seeds 2026090610 + profile index.
Resample 80 scenarios within each of the five entry categories, preserving
candidate pairing and recomputing means, the historical tied upper-tail
statistic, and both endpoint extremes. Apply every tariff radius to the same
draw. Report count distributions and candidate retention frequencies,
including the fate of the original 72 certificates. These frequencies
describe the empirical resampling experiment, not confidence guarantees.

Separately use one-sided Hoeffding bounds at family alpha 0.10, 0.05, 0.01
for the paired differences in mean loss, k=4 rival minus k=1 candidate outage,
and non-recovery. The family includes three quantities for every ordered
distinct candidate pair across all profiles. Loss is bounded by 72 times
the sum of the seven service weights; binary differences lie in [-1,1].
Each alpha defines its own simultaneous family. The bound assumes independent
scenario draws within the declared fixed-stratum experiment, and does not
require independence across candidate comparisons. To certify retention,
every rival must have at least one *strictly worse* coordinate throughout
its lower bounds and tariff support values. This sufficient screen remains
valid for any value of the omitted tail coordinate, including exact ties
in the other coordinates. Report vacuous or baseline-only results plainly.

## Evidence extension and reporting

Inspect version 1.0.1 of the independently authored CIPHER public dataset for
coverage of service disruption and recovery constructs. Record provenance
and inspect its schema before choosing an analysis. It must not be used as
a denominator for population incidence or as control-effectiveness data.
Any quantitative extension will receive a separate design note identifying
what was already inspected. The existing THREAT preview export can support
descriptive event-versus-hospital weighting; its provenance limitation must
remain explicit. Neither source supplies paired defense outcomes.

Report all planned radii and alpha settings, relevant negative findings,
deviations, code/input hashes, and deterministic seeds. Describe established
interval optimization, paired resampling, and concentration inequalities as
prior methods. The contribution sought is an auditable comparison of what
each form of evidence can support in this finite defense decision problem.

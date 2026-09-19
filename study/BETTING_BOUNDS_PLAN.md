# Betting confidence bound and its comparison to the existing bound families

Recorded on 2026-09-19 after release 3.3.0 and before running the analysis
below. This is a retrospective extension. The original scenario bank, endpoint
findings, shared-price results, and the release 3.2.0 bound comparison recorded
in FINAL_COMPARISON_PLAN.md are already known and are not replaced. This note
adds a fourth bound family alongside the three frozen there; it does not edit
that frozen plan or its outputs.

## Motivation

The final comparison reports three one-sided simultaneous margin families over
the paired contrast bank: Hoeffding and Maurer and Pontil (2009) empirical
Bernstein, which are finite-sample valid but use only the range or a pooled
variance, and an approximate stratified paired t, which is tight but only
asymptotically justified. No existing family is at once finite-sample valid and
variance-adaptive. This extension adds a confidence bound by betting
(Waudby-Smith and Ramdas, 2023), which is finite-sample valid, distribution
free, and adapts to the observed variance through a data-driven capital process.

## Method

Rescale a sample of paired differences in [-B, B] to [0, 1]. For a fixed betting
fraction lambda >= 0 and any tested mean m, the capital
K_n(m) = prod_t (1 + lambda (y_t - m)) satisfies K_n(m) <= exp(lambda sum_t
(y_t - m)); its expectation under the hypothesis that the average mean equals m
is therefore at most exp(lambda sum_t (mu_t - m)) = 1, even when the individual
means mu_t differ. Each fixed-fraction product is thus a nonnegative e-value for
the average mean, an average over a fixed grid of fractions is again an e-value,
and by Markov's inequality {m : K_n(m) < 1/a} is a level 1 - a confidence set.
The one-sided lower bound is its infimum, found by bisection because K_n(m) is
decreasing in m.

Because the guarantee holds for independent observations that are not
identically distributed, all paired differences from a profile are pooled; the
five entry categories need no separate treatment. This is the same average mean,
and the same independence-only assumption, that Hoeffding and empirical Bernstein
use. The grid of fractions is fixed in advance: predictability, not any
particular schedule, is what preserves the e-value guarantee, so no data-driven
per-step fraction is used.

## Fixed design

Use the unchanged confirmation bank and the same 276,048 ordered mean contrasts
as FINAL_COMPARISON_PLAN.md: all three profiles, and mean loss, worst-endpoint
outage difference (k4 minus k1), and nonrecovery. Use the original 381.6-hour
loss bound and unit bounds for the two binary endpoints. Family alpha is 0.05,
allocated one-sided across the contrast family by a union bound. The betting
fractions are a fixed geometric grid of fifteen values from 1e-3 to 0.9 (kept
below one so every capital factor stays positive for tested means in [0, 1]),
mixed with equal weight, and the bound is located by 30 bisection steps in the
rescaled mean. Recompute the three existing families on the identical contrasts
and error allocation, so the four are reported side by side. Report margins,
baseline mean-loss comparisons, and sufficient population retention under the
original screen at price radii zero and 0.5 with positive upgrade floors, marking
the betting result finite-sample, unlike the approximate t.

## Scope and limits

The only asserted property is finite-sample one-sided validity. Whether the
betting margin is narrower than empirical Bernstein or than the approximate t is
an empirical outcome reported from the committed tables; it is not assumed. The
bound uses the recorded bank and its stratification and is not a new
concentration theorem, a resampling procedure, or independent hospital evidence.
Tail loss is unrestricted in the sufficient screen, as before. Each family
carries its own allocation; the smallest margin across families is not a joint
95% procedure. Report all outcomes, including any that certify no additional
purchased portfolios.

## Software and reporting

Provide a pure-array kernel with no input or output, validated by an independent
capital-process oracle, by a simulation check that one-sided non-coverage does
not exceed alpha for both identically and non-identically distributed bounded
data, and by rejection of invalid bounds, error allocations, and betting
fractions. Recomputing the analysis on the committed bank must reproduce every CSV
byte for byte. Generate all new manuscript values from the committed tables,
record code and input hashes in a provenance manifest, and state the method's
scope once where it is used.

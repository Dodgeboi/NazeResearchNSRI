# Final revision record

Version 3.3.0, September 6, 2026.

| Review concern | Completed revision |
| --- | --- |
| Decimal prices could make a feasible zero-radius region appear empty | Construct vertices in original coordinates with scale-aware boundary tolerance; regression tests cover decimal singleton regions, true infeasibility, and three scales |
| Hoeffding's range-only margin obscured paired precision | Compare empirical Bernstein and approximate stratified paired t using the same observations, endpoints, family size, and price regions |
| Coefficient sensitivity reported rankings instead of the complete frontier | Recompute every objective and frontier in all 60 low/high coefficient regimes; release membership, objectives, and certificates |
| Smaller conditional subsets could manufacture apparent instability | Compare with 3,000 matched-size random subsets, preserving entry weights and candidate pairing; label the reference as descriptive |
| The strongest outcome-versus-decision finding was buried | Lead the abstract and discussion with the mismatch between frequency changes and frontier changes |
| Model mechanics and mathematical scope were difficult to follow | Add an original model diagram, loss equation, worked interpretation table, all coefficient ranges, and an evidence-scope table |
| The literature lineage was too narrow | Add Bitran, Ide and Schobel, and Maurer-Pontil; retain direct simulation-selection precedents and identify recent preprints explicitly |
| The paper felt compressed | Expand to a full methods treatment with results, figures, and technical appendices; retain accurate research dates and retrospective labels |

## Results of the added analyses

The high-capacity best-versus-baseline margin is 106.32 hours under Hoeffding,
74.31 under empirical Bernstein, and 1.74 under approximate paired t. The
observed benefit is 1.95 hours. Empirical Bernstein does not eliminate its
finite-sample range penalty. At nominal prices, approximate inference supports
12 purchased portfolios in the sufficient population screen; only one remains
under positive-gap 50% price stress. The two finite-sample methods retain
only free baselines in these settings. Approximate findings are labeled and
are not converted into exact guarantees.

Coefficient-regime Jaccards range from 0.535 to 0.815, 0.708 to 1.000, and
0.429 to 1.000 across the resource-constrained, intermediate, and high-capacity
profiles. Six of 60 regimes fall below their matched-size reference's 2.5th
percentile. This is a descriptive comparison across overlapping conditional
subsets, not a multiplicity-adjusted significance test or causal estimate.
Every coefficient, including weak findings, is reported.

## Preservation and status

All five existing joint-analysis CSVs reproduce release 3.2.0 byte for byte
after the decimal fix. The original raw simulation banks, configuration,
frozen protocols, engineering definitions, failed external comparisons, and
historical audit remain preserved. The assistance disclosure remains one
sentence. The final research artifact does not assert a five-month history,
independent clinical validation, author sign-offs, or venue acceptance.
Earlier revision details remain in Git history.

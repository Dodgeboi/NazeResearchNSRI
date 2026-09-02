# Results

## Primary multi-objective study

The paired discovery bank contains 12,960 executions across 432 profile-candidates. Fifty-five candidates were on a point-estimate discovery frontier. The frozen rule admitted 57 finalists to 8,550 fresh paired holdout executions. Forty-nine finalists were non-dominated in holdout, and 46 of 52 tested discovery-frontier candidates survived: 22/28 resource-constrained, 19/19 intermediate-capacity, and 5/5 high-capacity.

No candidate minimized all six objectives. Figures prefixed `multiobjective_` show the held-out frontier, declared benchmark strategies, and discovery-to-holdout survival. Cost and burden are normalized scenario points, not observed economic or staffing quantities.

## Earlier paired replication

The manuscript's main result comes from the frozen five-minute replication:

- 500 paired scenarios;
- reference mean: 193.4 weighted service-hours lost;
- layered mean: 33.9 weighted service-hours lost;
- paired mean change: -159.5 hours;
- 95% bootstrap interval: -166.1 to -152.7;
- lower / tied / higher loss with layered controls: 451 / 48 / 1.

In the 128-setting joint stress analysis, every setting favored the layered portfolio on its mean. The median reduction was 28.7%, but the fifth percentile was 3.1%. That lower tail limits the strength of the conclusion.

The figures in this directory are generated from committed CSV files. Negative values in the paired-effect plot favor the layered portfolio.

These are conditional model results, not measurements of real hospitals or estimates of clinical harm.

Real-world records and their summaries are stored under `data/observed`, not mixed into this simulation-results directory. The main empirical findings used as external checks are 74 ransomware events covering 149 attacked hospital-event records; 30.9% had an emergency-diversion flag, 49.0% had a cancellation/delay flag, and 25.7% of events affected more than one hospital. These endpoints are not numerically interchangeable with modeled service-hours.

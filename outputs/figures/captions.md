# Figure captions

Generated from `standard` mode outputs. All values are simulation outputs under documented model assumptions; none are real-world measurements.

**fig1_network_architecture** — One randomly generated regional-hospital topology (basic segmentation, intermediate-capacity profile). Nodes cluster by zone; stars mark service core nodes; darker lines cross segmentation boundaries. Synthetic model — not a real hospital. Edges subsampled for readability.

**fig2_disruption_by_strategy** — Share of Monte Carlo trials in which at least one clinical service (EHR, laboratory, pharmacy, imaging) experienced any downtime, by defense portfolio and capacity profile (regional hospital, all entry points pooled).

**fig3_patch_detection_heatmap** — Probability that at least one clinical service stays down for more than 8 consecutive steps (2 modeled hours), across the patch-coverage x detection-delay grid (regional hospital, intermediate profile, flat architecture, entry points pooled).

**fig4_pareto_frontier** — Each gray dot is one of 144 candidate defense portfolios evaluated by Monte Carlo simulation; the line joins cost-nondominated portfolios. Dashed lines mark the studied budget levels. Costs are normalized model points, not dollars.

**fig5_facility_comparison** — Mean weighted service-hours lost under each profile's as-is defensive posture (portfolio 'profile_baseline'), by synthetic facility size; error bars are 95% bootstrap CIs of the mean, all entry points pooled.

**fig6_backup_strategies** — Probability that any backup-zone node was compromised, from the CONTROLLED backup experiment: three portfolios identical except for backup connectivity (flat architecture, each profile's own baseline patch/detection), so only the backup strategy varies. Facilities pooled.

**fig7_cost_effectiveness** — Reduction in mean weighted service-hours lost relative to the flat baseline, divided by the portfolio's normalized cost (regional hospital). Costs are model points, not dollars; patch-upgrade costs depend on the profile's starting coverage.

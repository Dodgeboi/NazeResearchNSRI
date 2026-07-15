# Abstract

**Global Ransomware Resilience under Constraint: A Monte Carlo Analysis
of Cybersecurity Defense Portfolios for Healthcare Networks**

Ransomware repeatedly disrupts the hospital services that clinical care
depends on, yet healthcare organizations differ enormously in what they
can spend on defense. We ask which cybersecurity controls buy the most
resilience when an organization cannot afford every defense. Because
experimenting on real hospitals is impossible, we built a fully
synthetic, defensive Monte Carlo simulation: abstract ransomware-style
compromise spreads as a state transition (healthy → compromised →
detected → isolated → restored) across generated healthcare networks of
three sizes (40–1,000 nodes) and three neutral cyber-capacity profiles.
Damage is measured as disruption to seven interdependent critical
services, not infected-machine counts. We compared network
segmentation, patch coverage, detection and isolation speed, identity
restrictions, and backup isolation — alone and combined — across
{{N_TOTAL}} simulation runs, and searched 144 defense portfolios under
fixed budgets, re-testing every conclusion under ±50% cost scaling.
Relative to a flat, unsegmented baseline, the full defense portfolio
reduced weighted service-hours lost by {{REL_RED_FULL_IC}} in
the intermediate-capacity regional hospital (Mann–Whitney
{{FULL_MW_P_IC}}), and isolated backups cut the modeled probability of
backup compromise from {{PBAK_CONNECTED}} to {{PBAK_ISOLATED}}. Under
the tightest budget, the most cost-effective portfolios combined
{{MOST_STABLE_CONTROL}} with other low-cost controls rather than the
single most expensive one. The main limitation is that networks, costs,
and attack mechanics are simplified abstractions: the model identifies
tradeoffs under stated assumptions, not guaranteed real-world outcomes,
and makes no country-level claims. Still, inexpensive, well-chosen
control *combinations* delivered much of the achievable resilience — an
encouraging message for resource-constrained providers.

*Word count target: ≤ 250. Every numeric value above is inserted by
`python -m grrc.cli report` from generated CSV files; any unfilled
double-brace placeholder would mean the corresponding experiment had not
been run yet (none remain in this rendered version).*

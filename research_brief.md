# Global Ransomware Resilience under Constraint
### A Monte Carlo Analysis of Cybersecurity Defense Portfolios for Healthcare Networks

*NSRI Summer Research Hackathon 2026 — Engineering & Technology track.
Numeric results are generated from `standard`-mode simulation outputs
(master seed 20260713, 28,225 total trials) by
`python -m grrc.cli report`. Any remaining double-brace placeholder
would mark a value whose experiment had not been run — values are never
hand-entered (none remain in this rendered version).*

---

## Abstract

See `report/abstract.md` (≤ 250 words), generated from the same outputs.

## 1. Research question

Across simulated healthcare networks of different sizes and
cyber-capacity levels, how do network segmentation, patching, detection
speed, access restrictions, and backup isolation affect
ransomware-style propagation and critical-service disruption — and which
defense combinations give the greatest resilience under limited security
budgets?

## 2. Motivation and global significance

Hospitals run on connected systems: electronic health records (EHR),
laboratory and pharmacy systems, medical imaging, scheduling,
authentication, connected devices, and backups. Ransomware can disrupt
these services, and the disruption — not the encryption itself — is what
threatens patients. Authoritative reporting documents the scale:
ransomware accounts for a majority of analyzed health-sector incidents
in the EU, most of them hitting care providers and hospitals (ENISA,
2023); U.S. ransomware attacks on healthcare delivery organizations more
than doubled from 2016 to 2021 (Neprash et al., 2022); the 2017 WannaCry
event forced English NHS trusts to cancel roughly 19,000 appointments
and operations (National Audit Office, 2018); and federal authorities
have issued sector-specific warnings (CISA/FBI/HHS, AA20-302A, 2020).

Crucially, organizations differ in what they can spend and staff.
National cybersecurity capacity varies widely, with a persistent
"cybercapacity gap" in skills, staffing, and funding across regions
(ITU, 2024). A defense that is trivial for a well-resourced system may
be out of reach for a small clinic. The engineering question is
therefore not "what is the strongest defense?" but **"what is the most
cost-effective defense when you cannot afford everything?"** We study
this with neutral capacity profiles rather than naming countries,
because our synthetic model cannot support country-level claims.

## 3. Method

We built a fully synthetic, **defensive** Monte Carlo simulation. There
is no malware, exploit, scanner, or real system anywhere in the project;
a "compromise" is an abstract state transition (HEALTHY → COMPROMISED →
DETECTED → ISOLATED → RESTORING → RESTORED) on a generated graph. We run
the stochastic process many thousands of times and report the
distribution of outcomes. Full details: `docs/methodology.md`; every
assumption: `docs/assumptions.md`.

## 4. Network and threat model

Each facility is a directed graph. Nodes are devices/systems with a
zone, vulnerability score, patch status, privilege, criticality, and
detection capability; edges are permitted communication paths with an
access strength and an attack-traversal modifier. Ten zones span
workstations, EHR, lab, pharmacy, imaging, medical/IoT devices,
administration, identity, backup, and internet-facing services. Three
facility sizes (small clinic 40–60 nodes, regional hospital 200–300,
large hospital 750–1,000) are **simulation settings, not real-world
claims**. Topology is regenerated every trial so no result depends on
one fixed network. Figure 1 shows one generated regional hospital.

The threat is one ransomware-style intrusion starting at a single
foothold in one of five entry categories (workstation, internet-facing
service, privileged system, medical/IoT device, vendor connection). Each
step, compromised non-isolated nodes attempt lateral movement along
permitted edges with probability
`base_spread × privilege × edge_access × edge_strength × traversal ×
target_vulnerability × patch_factor` (all factors in [0,1]; §A5). The
model represents **no specific ransomware family**.

## 5. Defense scenarios

We model, independently and combined: network segmentation (flat / basic
/ least-privilege), patch coverage (25–90%), detection delay
(1–24 steps) with configurable isolation success and a small
false-positive rate, backup strategy (connected / periodic / isolated),
and identity/access restrictions. Because defensive isolation also
removes nodes from service, the model captures a genuine
**security-versus-availability tradeoff**. Fourteen named portfolios run
in the main experiment, from `baseline_flat` to `full_defense`.

## 6. Experimental design

Main factorial: 3 facilities × 3 profiles × 14 portfolios × 5 entry
points × 25 trials = 15,750 trials. A patch × detection
sweep adds 1,000 trials (Figure 3), a controlled backup-strategy
comparison adds 675 trials (Figure 6), and the budget optimizer
evaluates a 192-combination portfolio lattice per profile — deduplicated
to the distinct configurations reachable from each baseline (10,800
trials). Total:
**28,225 trials**, master seed 20260713; identical seeds
reproduce identical CSVs. Twelve automated validation checks
(`docs/model_validation.md`) confirm the simulation behaves logically
before any result is trusted. The primary outcome is **weighted
service-hours lost**; the pre-registered **catastrophic-disruption**
event is any clinical service down for more than 8
consecutive steps (~2 modeled hours).

## 7. Evidence and results

*All numbers below come from generated CSVs; see `data/processed/`.*

**Effect of defenses vs. the flat baseline (regional hospital).** In the
intermediate-capacity profile, the flat baseline lost a mean of
185.4 weighted service-hours; the full defense portfolio
lost 3.6, a relative reduction of 98.0%
(Mann–Whitney p < 0.001, Cliff's δ = -0.94). The
probability of catastrophic disruption fell from 92.8% to
2.4%. In the resource-constrained profile the same portfolio
moved catastrophic probability from 99.2% to 17.6%
(relative service-hour reduction 95.1%).

**Single controls, ranked (mean reduction in weighted service-hours vs.
flat baseline, regional hospital):**

| Single defense | Mean reduction in weighted service-hours lost vs. flat baseline |
|---|---|
| Least-privilege seg. | 53.3% |
| Basic segmentation | 36.0% |
| Patch 90% | 35.3% |
| Isolated backups | 28.6% |
| Identity controls | 13.1% |

The strongest single control was **Least-privilege seg.**
(53.3% reduction), followed by Basic segmentation
(36.0%). Figure 2 shows disruption probability by
strategy and profile. (The "fast detect + isolate" condition is *not*
listed here: it bundles two controls — faster detection **and** rapid
automated isolation — so it is reported among the multi-control
combinations rather than as a single control.)

**Patch coverage vs. detection speed (Figure 3).** Catastrophic
probability ranged from 100.0% at the worst cell
(75% patch / 24-step delay) to 0.0% at the best
(90% patch / 1-step delay), showing how the two controls trade off.

**Backups (Figure 6).** In a controlled sub-experiment (675
trials) that varied *only* the backup strategy on an otherwise identical
flat network, modeled backup-compromise probability was
75.1% for connected backups, 73.3% for
periodically disconnected, and 0.4% for isolated/immutable
backups — the mechanism by which isolated backups protect recoverability.

## 8. Budget optimization

For each profile and budget we searched every candidate portfolio and
selected the lowest expected disruption (Figure 4 shows the cost–resilience
Pareto frontier; Figure 7 shows service-hours preserved per cost point).

| Profile | Budget | Best portfolio (min expected disruption) | Mean hours lost | P(catastrophic) |
|---|---|---|---|---|
| High-capacity | 5 | segmentation=flat; rapid isolation; backups=connected | 2.6 | 8.0% |
| High-capacity | 10 | segmentation=flat; patch+1 levels; faster detection; backups=connected; identity controls | 2.4 | 0.0% |
| High-capacity | 15 | segmentation=basic; patch+1 levels; faster detection; rapid isolation; backups=isolated | 1.0 | 0.0% |
| Intermediate-capacity | 5 | segmentation=least_privilege; backups=connected | 74.8 | 64.0% |
| Intermediate-capacity | 10 | segmentation=least_privilege; patch+1 levels; faster detection; backups=connected | 5.6 | 4.0% |
| Intermediate-capacity | 15 | segmentation=least_privilege; patch+1 levels; faster detection; rapid isolation; backups=connected | 2.2 | 8.0% |
| Resource-constrained | 5 | segmentation=flat; faster detection; backups=isolated | 153.5 | 96.0% |
| Resource-constrained | 10 | segmentation=least_privilege; patch+1 levels; faster detection; backups=connected | 110.8 | 60.0% |
| Resource-constrained | 15 | segmentation=least_privilege; patch+3 levels; faster detection; backups=connected | 28.9 | 40.0% |

**Minimum budget to reach P(catastrophic) ≤ target:**

| Profile | Min budget (point estimate <= 5%) | Min budget (95% upper bound <= 5%) |
|---|---|---|
| Resource-constrained | not reached in tested space | not reached in tested space |
| Intermediate-capacity | 10 points | not reached in tested space |
| High-capacity | 3 points | not reached in tested space |

The two columns separate a point estimate from a confidence-aware
reading. At 25 trials per portfolio the point estimate is
coarse (4-percentage-point granularity) and optimistic: a portfolio can
post a point estimate at or below the 5% target while its Wilson 95%
upper bound remains well above it. Only the second column supports a firm
"below 5%" claim, and where it reads *not reached*, the target is not
statistically established at this sample size even if a point estimate
appears to meet it.

**Cost sensitivity.** Re-running the optimization at ×0.5–×1.5 costs, we
measured how often each control appears in the min-disruption winner:

| Control | High-capacity | Intermediate-capacity | Resource-constrained |
|---|---|---|---|
| Basic segmentation | 40.0% | 13.3% | 0.0% |
| Least-privilege segmentation | 20.0% | 73.3% | 60.0% |
| Patch upgrade (any level) | 60.0% | 66.7% | 73.3% |
| Detection improvement | 66.7% | 73.3% | 93.3% |
| Rapid isolation | 46.7% | 26.7% | 0.0% |
| Protected backups | 40.0% | 13.3% | 53.3% |
| Identity controls | 20.0% | 0.0% | 20.0% |

The most consistently selected control across all cost scenarios was
**Detection improvement** (77.8% of winning
portfolios), indicating the ranking is not an artifact of the exact
cost numbers.

## 9. Limitations

Networks, costs, and attack mechanics are simplified abstractions
(`docs/limitations.md`): synthetic topologies; normalized non-dollar
costs; a single lateral-movement formula standing in for many
techniques; no modeling of human behavior, data-extortion, or
re-infection; simplified recovery on a 48-hour horizon. Capacity
profiles are neutral parameter bundles, **not** countries or income
groups. The study identifies **modeled tradeoffs under stated
assumptions**, not guaranteed outcomes for any real hospital, and no
defense portfolio should be called universally optimal.

## 10. Conclusion and impact

Within the model, resilience is dominated by **combinations** of
controls, and much of the achievable protection comes from *inexpensive*
controls — isolated backups plus segmentation and faster
detection/isolation — rather than from any single costly measure. That
is an actionable and hopeful message for resource-constrained providers:
the cost-effective frontier, not the maximum-spend portfolio, is where
the leverage is. The open-source simulator lets others change any
assumption and re-derive the tradeoffs for their own context.

## 11. References

See `report/references.md` (all sources manually verified; unverifiable
items are marked `[SOURCE NEEDED]`, never invented).

## 12. AI transparency statement

See `report/ai_transparency.md`.

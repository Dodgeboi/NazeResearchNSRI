# Global Ransomware Resilience under Constraint
### A Monte Carlo Analysis of Cybersecurity Defense Portfolios for Healthcare Networks

*NSRI Summer Research Hackathon 2026 — Engineering & Technology track.
Numeric results are generated from `{{MODE}}`-mode simulation outputs
(master seed {{MASTER_SEED}}, {{N_TOTAL}} total trials) by
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
points × {{N_PER_CELL}} trials = {{N_MAIN}} trials. A patch × detection
sweep adds {{N_SWEEP}} trials (Figure 3), a controlled backup-strategy
comparison adds {{N_BACKUP}} trials (Figure 6), and the budget optimizer
evaluates 144 portfolios per profile ({{N_OPT}} trials). Total:
**{{N_TOTAL}} trials**, master seed {{MASTER_SEED}}; identical seeds
reproduce identical CSVs. Twelve automated validation checks
(`docs/model_validation.md`) confirm the simulation behaves logically
before any result is trusted. The primary outcome is **weighted clinical
service-hours lost**; the pre-registered **catastrophic-disruption**
event is any clinical service down for more than {{CATASTROPHIC_STEPS}}
consecutive steps (~{{CATASTROPHIC_HOURS}} modeled hours).

## 7. Evidence and results

*All numbers below come from generated CSVs; see `data/processed/`.*

**Effect of defenses vs. the flat baseline (regional hospital).** In the
intermediate-capacity profile, the flat baseline lost a mean of
{{BASELINE_HOURS_IC}} weighted service-hours; the full defense portfolio
lost {{FULL_HOURS_IC}}, a relative reduction of {{REL_RED_FULL_IC}}
(Mann–Whitney {{FULL_MW_P_IC}}, Cliff's δ = {{FULL_DELTA_IC}}). The
probability of catastrophic disruption fell from {{CAT_BASE_IC}} to
{{CAT_FULL_IC}}. In the resource-constrained profile the same portfolio
moved catastrophic probability from {{CAT_BASE_RC}} to {{CAT_FULL_RC}}
(relative service-hour reduction {{REL_RED_FULL_RC}}).

**Single controls, ranked (mean reduction in weighted service-hours vs.
flat baseline, regional hospital):**

{{TABLE_SINGLE_DEFENSES}}

The strongest single control was **{{BEST_SINGLE_NAME}}**
({{BEST_SINGLE_RED}} reduction), followed by {{SECOND_SINGLE_NAME}}
({{SECOND_SINGLE_RED}}). Figure 2 shows disruption probability by
strategy and profile.

**Patch coverage vs. detection speed (Figure 3).** Catastrophic
probability ranged from {{SWEEP_WORST_CAT}} at the worst cell
({{SWEEP_WORST_CELL}}) to {{SWEEP_BEST_CAT}} at the best
({{SWEEP_BEST_CELL}}), showing how the two controls trade off.

**Backups (Figure 6).** In a controlled sub-experiment ({{N_BACKUP}}
trials) that varied *only* the backup strategy on an otherwise identical
flat network, modeled backup-compromise probability was
{{PBAK_CONNECTED}} for connected backups, {{PBAK_PERIODIC}} for
periodically disconnected, and {{PBAK_ISOLATED}} for isolated/immutable
backups — the mechanism by which isolated backups protect recoverability.

## 8. Budget optimization

For each profile and budget we searched all 144 portfolios and selected
the lowest expected disruption (Figure 4 shows the cost–resilience
Pareto frontier; Figure 7 shows service-hours preserved per cost point).

{{TABLE_BEST_BUDGET}}

**Minimum budget to reach P(catastrophic) ≤ target:**

{{TABLE_MIN_BUDGET}}

**Cost sensitivity.** Re-running the optimization at ×0.5–×1.5 costs, we
measured how often each control appears in the min-disruption winner:

{{STABILITY_TABLE}}

The most consistently selected control across all cost scenarios was
**{{MOST_STABLE_CONTROL}}** ({{MOST_STABLE_FREQ}} of winning
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

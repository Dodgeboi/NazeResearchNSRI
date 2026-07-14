# Methodology

## 1. Study type

A **Monte Carlo simulation study** on fully synthetic networks. Nothing
in this repository interacts with real systems: the "attack" is an
abstract state-transition process (HEALTHY/VULNERABLE → COMPROMISED →
DETECTED → ISOLATED → RESTORING → RESTORED) on generated graphs. No
malware, exploit code, scanning, or network traffic of any kind exists
in the codebase.

## 2. Research question

Across simulated healthcare networks of different sizes and
cyber-capacity levels, how do network segmentation, patching, detection
speed, access restrictions, and backup isolation affect
ransomware-style propagation and critical-service disruption — and
which defense combinations provide the greatest resilience under
limited security budgets?

## 3. Synthetic network model

Each facility is a directed graph (`network_generator.py`):

* **Nodes** = devices/systems/services with attributes: zone, type,
  vulnerability score (0–1), patch status, criticality weight,
  privilege tier, detection capability, legacy flag, plus runtime state
  and timestamps (compromised/detected/isolated/restored).
* **Edges** = permitted communication paths with attributes: access
  permission, connection strength, direction, segmentation-boundary
  flag, and attack-traversal modifier.
* **Ten zones**: workstations, EHR, laboratory, pharmacy, imaging,
  medical/IoT devices, administration, identity/authentication,
  backup/recovery, internet-facing (assumption A4).
* **Three sizes** (A3): small clinic 40–60 nodes, regional hospital
  200–300, large hospital 750–1,000 — simulation settings, not
  real-world claims.
* **Topology jitter**: every Monte Carlo trial regenerates the graph
  (node counts, edge placement, vulnerability draws, patch assignment)
  from its own RNG stream, so no conclusion depends on one fixed
  network.

Architecture variants differ in which zone→zone pairs are permitted and
how strongly cross-boundary edges are attenuated (A22): *flat* (all
pairs), *basic segmentation* (required paths + convenience paths,
modifier 0.5), *least privilege* (required paths only, modifier 0.25,
extra restriction into identity/backup).

## 4. Threat model (abstract)

The scenario is a single ransomware-style intrusion that begins at one
foothold node (A19) in one of five entry categories: employee
workstation, internet-facing service, privileged system, medical/IoT
device, or third-party vendor connection. Propagation is
epidemic-style lateral movement: at each step every compromised,
non-isolated node attempts to spread along each permitted outgoing
edge with probability

```
p(edge) = base_spread_rate                # A7
        × privilege_modifier(source)      # A20
        × edge_access × edge_strength     # generator draws
        × traversal_modifier              # segmentation/backup, A17/A22
        × vulnerability(target)           # 0–1 draw
        × patch_factor(target)            # 1 or 0.15, A6
```

with all factors in [0,1]. If any identity node is compromised, all
probabilities are multiplied by 1.5 (capped at 1) as a credential-abuse
abstraction (A13). The model deliberately represents **no specific
ransomware family** and no real technique.

## 5. Defense and response model

* **Detection** (A8): geometric per-step detection with configurable
  mean delay (tiers 24/12/6/3/1 steps tested); medical-device and
  legacy nodes are harder to monitor.
* **Isolation** (A9): detected nodes are isolated with per-step success
  probability; rapid automated isolation raises success to 0.95 and
  reacts in the same step. Isolated nodes neither spread nor provide
  service; a small false-positive rate (A10) isolates healthy nodes,
  making over-aggressive response measurable as availability loss.
* **Patching** (A6): coverage levels 25/50/75/90% assign the patched
  flag at generation; patched nodes are 85% less susceptible.
* **Backups** (A17): connected, periodically connected, or fully
  isolated/immutable (no inbound edges — structurally uncompromisable
  via propagation, verified by validation case 4).
* **Identity controls** (A13): halve traversal into the identity zone.
* **Recovery** (A15): begins after containment; restore capacity per
  step is proportional to facility size, sharply reduced if backups
  were lost; core service nodes restore first.

## 6. Critical-service dependency model

Damage is measured in **service availability**, not node counts
(`service_dependencies.py`). Seven services (EHR, laboratory, pharmacy,
imaging, scheduling, identity, backup/recovery) each require: their
core node functional, ≥60% of their supporting nodes functional (A11),
and — for the five identity-dependent services — the identity service
available. Both compromise *and defensive isolation* remove nodes from
service, so the model captures the security-versus-availability
tradeoff explicitly.

## 7. Capacity profiles

Three neutral profiles (A18) — resource-constrained, intermediate-
capacity, high-capacity — bundle patch coverage, detection delay,
isolation success, legacy-node fraction, baseline architecture, backup
strategy, network complexity, and defense budget. They are parameter
settings in YAML, deliberately not mapped to any country or income
group.

## 8. Experiments

1. **Main factorial** — facility (3) × profile (3) × defense portfolio
   (14, from flat baseline to full defense) × entry point (5) ×
   repeated trials. Standard mode: 25 trials/cell = 15,750 trials.
2. **Patch × detection sweep** — 4 coverage levels × 5 delay tiers on
   the regional hospital (Figure 3). Standard: 1,000 trials.
3. **Budget optimization** — all 144 composable portfolios (3
   segmentation tiers × 3 patch boosts × detection × rapid isolation ×
   backup protection × identity controls) evaluated per profile, then
   filtered by budgets 5/10/15 and re-ranked under cost scalings ±25%,
   ±50% (A16). Standard: 10,800 trials. Outputs: best portfolio per
   budget × criterion, Pareto frontier, minimum budget to reach
   P(catastrophic) ≤ 5%, and defense-inclusion stability.

Every output row carries `(master_seed, trial_id)` plus all condition
fields, so any row can be regenerated exactly.

## 9. Outcome metrics

Per trial (see `docs/data_dictionary.md`): technical (nodes
compromised, peak, zones reached, lateral movements, containment time,
backup/identity compromise), service (per-service downtime, weighted
service-hours lost, % clinical capacity lost, catastrophic flag per
pre-registered definition A14, defensive-isolation node-steps),
recovery (recovery step, services restored, simulated unrecoverable
data), and cost-effectiveness at analysis time (service-hours preserved
per cost point, damage reduction vs. flat baseline, minimum budget for
target resilience) plus tail risk (P90/P95, catastrophic probability).

## 10. Statistical analysis

Skewed outcomes → medians, IQRs, P90/P95, and **95% percentile
bootstrap CIs** (2,000 resamples) everywhere; **Mann–Whitney U** with
**Holm correction** and **Cliff's delta** effect sizes for the focused
portfolio-vs-baseline comparisons; **Kruskal–Wallis** across profiles.
Effect sizes and CIs are prioritized over p-values; no normality
assumptions are made.

## 11. Validation and reproducibility

Twelve automated behavioral checks (zero-spread, guaranteed-spread,
disconnected zone, isolated backups, patch immunity, isolation,
reproducibility, seed variation, service dependencies, convergence at
100/250/500/1,000 trials, budget feasibility, data integrity) run via
`python -m grrc.cli validate` and in pytest; results are written to
`docs/model_validation.md`. Seeding uses
`numpy.random.SeedSequence(master_seed, trial_id)`; identical seeds
give bit-identical CSVs. `scripts/reproduce_all.py` reruns the entire
study from a clean checkout.

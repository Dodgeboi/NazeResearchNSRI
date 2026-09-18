# Defense-policy experiments with the GRRC simulator (honest appraisal)

*Follow-on experiments. Reproduce with `python scripts/discover_vgri.py`
(targeting), `python scripts/discover_mvr.py` (recovery), and
`python scripts/discover_adaptive_segmentation.py` (reactive segmentation).
Raw data and summaries in `outputs/vgri/`, `outputs/mvr/`,
`outputs/mvr_robust_full/`, and `outputs/adaptive/`. All figures are
matched-pair comparisons on identical networks and random streams (master seed
20260713), so differences are attributable to the policy alone.*

## Novelty: these are NOT new methods

An explicit check of the literature and industry shows every policy explored
here already exists. We re-implemented them inside this simulator to *measure*
their effect within the model; none is an invention, and we make no novelty
claim.

| Policy tried here | What it already is |
|---|---|
| Reactive / just-in-time segmentation (`adaptive.py`) | Detection-triggered **dynamic microsegmentation** — a mainstream commercial category (Illumio, Zero Networks, Elisity, CrowdStrike) and academic moving-target-defense / RL-segmentation work. |
| Targeted enclaving (VGRI, RPE in `vgri.py`) | Crown-jewel microsegmentation and targeted network **immunization** / graph-cut hardening. |
| Marginal-Value Restoration (`mvr.py`) | Dependency-aware, consequence-minimizing **recovery sequencing**: NIST SP 800-184, Sandia "Optimal Recovery Sequencing for Enhanced Resilience," arXiv:1811.07242, DR/ITSM restoration-order practice, and malware-recovery patents. |

What is legitimately ours is **quantified findings within this model** plus a
reusable, honest evaluation harness (no-op engine seams + matched-pair
experiment design). Those findings follow.

---

## 1. Targeted segmentation (VGRI, RPE): does not beat blunt segmentation

Two targeted refinements of reactive segmentation — throttle only the top
value-ranked links (VGRI) or cut the complete inbound boundary of the
crown-jewel zones (RPE) — were compared against open / always-segmented /
blunt-reactive on 150 matched trials per cell across a 6×4 detection-delay ×
operational-cost grid.

**Finding (negative).** Neither beats the best baseline with a 95% CI clear of
zero in **any** of the 24 cells. VGRI wins 0/24 outright; RPE wins 2/24 (only
the corners where always-on segmentation self-destructs). Mechanism: the damage
metric aggregates *all* services, so blunt full-network containment protects
everything at once, while any targeted/enclave method forfeits protection on
the non-enclaved services — and that forfeited protection roughly cancels the
cost it saves. Partial cuts also simply let a fast spread percolate around the
survivors. See `outputs/vgri/vgri_phase.png`.

Useful conclusion: the *segmentation* lever is not where targeting pays off in
this model.

---

## 2. Reactive segmentation: wins only in a narrow corner

Full detail in [`adaptive_segmentation.md`](adaptive_segmentation.md). In
brief: detection-triggered segmentation beats *both* always-open and
always-segmented (95% CI clear of zero) in only 3 of 24 cells — where detection
is fast (≤3 steps) **and** permanent segmentation is operationally expensive.
Outside that corner, the simple static posture is as good or better. This
matches what dynamic-microsegmentation vendors implicitly assume (fast
detection + costly standing segmentation); the contribution is quantifying the
boundary, not the policy.

---

## 3. Marginal-Value Restoration: works only in a specific regime

MVR restores nodes in order of marginal weighted-service-availability gain
instead of static criticality. It changes only the restoration *sequence*, adds
no availability cost, and has no losing regime.

**Under a mid-containment posture** (`seg_plus_detection`, 200 matched trials):
significantly better in 5/9 facility×profile cells, **never worse anywhere**,
pooled −1.9% weighted service-hours [−1.40, −1.03], with the largest gains
(up to −8.2%) in the small / resource-constrained facilities.
See `outputs/mvr/mvr_comparison.png`.

**But it is not robust across postures.** Re-run under the strong
`full_defense` posture (120 trials, `outputs/mvr_robust_full/`), MVR's pooled
effect is **−0.0%** — significant in only 1/9 cells and negligible in size.
The reason is mechanical: strong defenses keep total damage tiny (means of
0.6–16 service-hours vs. 10–186 under the weaker posture), so almost nothing is
isolated-and-restored and there is no recovery order left to optimize. The
high-capacity profiles are no-ops for the same reason.

**Honest summary of MVR.** It is a *safe, situational* micro-optimization of an
established idea: it never hurts, and it helps a meaningful amount only in the
regime where a moderate defense both (a) isolates and restores enough nodes for
sequencing to bite and (b) still lets the attack do real damage. It is neither
novel nor a broadly reliable win.

---

## 4. Recovery under active spread (RIAR): a large, robust in-model win — but known practice

The base engine restores only after full containment, inheriting the recovery-
sequencing literature's assumption that the disruption is *over* before recovery
begins. Real ransomware recovery is not like that: organizations rebuild while
the intrusion is live, and reimaged machines are routinely re-encrypted. The
opt-in `simulation.concurrent_recovery` flag removes that assumption so
restoration runs during active spread and re-infection becomes possible.

Under that regime we compared four recovery policies on matched networks
(`scripts/discover_riar.py`; moderate posture, detection delay 6, isolation
0.7): `gated` (base contain-then-recover), `naive` (concurrent, criticality
order), `mvr` (concurrent, marginal-value order), and **`riar`** (concurrent,
marginal-value order **plus immunize-on-restore** — a restored node is hardened,
lowering its inbound spread probability by the model's patch effectiveness).

**Finding (positive, robust).** RIAR beats naive concurrent recovery in **9/9**
cells, pooled **−63.4%** weighted service-hours [−86.78, −78.77] (120 trials),
and repeated under fast detection (delay 3): **9/9**, pooled **−60.2%**. It also
beats the conventional `gated` contain-then-recover baseline in essentially
every cell. The mechanism is measured directly: naive concurrent recovery
suffers a re-infection treadmill (mean 273 re-infections), which
immunize-on-restore cuts to 62. Crucially, `mvr ≈ naive` while `riar ≪ both`,
so the win is driven by **immunize-on-restore**, not the ordering. See
`outputs/riar/riar_comparison.png`.

**But it is not novel.** "Harden/patch before reconnecting, because fast
recovery during an active incident causes re-infection" is established
ransomware-recovery best practice (Veeam, SentinelOne, ThreatDown), and
recovery-with-re-infection is the classic SIRS epidemic model with well-studied
treatment/immunization control. RIAR is a faithful *quantification* of that
known practice in this service-weighted model. Its contribution is the
measurement — showing how badly naive concurrent recovery churns and how much
hardening-on-restore recovers — not a new idea. It is also the one result here
that is both large and robust, precisely because it encodes real operational
wisdom the base model omitted.

## Limitations

Single spread and cost model; one simulator. RIAR's magnitude depends on the
modeled patch effectiveness (0.85) and the concurrent-recovery assumption; the
robust, honest claim is directional (naive recovery-during-spread is a
re-infection trap; hardening-on-restore fixes it), not the exact percentage. The targeting negative result is
tied to an aggregate-over-all-services metric; MVR's effect size is tied to the
0.60 availability threshold, the restore rate, and the defensive posture. The
robust, honest claims are directional (targeting the segmentation lever fails;
reactive segmentation helps only in a narrow corner; recovery sequencing is
free but only sometimes matters), not the precise percentages.

## Sources

- NIST SP 800-184, *Guide for Cybersecurity Event Recovery*.
- Sandia National Laboratories, *Optimal Recovery Sequencing for Enhanced
  Resilience* (2013/2021).
- *Generalized network recovery based on topology and optimization*,
  arXiv:1811.07242.
- Commercial dynamic microsegmentation: Illumio, Zero Networks, Elisity,
  CrowdStrike Falcon (product literature).

# Vendor access mediation: control specification, version 1

**Status:** proposed. Not frozen, not run, not in any reported result.
**Scope:** adds one purchasable control to the model specified in
[`MODEL_SPECIFICATION.md`](MODEL_SPECIFICATION.md). Changes nothing about the
entities, the state machine, the transition order, or any endpoint.
**Authority:** where this document and the code disagree, this document is the
specification and the code is the defect — the same rule
`MODEL_SPECIFICATION.md` states for itself.

---

## 0. Why this control exists

The rebuild split edge traversal into three mechanisms so that a control could
act only where it could act (`Pathway.EXPLOIT`, `CREDENTIAL`, `VENDOR`; audit
ISSUE-009, ISSUE-010). Six controls were then priced against those mechanisms.
One mechanism was left with no control on it at all:

| Pathway | Control that acts on it |
|---|---|
| `EXPLOIT` | patch coverage ladder (`patch_effectiveness` 0.85) |
| `CREDENTIAL` | identity controls (coverage 0.85 x effectiveness 0.70) |
| `VENDOR` | **none** |

The gap is not only that patching is weak on the vendor pathway
(`patch_effectiveness_vendor` = 0.25, because the remote side is outside the
estate). It is structural. Vendor-gateway support paths are **exempt from the
segmentation permitted-pair filter**:

    # network_generator.apply_controls_to_base, before this control
    vendor_path = (base.node_type[int(base.edge_src[eid])] == "vendor_gateway"
                   and zb in VENDOR_PATHS)
    permitted[i] = (za, zb) in allowed or vendor_path

So buying least-privilege segmentation does not remove a vendor gateway's path
into medical devices, imaging or administration. `models.HospitalNetwork`
already records the consequence in a docstring — "neither fully on VENDOR" —
and `EntryPoint.VENDOR_CONNECTION` is one of the five entry categories the
confirmatory design balances across, so roughly a fifth of scenarios begin at
a node whose outbound paths no purchasable control could touch.

A decision model whose purpose is to expose trade-offs between portfolios
cannot express a trade-off on a mechanism it prices nothing against. That is
the gap this control fills. It is **not** motivated by a finding, and no result
in the repository is evidence for or against it.

---

## 1. What the control is

**Vendor access mediation.** Third-party access reaches the estate through a
broker — a mediated, scoped, time-boxed session — instead of a standing direct
tunnel. Real programs of this shape combine a jump host or access proxy,
just-in-time rather than persistent authorization, per-session approval, and
session recording.

**Scope, stated as a limit.** The control acts on vendor-gateway *support
paths* only: edges whose source node is a `vendor_gateway` and whose
destination zone is in `VENDOR_PATHS` (medical device, imaging,
administration). It does **not** act on the rest of the internet-facing zone.
A vendor remote-access broker does not mediate the patient portal, and letting
it do so here would credit this control with segmentation's effect.

---

## 2. Mechanism

Let `c` = `vendor_mediation_coverage`, `e` = `vendor_mediation_effectiveness`.

A support path is either **brokered** or not. The number brokered is
`round(c x n_support_paths)`.

**M1 — the segmentation exemption is forfeited.** A brokered path is routed
through the broker, so it is an ordinary cross-boundary edge and the
permitted-pair filter applies to it like anything else. Under least privilege,
a brokered path into medical devices or imaging is therefore *removed*, not
merely weakened.

**M2 — a brokered path that survives the filter is weakened**, traversal
modifier times `(1 - e)`: a scoped session in place of a standing tunnel.

**M3 — brokered-session monitoring (inert by default).** Session recording is
a real part of such a program, so `vendor_mediation_detection_gain` multiplies
detection probability on vendor-gateway nodes. It is **1.0, exactly inert, in
this specification**. Crediting it by default would hand this control the
`detection_improvement` control's effect without paying for it. It exists so a
sensitivity analysis can raise it deliberately.

An unbrokered path receives **nothing**: not M1, not M2, not M3.

### 2.0 A consequence worth stating before anyone reports a number

The existing architecture permits **no** path from the internet-facing zone
into any `VENDOR_PATHS` zone under either basic or least-privilege
segmentation. Only `FLAT` permits them, and it permits all of them. So:

* Above flat, a brokered support path is always *removed*. M1 does all the
  work and M2 never bites.
* Under flat, no brokered path is removed. M2 does all the work and M1 never
  bites.

Vendor mediation and segmentation therefore interact strongly rather than
additively, and the interaction is a property of `REQUIRED_PATHS` and
`BASIC_EXTRA_PATHS` — a declared architecture — **not** an empirical finding
about brokering vendor access. Any reported interaction between these two
controls must say so. `tests/test_vendor_mediation.py` pins this property so
that a later edit to those zone-pair sets cannot quietly change the reading.

### 2.1 Which paths are brokered is deterministic, not drawn

The brokered set is chosen by lowest support-path index, with no random draw.
This is deliberate:

* Whether a vendor relationship *can* be put behind a broker is a property of
  the estate's contracts and device inventory, not of the incident. A per-trial
  draw would make the same hospital brokerable in one scenario and not the
  next.
* In the paired confirmatory design two candidates sharing a scenario must see
  the same estate. A per-candidate draw would break matching, which is the
  whole basis of the paired contrast.

### 2.2 Coverage is below 1.0 by construction

`c` = 0.75 is a **declared assumption**, and it is deliberately not 1.0 for the
same reason `backup_residual_failure` is deliberately not 0.0 (audit
ISSUE-006): a control that completely closed its pathway would be a modeling
artifact, and the optimizer would buy it for that reason rather than for a
mechanism. The uncovered quarter stands for access that is not mediable in
practice — service tunnels contractually required by device vendors, legacy
maintenance protocols, telemetry that will not traverse a proxy, and
break-glass access.

**The residual is where this control's risk concentrates, and it is the part a
reader should attack first.**

---

## 3. Parameters

| Parameter | Value | Status |
|---|---|---|
| `vendor_mediation_enabled` | `false` | master switch; off = control absent |
| `vendor_mediation_coverage` | 0.75 | declared assumption, no validation |
| `vendor_mediation_effectiveness` | 0.60 | declared assumption, no validation |
| `vendor_mediation_detection_gain` | 1.0 | inert in this specification |
| cost | 4 points | normalized, **not** dollars |
| burden | 4 points | normalized scenario points |

Cost 4 sits level with identity controls: both are estate-wide access-path
programs rather than a device or a ladder rung. Burden 4 sits *above* identity
controls' 3 because most of the work is external to the estate — renegotiating
vendor access terms, re-validating device service procedures, and standing up
a break-glass path for the share that cannot be brokered — and therefore is
not on the security team's own schedule.

**No parameter here is identified by hospital data.** Like every other
coefficient in this model, they are declared, and the register in
[`PUBLIC_EVIDENCE_PARAMETER_REGISTER.csv`](PUBLIC_EVIDENCE_PARAMETER_REGISTER.csv)
should record them as such before any result is reported.

---

## 4. Claims this specification forbids

Inheriting the three prohibitions in `MODEL_SPECIFICATION.md` section 0, and
adding four specific to this control:

1. That 0.75 coverage or 0.60 effectiveness is a measured property of any
   vendor-access product, program or deployment.
2. That any simulated reduction is evidence that brokering vendor access
   reduces real hospital ransomware harm.
3. That the control's ranking against the other six reflects anything about
   real procurement priority. It reflects two declared coefficients and a
   declared price.
4. That "vendor access mediation" names a product category. It is an abstract
   control in an abstract model.

---

## 5. Reproducibility guarantee

The control is **inert while `vendor_mediation_enabled` is false**, which is
the default everywhere including `default_config()`. Specifically:

* `enumerate_portfolios()` yields the original **288** candidates, in their
  original order, with their original names. Only mediated candidates carry a
  `|vam1` suffix, so an unmediated candidate's name is unchanged whether or
  not the dimension is on — names are the join key to the frozen result CSVs
  and the protocol snapshots.
* Result-row schema is unchanged: the `vendor_mediation` column is emitted only
  when the switch is on, and is keyed off the run-level config rather than the
  row's portfolio, so a single run never produces a ragged schema.
* `CONTROL_COLUMNS` is frozen at its original seven. Readers use
  `optimization.control_columns(frame)`, which derives the set from the frame,
  so mixed-vintage result files need no special handling.
* `portfolio_features` stays 8-dimensional by default. The simultaneous screen
  is computed over a price region whose dimension is this vector's length;
  widening it to 9 silently would change every published retention count.
* `PORTFOLIO_CATALOG["full_defense"]` deliberately does **not** buy the new
  control. Its frozen meaning is "every control the confirmatory experiment
  priced". `full_defense_mediated` is the all-controls condition.
* Cost and burden files without a `vendor_mediation` key still load. The key is
  optional to *declare* and mandatory to *use*: pricing a portfolio that buys
  the control without a declared tariff raises, rather than silently charging
  zero, which is exactly the free-upgrade defect of audit ISSUE-003/ISSUE-004.

`tests/test_vendor_mediation.py` asserts the inertness properties directly.

---

## 6. What has not been done

* **No experiment has been run.** No result, figure, table or manuscript
  sentence in this repository reflects this control.
* Coverage and effectiveness have had no sensitivity analysis.
* The control has not been through the claim-contract machinery in
  `study/interpretation_contracts.json`.
* The 576-candidate space has not been checked for the labeling honesty
  property that audit ISSUE-005 required of the 288-candidate space: under
  upgrade-only precedence, mediated and unmediated candidates could resolve
  identically for some profile, and `distinct_portfolios_for_profile` must be
  confirmed to prefer the honest label.
* A confirmatory protocol would have to be frozen before any run, per the
  procedure that produced `study/protocols/multiobjective_confirmatory_v2`.

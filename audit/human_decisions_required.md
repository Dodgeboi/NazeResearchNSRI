# Decisions this rebuild deliberately did not make

> Historical rebuild record, superseded for the current release by
> [CURRENT_RELEASE_STATUS.md](CURRENT_RELEASE_STATUS.md). The blocking
> labels and references to a draft below describe that earlier state.
> They are preserved as audit history, not a current release checklist.

The handoff lists choices an AI must not invent. Each is recorded here with
what was assumed in the meantime, so nothing is silently decided by default.
Anything marked **blocking** must be settled before submission.

---

## Authorship and venue

**1. Target journal and fallback. — blocking, and it changes the paper.**
No venue was assumed. The manuscript is written as a computational methods
paper, which fits a simulation-methods or health-informatics venue better
than a security venue, and formatting follows the existing two-column
template rather than any journal's. If the target is a health-services or
medical-informatics journal, the reporting checklist it requires (and
probably a structured abstract) will need to be added. If it is a security
venue, the framing may need to lead with the full-space methodology rather
than the hospital application.

**2. Author list, order, affiliations, CRediT roles, corresponding author. —
blocking.** The existing three names, order and affiliation were carried
forward unchanged from the previous version. The contributions statement
still says roles "must be agreed before submission", which is now overdue:
this rebuild materially changed the study, and who did what needs restating.

**3. AI-use disclosure. — blocking.** The current statement says an AI system
performed the audit that identified the defects and implemented the
corrections under human direction, that its output was not treated as
evidence, that numerical claims are script-generated, and that no AI system
is an author. That is an honest description of what happened. Whether it
satisfies the target journal's current policy is a question only the authors
can answer against that journal's text, and some venues require disclosure in
a specific place or form.

**4. Conflicts, funding, ethics/IRB determination. — blocking, low effort.**
Carried forward as "none" and "no specific funding". All authors should
reconfirm. No IRB determination is asserted; the study used no participants
or patient-level data, but the determination itself is the institution's to
make.

---

## Scope of the science

**5. Multi-facility structure, or an explicit narrowing. — blocking, and it
is the largest open scientific decision.**
The model runs one facility. It therefore assigns probability zero to roughly
a quarter of publicly reported hospital-linked events and cannot address
regional spillover at all — both reported as external-validation failures.
There are two honest resolutions and they lead to different papers:

- *Narrow the scope.* State in the title and abstract that this is a
  single synthetic facility, and drop any implication about multi-facility
  incidents. Cheap, and defensible.
- *Add correlated multi-facility scenarios.* Substantial work, and it makes
  the multi-facility benchmark scoreable rather than failed.

The current draft takes neither cleanly: it reports the failure honestly but
still frames the work at hospital level. This should be decided, not left.

**6. Purely methodological paper, or a stronger applied claim. — blocking.**
The stronger claim would require external collaborators and non-public
telemetry, and the manuscript currently forecloses it. If the authors want an
applied contribution, the framing must change before, not after, submission.

**7. Clinical and security review of declared thresholds. — strongly
recommended.**
The 60% service-functional fraction, the two-hour outage duration, and the
four-service count are declared choices with no clinical validation, and the
paper says so. A clinician or hospital operations reviewer stating whether
they are plausible would convert three declared assumptions into
expert-elicited ones. Nothing in the pipeline can substitute for this.

**8. Cost and burden weights. — strongly recommended.**
Two of six objectives rest on normalized point tables nobody has defended.
They materially shape the frontier. Domain review, or at minimum a
confirmatory cost-scaling sensitivity, would address it.

---

## Resources

**9. Access to clinicians, hospital security staff, or non-public telemetry.**
Assumed unavailable. This is the binding constraint on the whole project: it
is what separates "partially calibrated" from "calibrated", and no amount of
additional simulation substitutes for it. If any such access exists, the
priority order is in the manuscript's "What would actually improve this".

**10. Compute budget and deadline.**
Assumed generous but not unlimited. The confirmatory bank took roughly three
hours on two cores. The largest outstanding item — propagating parameter
uncertainty over the unidentified coefficients — is perhaps an order of
magnitude more compute, and would be the highest-value next spend.

**11. Licensing for new code and data artifacts.**
The repository's existing licence was left unchanged and no licence was
chosen for the new artifacts (protocols, manifests, validation registry).
Archived public sources carry their own terms, recorded per source in the
manifest: CC BY 4.0 for the THREAT deposit, U.S. Government work for the
CISA catalog.

---

## Two decisions this rebuild *did* make, which the authors may want to overturn

Both are flagged because they are judgement calls that changed the study, and
because an author reading only the results would not see that a choice was
made.

**A. The sustained-outage endpoint is k = 4.**
An earlier draft of the specification set k = 2 and argued for it; the
discovery data did not support the argument and it was withdrawn in writing.
k = 4 restores the definition the previous manuscript always stated. Because
the outcome is near-binary, any k gives substantially the same answer, so
this is reversible at no cost — every results table reports all four values.

**B. WP3, the evidence-constrained model redesign, was not attempted.**
Recovery layers, exploit-specific patching, coverage-dependent identity
effects, and nonzero residual failure for isolated backups are all specified
and none is implemented. They are disclosed as defects rather than repaired.
This is the reason the scored rubric reaches 81 rather than the 85–90 target,
and it was a scoping decision, not an oversight. If the authors want the
target score, this is the work.

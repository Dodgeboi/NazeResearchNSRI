# Limitations and Ethics

## Limitations of the model

1. **Synthetic topologies.** Networks are generated from documented
   proportions and access rules (A3–A4, A22); no real hospital network
   diagram was used or approximated. Real facilities differ in
   structure, scale, and heterogeneity.
2. **Abstract, normalized defense costs.** Costs are relative model
   points (A16), not dollar estimates; real prices vary by market,
   vendor, and existing infrastructure. We mitigate — but do not
   eliminate — this with ±25%/±50% cost-sensitivity analysis.
3. **Simplified lateral movement.** One multiplicative probability
   formula (A5) replaces the many distinct techniques real intrusions
   use. The model represents no specific ransomware family and cannot
   capture attacker adaptation, human operators, or zero-day dynamics.
4. **Simplified human behavior.** Clinician workarounds, incident-
   response staffing, decision fatigue, communication failures, and
   paper fallback procedures are not modeled.
5. **Not every ransomware technique.** Data exfiltration/extortion,
   supply-chain compromise, re-infection after restore, and multi-wave
   campaigns are out of scope.
6. **No real hospital is represented.** Outputs are model quantities;
   the simulation does not predict what would happen at any actual
   facility, and results must never be quoted as real-world incident
   statistics.
7. **No country-level conclusions.** Capacity profiles are neutral
   parameter bundles (A18). Mapping them to named countries, regions,
   or income groups would require evidence this study does not have.
8. **Simplified recovery.** Restoration capacity, duration, and
   backup-loss penalties (A15) are stylized; real recovery involves
   forensics, regulatory steps, and vendor dependencies that can take
   far longer than the 48-hour modeled horizon (long recoveries appear
   only as censored rows).
9. **Parameter-range dependence.** Conclusions are conditional on the
   assumptions registry; the sweep and cost-scaling analyses probe the
   most decision-relevant parameters, but a full global sensitivity
   analysis was outside the six-day scope.
10. **Security controls cost availability.** The model includes this
    tradeoff (false positives, isolation downtime, A10), but only
    crudely; real over-blocking harms are broader (e.g., delayed
    logins, broken integrations).
11. **What the results are.** The study identifies *modeled tradeoffs
    and rankings under stated assumptions* — not guaranteed real-world
    outcomes, and not a prescription that any specific hospital should
    follow without local assessment.

## Ethics and safety

* Entirely defensive and simulated: no malware, encryption payloads,
  exploit code, credential tools, scanners, persistence mechanisms, or
  command-and-control functionality exists in this repository; a
  compromise is a boolean flag on a synthetic graph node.
* No confidential, patient, or personal data; no real IP addresses,
  systems, organizations, or network diagrams.
* The work aims to help defenders reason about resource allocation;
  it contains no information that meaningfully assists an attacker
  (the "insight" that flat networks and connected backups are weak is
  standard defensive guidance, e.g., CISA AA20-302A).
* Findings are framed as conditional model results to avoid alarmist
  or misleading claims about real hospitals or countries.

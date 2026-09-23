# Evidence-anchored synthetic hospital

Recorded 2026-09-20. This note upgrades the synthetic hospital from *declared
assumptions* to *citation-anchored ranges*, and records the one structural change:
its attack surface is driven by the real MITRE ATT&CK kill chain
(`data/attack/raw/`, pinned v17.1) rather than an abstract epidemic constant.

It is still a **synthetic** model: real hospital network maps and per-incident
host-level telemetry are not public. "Evidence-anchored" means every parameter
*range* is tied to a real, citable published figure and used as an interval, not a
point --- the honest posture the certificate then propagates. This is a new,
additive artifact; it does not modify the frozen hospital manuscript or its model.

## Structure

| Element | Anchoring | Source |
|---|---|---|
| Ten network zones (workstation, EHR, lab, pharmacy, imaging, medical device, admin, identity, backup, internet-facing) | Zoned hospital-network reference architecture | NIST SP 1800-8 *Securing Wireless Infusion Pumps in HDOs*; reused in SP 1800-24 (PACS) and SP 1800-30 (Telehealth RPM) |
| Segmentation limits lateral movement; sensitive assets on discrete segments | Named control intent | HHS 405(d) HICP; CISA/HHS Cross-Sector & HPH Cybersecurity Performance Goals; CISA HPH RVA AA23-349A |
| Clinical services (EHR, laboratory, pharmacy, imaging) and their dependency on identity | Care-delivery service decomposition | NIST HDO architecture + service-dependency modelling (repo `service_dependencies.py`) |

## Attack surface (structural change)

The adversary progresses along the real ATT&CK enterprise kill chain to the
ransomware **impact** tactic; a control portfolio is a set of real ATT&CK
mitigations, reducing technique success through ATT&CK's own `mitigates` edges
(see `study/CONTROL_CERTIFICATE_PLAN.md`). Which clinical service an impact
technique degrades is a documented mapping (below), not an ATT&CK fact.

| Impact technique | Clinical effect modelled |
|---|---|
| T1486 Data Encrypted for Impact | Records/systems unavailable (encryption) |
| T1490 Inhibit System Recovery | Backups/recovery impaired |
| T1489 Service Stop | Application/service outage |
| T1485 Data Destruction | Data loss |

## Parameter ranges (intervals, with sources)

| Parameter | Anchored range | Basis / source |
|---|---|---|
| Multi-factor authentication effectiveness (identity mitigation, M1032) | 0.85 -- 0.99 | Microsoft: MFA blocks ~99.2% of account-compromise; lower bound reflects AiTM / MFA-fatigue degradation and non-phishing-resistant factors |
| Generic mitigation effectiveness (per ATT&CK mitigation, absent a specific study) | 0.20 -- 0.70 | Wide analyst prior; no transferable per-technique effect size exists |
| Patching effect (exploit pathway) | moderate, wide | "Effect of Security Controls on the Patching Window" (causal, ~2000 orgs; ~9.5-day attributable delay) |
| Adversary progression base success per stage | 0.5 -- 0.9 | Common prior consistent with observed high intrusion-completion once initial access is gained (Mandiant M-Trends 2024; Sophos Active Adversary 2024/25) |
| Time from attack start to impact | days, not hours | Sophos 2024: attack-start to exfiltration median ~3.0 days; Mandiant 2024: global median dwell ~10 days (ransomware often shorter) |
| Probability an impact-capable intrusion degrades a given clinical service | 0.17 -- 0.44 (service-dependent) | Neprash 2022 (JAMA Health Forum): 44% of ransomware attacks disrupted care delivery, 8.6% > 2 weeks; McGlave/Neprash/Nikpay (AEJ:EP 2026): hospital volume drop ~17--26% in the attack week |

## Scope and honesty

- ATT&CK `mitigates` edges are qualitative expert mappings, not measured effect
  sizes; effectiveness stays an interval.
- The impact-technique -> clinical-service mapping and the per-service degradation
  probability are modelling choices anchored to the ranges above, not measured on
  any hospital.
- Progression and dwell figures come from vendor/observational reports (aggregate,
  not microdata) and are used only to justify interval bounds.
- No claim of calibration to, or validation against, any specific hospital.

## Sources

- NIST SP 1800-8 https://www.nccoe.nist.gov/healthcare/securing-wireless-infusion-pumps ; SP 1800-30 https://csrc.nist.gov/pubs/sp/1800/30/final
- HHS 405(d) https://405d.hhs.gov/ ; CISA Cross-Sector CPGs https://www.cisa.gov/cross-sector-cybersecurity-performance-goals ; AA23-349A https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-349a
- Microsoft MFA effectiveness https://www.microsoft.com/en-us/security/blog/2019/08/20/one-simple-action-you-can-take-to-prevent-99-9-percent-of-account-attacks/
- Patching-window causal study https://dl.acm.org/doi/fullHtml/10.1145/3427228.3427271
- Mandiant M-Trends 2024 https://services.google.com/fh/files/misc/m-trends-2024.pdf ; Sophos Active Adversary 2025 https://www.sophos.com/en-us/blog/2025-sophos-active-adversary-report
- Neprash 2022 doi:10.1001/jamahealthforum.2022.4873 ; McGlave/Neprash/Nikpay SSRN 4579292 (AEJ:EP 2026)
- MITRE ATT&CK Enterprise v17.1 (Terms of Use), pinned in `data/attack/raw/`

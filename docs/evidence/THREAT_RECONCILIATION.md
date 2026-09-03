# THREAT cohort reconciliation

**Resolves:** audit ISSUE-018 — "THREAT preview-derived counts unreconciled
with published article totals".
**Data:** `data/observed/raw/threat_database.csv`, SHA-256
`a78291e0b4acd35ef2048230f614f79a83747c043c28b57c05638069da27b536`,
verified against `data/observed/raw/source_manifest.json` at commit
`3b734df` and unchanged since.
**Published source:** Neprash HT et al., *Trends in Ransomware Attacks on US
Hospitals, Clinics, and Other Health Care Delivery Organizations,
2016-2021*, JAMA Health Forum 2022.

The evidence memorandum flagged that the repository's derived counts (149
hospital-event records, 74 events, 25.7% multi-hospital) had to be reconciled
with "the final article's approximately 160 affected hospitals and the
broader THREAT statistic that 198 of 374 healthcare-delivery attacks affected
multiple facilities" before either could be load-bearing. They reconcile
exactly. **The apparent conflict is three different denominators, not a data
error.**

## The three populations

| Population | Count | What one row is |
|---|---:|---|
| All healthcare-delivery ransomware attacks, 2016-2021 | **374** | one attack on any delivery organization: clinic, hospital, dental practice, imaging center, and so on |
| Hospital-linked attack records in the public file | **160** | one Medicare-certified hospital affected by one attack, as recorded |
| Distinct hospital-event records after deduplication | **149** | one unique (Medicare ID, THREAT ID, attack date) triple |

The published article's headline figures are computed on the **374-attack**
population. The repository's derived figures are computed on the
**hospital-linked** subset, which is the only part released in the public
file. Neither can be substituted for the other.

## 160 → 149: what deduplication removes

The file contains 20 rows that are exact repeats of 9 underlying
(Medicare ID, THREAT ID, attack date) triples — seven triples appear twice
and two appear three times. Removing the 11 surplus rows leaves 149.

Verified reproducibly:

```
attacked == 1 rows                    160
duplicated (medicare_id, threat_id, attack_date) rows   20  →  9 unique
records after deduplication           149
distinct Medicare IDs among attacked  148
```

The duplicated rows carry identical `er_diversion` and `cancel_delay` flags,
so deduplication changes no operational count except the denominator. The
article's "approximately 160 affected hospitals" is the **row count before
deduplication**; the repository's 149 is the count after. Both are correct
descriptions of the same file. Because 148 distinct Medicare IDs appear
across 149 records, one hospital was attacked on two separate occasions.

## 25.7% vs. 52.9%: multi-hospital is not multi-facility

These measure different things on different populations and are **not in
conflict**:

| Statistic | Value | Population | Unit of "multiple" |
|---|---:|---|---|
| Published: attacks affecting multiple facilities | 198 / 374 = **52.9%** | all delivery attacks | any facility type |
| Repository: events affecting multiple hospitals | 19 / 74 = **25.7%** | hospital-linked events only | Medicare-certified hospitals |

An attack that hit one hospital and six of its outpatient clinics is
multi-*facility* in the published statistic and single-*hospital* in the
repository's. Multi-hospital is a strict subset of multi-facility, so the
smaller figure is expected. **The 52.9% figure must never be used as the
model's hospital-breadth distribution**, and the 25.7% figure must never be
described as the THREAT multi-facility rate.

## Derived hospital-breadth distribution

Computed from the 74 hospital-linked events:

| Quantity | Value |
|---|---:|
| Events | 74 |
| Single-hospital events | 55 (74.3%) |
| Multi-hospital events | 19 (25.7%) |
| Events affecting ≥ 4 hospitals | 7 |
| Median hospitals per event | 1 |
| Mean hospitals per event | 2.014 |
| Maximum hospitals in one event | 22 |

Operational flags across the 149 records: ambulance diversion 46 (30.9%),
cancellation or delay 73 (49.0%).

**Status: structural check, not a calibration target.** This distribution
describes hospital-linked events that were publicly reported *and* linkable
to a Medicare ID. It is not a random sample of hospital ransomware incidents,
the linkage is incomplete, and a zero flag may mean "not reported" rather
than "did not occur". It is used to check whether the simulator's
single-facility structure is a defensible simplification — it is not, and
that is reported as a failure boundary — never to fit a parameter.

## Published figures verified against secondary reporting

The full text is behind a CAPTCHA gate for automated retrieval, so the
headline figures were cross-checked against independent reporting of the
same study. Every one is consistent with the counts the evidence
memorandum records:

| Figure | Memorandum count | Published as | Consistent |
|---|---|---|---|
| Total attacks | 374 | 374 | ✅ |
| Care disruption | 166 / 374 | "44%" (44.4%) | ✅ |
| Electronic-system downtime | 156 / 374 | 41.7% | ✅ |
| Scheduled care delay or cancellation | 38 / 374 | "10.2%" | ✅ |
| Ambulance diversion | 16 / 374 | "4.3%" | ✅ |
| Disruption exceeding two weeks | 16 + 16 = 32 / 374 | "8.6%" | ✅ |
| Multiple facilities | 198 / 374 | "more than half" (52.9%) | ✅ |

**Remaining action before submission.** The public file is a normalized
export of the browser preview, because downloading the original openICPSR
deposit requires sign-in. The original file and its codebook should replace
this copy before submission, and this reconciliation should be re-run
against it. The SHA-256 above pins exactly what was analyzed in the
meantime, so any substitution is detectable.

**Interval censoring.** Of the 374 attacks, 67 had known disruption of
unknown duration and are excluded from the duration bins. That missingness is
plausibly informative — longer or more severe incidents may be less likely to
have a cleanly reported end date — so any recovery-class model fitted to
these bins must test the missingness assumption rather than dropping those
events silently.

## Sources

- [Trends in Ransomware Attacks on US Hospitals, Clinics, and Other Health Care Delivery Organizations, 2016-2021 (JAMA Health Forum)](https://jamanetwork.com/journals/jama-health-forum/fullarticle/2799961)
- [ASPR TRACIE resource record for the same study](https://asprtracie.hhs.gov/technical-resources/resource/12127/trends-in-ransomware-attacks-on-us-hospitals-clinics-and-other-health-care-delivery-organizations-2016-2021)
- [Fierce Healthcare reporting of the study's figures](https://www.fiercehealthcare.com/health-tech/new-jama-study-scrapes-dark-web-find-true-frequency-healthcare-ransomware-attacks)
- [openICPSR replication deposit, DOI 10.3886/E235483V1](https://www.openicpsr.org/openicpsr/project/235483/version/V1/view)

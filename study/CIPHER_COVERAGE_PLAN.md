# External construct coverage, recorded before aggregation

The version 1.0.1 CIPHER archive (Zenodo DOI 10.5281/zenodo.17344644)
was retrieved on 2026-09-06. Before this note, we inspected its README,
license, citation file, CSV shape (316 rows, 9 columns), first two rows,
and distinct time, specialty, and technical-domain labels. We did not
inspect domain or time counts or source-level distributions. This is an
exploratory construct audit of an independently authored dataset, not a
prospective validation experiment.

Preserve the CSV bytes and archive identity. Strip surrounding whitespace
in text fields for analysis. Count exact duplicate rows separately; report
results on all records and after exact-row deduplication. A source means
a distinct nonmissing Reference Link after whitespace and trailing-slash
normalization. Different links may describe the same incident, and a single
source may contribute several coded records. Neither rows nor links are
independent patient or incident observations.

Map technical-domain labels before counting:

| CIPHER domain | Model construct | Coverage class |
| --- | --- | --- |
| Health Records | EHR service availability | represented digital service |
| Laboratory Systems | laboratory service availability | represented digital service |
| ePrescribing | pharmacy service availability | represented digital service |
| Imaging | imaging service availability | represented digital service |
| Booking Systems | scheduling service availability | represented digital service |
| Admin and Billing | no billing service | absent explicit service |
| Communications | no communication service | absent explicit service |
| Hospital Infrastructure | no infrastructure service | absent explicit service |
| Operating Rooms | no operating-room service | absent explicit service |
| Telemetry | no telemetry service | absent explicit service |
| All | cannot assign to one modeled service | unspecified |

"Represented" refers only to a digital-service label. It does not establish
coverage of the associated patient harm, clinical workflow, or severity.
Identity and backups are internal supporting services without matching
CIPHER technical-domain labels. Do not derive criticality weights or control
effects from Clinical Impact Score.

Normalize the obvious label typo Firsy Day to First Day, with the number
changed recorded. Report all time labels. First Week straddles the 72-hour
model horizon; it cannot be classified as wholly inside or outside it.
Week 2 and First Month are annotations beyond the model's horizon. They
are not recovery durations. Do not infer when an outage ended or count
these annotations as independently observed delayed recoveries.

Outputs: domain counts and distinct reference-link counts; coverage-class
counts; time-label counts and distinct reference-link counts; source-level
counts and leave-one-reference-link-out ranges for the proportion assigned
to absent explicit services and beyond-horizon time labels. These ranges
are influence diagnostics, not sampling confidence intervals. Publish the
mapping, provenance, missingness, duplicate count, and all categories.
No hypothesis tests or population prevalence claims are planned.

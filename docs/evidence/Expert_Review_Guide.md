# Expert review guide

## Purpose

Use structured expert review to identify unrealistic assumptions, missing failure modes, and defensible uncertainty ranges. Expert judgment should constrain or challenge the model; it should not be used to manufacture precise-looking numbers.

## Reviewers to recruit

Aim for at least three independent perspectives:

- Healthcare IT, clinical informatics, emergency management, or hospital operations.
- Cybersecurity incident response, security architecture, identity, network segmentation, or recovery.
- Statistics, operations research, or simulation modeling.

One person may cover multiple areas, but disagreements between disciplines are useful data and should be documented.

## Safety and ethics boundary

Before collecting responses as research data, check applicable school, competition, institutional, consent, and privacy requirements. Do not request:

- Real credentials, IP addresses, exploitable vulnerabilities, or sensitive network diagrams.
- Names of affected patients or staff.
- Nonpublic incident details that the reviewer is not authorized to share.
- Exact weaknesses that could make an identifiable organization easier to attack.

Use abstract dependency categories and broad ranges. Allow reviewers to decline any question.

## Materials to send in advance

- One-page project summary.
- Current assumption audit.
- Plain-language model description.
- Proposed outcome definitions.
- A diagram of abstract service dependencies only—not a real network.
- Statement that the simulator is defensive and not a risk calculator for a named hospital.

## Suggested 30–45 minute agenda

1. Five minutes: purpose, safety boundary, and model scope.
2. Ten minutes: service dependencies and operational outcomes.
3. Ten minutes: attack, detection, containment, and recovery logic.
4. Ten minutes: parameter ranges and failure modes.
5. Five minutes: most serious flaw and recommended validation case.

## Core questions for every reviewer

1. What is the most unrealistic assumption in the current model?
2. Which important dependency or failure mode is missing?
3. Which modeled quantity could you judge only qualitatively, not numerically?
4. Which parameter ranges appear clearly impossible or misleading?
5. What evidence would change your answer?
6. Which outcome would matter most to a healthcare decision-maker?
7. What result would make you distrust the simulator?
8. What real incident or exercise pattern should the model be able to reproduce?

## Healthcare-operations questions

- Which services have hard dependencies on identity, EHR, laboratory, pharmacy, imaging, communications, and vendor systems?
- When a digital service is unavailable, what workarounds preserve partial function?
- Which delays matter operationally: minutes, hours, days, or recovery sequencing?
- Is “fraction of supporting nodes available” a meaningful abstraction? If not, what rule is better?
- Which outcomes should be reported separately rather than collapsed into one weighted score?
- How do diversion, backlog, and recovery surges affect neighboring organizations?

## Cybersecurity questions

- Does the model separate initial access, privilege escalation, lateral movement, impact, detection, containment, eradication, and restoration sufficiently?
- Which paths can defeat nominal network segmentation?
- What makes a backup truly recoverable: isolation, credentials, management plane, immutability, testing, clean-room restoration, or reconnection procedure?
- Should detection delay and containment delay be modeled separately?
- Which controls interact in ways that a simple multiplier cannot represent?
- What extreme-condition tests should always pass?

## Simulation/statistics questions

- Is the unit of analysis correctly defined and paired?
- Are scenario and parameter uncertainties separated from Monte Carlo error?
- Is the planned scenario count sufficient for the desired precision?
- Are recovery times censored correctly at the horizon?
- Are rank probabilities and optimizer selection bias handled appropriately?
- Which validation evidence is independent of calibration?

## Recording judgments

For each proposed parameter or model change, record:

| Field | Required entry |
|---|---|
| Reviewer domain | Broad expertise only |
| Judgment | Range, ordering, mechanism, or objection |
| Basis | Experience, published evidence, exercise, or assumption |
| Confidence | Low, medium, or high |
| Disagreement | Other reviewer views |
| Decision | Accepted, rejected, or deferred |
| Rationale | Why the team made that decision |

Do not average incompatible expert opinions automatically. Preserve disagreement as alternative scenarios or wider uncertainty where appropriate.

## Short outreach message

Subject: Request for brief expert review of a student healthcare-cybersecurity simulation

Hello [Name],

We are high-school researchers developing a defensive simulation that compares cybersecurity and recovery strategies in synthetic healthcare networks. Our first version used transparent but largely theoretical assumptions. We are now designing a prospective validation study and want experts to challenge those assumptions before we run new experiments.

Would you be willing to spend 30–45 minutes reviewing our model at a high level? We would ask only about abstract service dependencies, plausible ranges, important failure modes, and appropriate validation tests. We will not request sensitive network, patient, credential, or vulnerability information. We can send a one-page summary and question guide in advance.

Your feedback would help us make the study more scientifically responsible. We would also follow any applicable school or research-consent requirements before treating responses as research data.

Thank you for considering it,

Ashish Agrawal, Mukil Dharanidharan, and Naman Upadhyay

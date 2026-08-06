# Originality and author-voice audit

**Manuscript audited:** *Layered Controls and Service Disruption in a Synthetic Hospital Network: A Paired Monte Carlo Analysis*
**Search date:** August 5, 2026
**Status:** Pre-external-validation manuscript

## Bottom line

The exact title and several distinctive sentences did not produce an indexed exact match in the web searches performed for this audit. The paper does not appear to duplicate the wording or full design of an identified publication.

The broader research area is not unique. Published studies already simulate hospital ransomware, recovery strategies, patient flow, infrastructure dependencies, financial loss, regional EMS effects, and IT segmentation. The manuscript should therefore avoid “first,” “novel,” or “unique” unless a later systematic review supports that wording.

The most defensible distinction is the combination used here: directed within-hospital asset propagation, seven service dependencies, event-indexed paired random values, simultaneous variation of 13 assumptions, independent metric reconciliation, several time-step checks, and retention of a failed diagnostic. This is a differentiated workflow, not proof of priority.

## Closest research located

| Study | Main overlap | Important difference |
|---|---|---|
| [Ghayoomi et al., 2021](https://doi.org/10.1177/20552076211059366) | Hospital ransomware simulation and recovery comparison | Patient-flow and resource-constrained discrete-event model; compares ransom payment and restoration rather than within-network control portfolios. |
| [Chiaradonna et al., 2023](https://doi.org/10.1111/risa.14127) | Random-graph hospital cyber-risk modeling | Models aggregate financial-loss distributions, not time-varying clinical-service availability. |
| [Willing et al., 2025](https://doi.org/10.1186/s12911-025-02988-8) | Cyberattack, device outage, and hospital-process simulation | Uses a hybrid trauma-process model and emergency plans rather than asset-level propagation across hospital services. |
| [Carraminana et al., 2025](https://doi.org/10.1016/j.comcom.2025.108070) | Agent-based healthcare-infrastructure interdependencies and availability | Broader infrastructure-agent model; the present study emphasizes paired portfolio differences, explicit metric reconstruction, and time-step diagnostics. |
| [Arsalani et al., 2026](https://doi.org/10.1016/j.omega.2026.103578) | Ransomware simulation and hospital IT segmentation | Combines two real incidents with a regional EMS model. It is the closest recent overlap, but its unit is ambulance operations and regional capacity rather than within-hospital digital propagation. |
| [Buffalo et al., 2026](https://arxiv.org/abs/2603.11084) | Event-indexed common random numbers | A general simulation-method paper. It supports the manuscript's event-keyed implementation and also shows why merely reusing a seed would be insufficient. |

The revised literature review now names these boundaries directly. In particular, it says that this project is not the first ransomware, hospital-resilience, or segmentation simulation.

## Phrase-overlap check

Searches included the exact manuscript title and quoted versions of distinctive phrases concerning the stability of direction, the metric audit, paired scenarios, and the retained convergence failure. No exact indexed match was found. This check can detect obvious public overlap; it cannot search private submissions, subscription-only similarity databases, unindexed student work, or every full-text scholarly archive.

For a formal submission, an adviser or school may run the final version through an institutional similarity service such as iThenticate or Turnitin. A similarity report should be reviewed source by source. A percentage alone does not distinguish copied prose from references, standard methods language, titles, or correctly quoted material.

## Why the earlier prose looked machine-written

The previous version had several common signals of heavily assisted academic prose:

- repeated contrast formulas such as “not X, but Y” and “the defensible finding is therefore”;
- nearly identical paragraph structure across sections;
- frequent abstract nouns such as “framework,” “robustness,” “contribution,” and “operational use” without a concrete development narrative;
- limitations written as a complete, evenly weighted catalogue;
- claims that sounded polished before explaining what the team actually encountered while running the model.

The revision does not insert mistakes, slang, or artificial randomness. Instead, it adds the real sequence of decisions: the first result looked unusually clean, the time-step diagnostic changed its interpretation, the diagnostic error was retained, and the recovery-duration check failed. It also shortens stock transitions and gives the closest studies specific credit.

## AI-detector warning

No “humanizer” was used and the manuscript was not uploaded to third-party rewriting sites. Those services can alter technical meaning, invent citations, expose unpublished work, and encourage concealment. They also cannot establish authorship.

AI-text detectors are probabilistic style classifiers, not forensic proof. Published evaluations have found strong sensitivity to domain and writing style, real-world unreliability, and false positives. Relevant evidence includes [Pudasaini et al., 2025](https://aclanthology.org/2025.genaidetect-1.4/), [Liang et al., 2023](https://doi.org/10.1016/j.patter.2023.100779), and [Doughman et al., 2025](https://aclanthology.org/2025.coling-main.288/). A “100% AI” result should not be treated as a measured percentage of who wrote the paper.

In this case, however, the paper genuinely received substantial AI assistance. The correct response is transparent disclosure and author ownership, not an attempt to produce a lower detector score.

## What the authors still need to do

Each named author should read the paper without the source code open and answer these questions in their own words:

1. Why did we choose service-hours rather than compromised-node count?
2. Which result surprised us most, and why?
3. What exactly was wrong with the first diagnostic?
4. Which assumption would we replace first if hospital data became available?
5. What did each author personally design, code, verify, or write?

Any author who cannot answer a question should revisit the code and analysis before approving the manuscript. The final contribution statement and a few sentences describing the team's actual choices should be written by the authors themselves. That is the strongest available evidence of genuine authorship and understanding.

## Confidence statement

**Reasonable conclusion:** the combined study design appears differentiated from the closest identified research, and no obvious public phrase copying was found.
**Conclusion not supported:** the paper is proven globally unique, plagiarism-free in every database, or ready to claim priority.
**Next scientific step:** external face validation with hospital IT, clinical operations, and simulation reviewers, followed by a documented model revision if necessary.

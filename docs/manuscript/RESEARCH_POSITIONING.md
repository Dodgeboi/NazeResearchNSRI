# Research positioning and primary sources

Source review updated September 6, 2026. This is a targeted review of directly relevant primary literature, not a systematic literature review or a priority claim over every related paper.

## Contribution

The central result is the loss of apparent endpoint stability when shared
costs, burdens, and sampling uncertainty are examined together. The
implementation computes guaranteed retention while preserving shared
component-price dependencies. It distinguishes that deterministic result
from conditional bootstrap frequency and a separate conservative
population-mean guarantee.

Necessary/possible efficiency, security portfolio simulation-optimization,
bootstrap subset selection, and concentration inequalities are prior methods.
The novelty is the specific joint study, dependency-aware implementation,
and documented scientific finding. This is not a claim to a new general
optimization or statistical theory.

The final comparison adds complete frontiers conditioned on all ten
unidentified coefficients, with matched-size reference subsets. It also
quantifies the difference between range-only bounds, empirical Bernstein,
and approximate paired inference. These are new analyses of the existing
bank, not an independently developed hospital experiment.

Additional primary sources reviewed for this revision:

| Primary source | Relevance and boundary |
| --- | --- |
| [Maurer and Pontil, 2009, official COLT paper](https://www.cs.mcgill.ca/~colt2009/papers/012.pdf) | Theorem 11 explicitly permits independent, nonidentically distributed observations; pooled paired variance plus the finite-sample range penalty supports the comparison |
| [Ide and Schobel, 2016, publisher](https://link.springer.com/article/10.1007/s00291-015-0418-7) | Survey distinguishing robustness concepts in uncertain multi-objective optimization; prevents presenting a finite specialization as a new general concept |
| [Bitran, 1980, publisher](https://pubsonline.informs.org/doi/abs/10.1287/mnsc.26.7.694) | Earlier interval-coefficient multiple-objective optimization; part of the mathematical lineage |
| [Currie and Monks, 2021](https://doi.org/10.1145/3462187); [accepted manuscript](https://eprints.soton.ac.uk/447867/) | BootComp is a direct predecessor for bootstrap subset selection with common random numbers and includes a hospital ward application |
| [Andradóttir and Lee, 2021](https://doi.org/10.1016/j.ejor.2020.10.021) | Pareto-set estimation with correct-selection guarantees; our fixed-bank diagnostic is not a replacement sequential selection procedure |
| [Hoeffding, 1963](https://doi.org/10.1080/01621459.1963.10500830) | Independent bounded-observation inequality used with a union bound; no new concentration result is claimed |
| [CIPHER v1.0.1](https://doi.org/10.5281/zenodo.17344644); [UC San Diego project](https://cyberhealth.ucsd.edu/research/cipher-platform/index.html) | Independently authored, licensed coded clinical-harm dataset; supports a construct audit, not causal effects or population incidence |
| [Tully et al., 2025, corrected publisher article](https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2836824); [PubMed](https://pubmed.ncbi.nlm.nih.gov/40682764/) | Corrected inherited citation metadata; verified 5.1-hour median is an HDO FHIR downtime construct, distinct from the services-within-six-hours statistic |

For presentation, the accepted BootComp paper and the
[Tanabe and Ishibuchi paper](https://arxiv.org/html/2009.12867v1) informed
the progression from problem formulation through methods to numerical
findings. Their wording, institutional identities, and publication marks
were not copied. The manuscript uses the existing IEEEtran layout with
shorter result headings, a model diagram, comparison figures, and technical appendices.

| Primary work | Established contribution | Relation to this project |
|---|---|---|
| [Kiesling et al., 2016](https://doi.org/10.1007/s40070-016-0055-7); [author PDF](https://noah.nrw/ubbihs/download/pdf/5918762) | Security-control portfolios using multi-objective simulation-optimization | Direct precedent for portfolio modeling; our evidence framework, hospital-service outcomes, and stability certificate define the specific contribution |
| [Hladík, 2017](https://kam.mff.cuni.cz/~hladik/publ/b2hd-Hla2017e.html) | Possible efficiency and robust counterparts under interval coefficient uncertainty | Established efficiency concepts; our exact corner proof concerns a finite Cartesian objective table |
| [Tanabe and Ishibuchi, 2020](https://doi.org/10.1016/j.asoc.2020.106078); [official implementations](https://ryojitanabe.github.io/reproblems/) | Published engineering multi-objective problem suite | Unchanged, versioned RE21/RE22 functions define the external cases; no claim to replicate continuous global fronts or the original paper's numeric tables |
| [Meyer et al., 2023 preprint](https://arxiv.org/abs/2305.00945); [Microsoft Research](https://www.microsoft.com/en-us/research/publication/how-effective-is-multifactor-authentication-at-deterring-cyberattacks/) | Observational MFA effectiveness in commercial accounts | Supports mechanism reasoning without identifying a hospital-wide ransomware effect; current bibliography corrects the inherited 2022 date |
| [Neprash et al., 2022](https://doi.org/10.1001/jamahealthforum.2022.4873) | Observed ransomware disruption in healthcare organizations | Incident context and comparison targets, not counterfactual portfolio effects |
| [Willing et al., 2025](https://doi.org/10.1186/s12911-025-02988-8) | Hospital process overload simulation with observations and expert input | A different empirical validation level; this model does not inherit that validation |
| [Monks et al., 2019](https://doi.org/10.1080/17477778.2018.1442155) | STRESS simulation reporting guidelines | Transparent design, implementation, and uncertainty reporting |
| [Nosek et al., 2018](https://doi.org/10.1073/pnas.1708274114) | Prior plans distinguish prediction from outcome-informed analysis | Hospital analyses are retrospective; benchmark choices were recorded before generating candidate outcomes |
| [Buffalo et al., 2026 preprint](https://arxiv.org/abs/2603.11084) | Event-keyed common random numbers | Meaningful pairing across alternative policy execution paths |
| [Steegen et al., 2016](https://doi.org/10.1177/1745691616658637) and [Simonsohn et al., 2020](https://doi.org/10.1038/s41562-020-0912-z) | Multiverse and specification-curve analyses | Motivate sensitivity to analysis choices; our descriptive enumeration does not implement specification-curve joint inference |
| [Nuijten et al., 2016](https://doi.org/10.3758/s13428-015-0664-2) and [Raunak and Olsen, 2021](https://doi.org/10.1109/MET52542.2021.00015) | Statistical consistency and metamorphic simulation checks | Selected scope/unit/quantifier assertions supplement established relational tests |
| [Yu et al., ABE-Ralph, August 2026 preprint](https://arxiv.org/abs/2608.26753) | Structured experimental-fidelity auditing in scientific-agent workflows | Related to the supporting assertion registry; not the central comparator for the hospital model or frontier certificate |

## What the external cases establish

The two published problems supply independent definitions; candidate generation, perturbations, and verification use this project's workflow. All planned radii are reported. The exact corner checks and separate sorting oracle test implementation; the mathematical proof establishes inclusion for the entire box. Five empty guaranteed sets show that correctness does not imply informative bounds.

## Final-product status

The repository contains the final named paper and anonymous manuscript copy. No venue submission or peer-review acceptance is claimed. Historical venue advice and earlier self-scores do not determine the project's contribution or current status.

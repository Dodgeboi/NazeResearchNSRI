# Global Ransomware Resilience under Constraint (GRRC)

**A Monte Carlo Analysis of Cybersecurity Defense Portfolios for
Healthcare Networks**

*Presentation title: "When Hospitals Cannot Afford Every Defense:
Finding the Most Cost-Effective Protection Against Ransomware."*

NSRI Summer Research Hackathon 2026 · Engineering & Technology track ·
Coding-based computational research study.

---

## 1. Project summary

Ransomware repeatedly disrupts the connected systems hospitals depend on,
but healthcare organizations differ enormously in what they can spend on
defense. This project is a **fully synthetic, defensive Monte Carlo
simulation** that measures how five families of cybersecurity controls —
network segmentation, patching, detection/isolation speed, identity
restrictions, and backup isolation — affect ransomware-style propagation
and, crucially, **critical-service disruption** across modeled healthcare
networks of different sizes and cyber-capacity levels. It then searches
for the **most cost-effective defense portfolios under limited budgets**.

## 2. Research question

> Across simulated healthcare networks of different sizes and
> cyber-capacity levels, how do network segmentation, patching, detection
> speed, access restrictions, and backup isolation affect
> ransomware-style propagation and critical-service disruption — and
> which defense combinations provide the greatest resilience under
> limited security budgets?

## 3. Why the problem matters

Hospitals run on EHR, lab, pharmacy, imaging, scheduling, authentication,
connected devices, and backups; when ransomware takes these down, patient
care suffers. Attacks on healthcare have risen sharply (Neprash et al.,
2022; ENISA, 2023), and events like WannaCry forced tens of thousands of
cancelled appointments (National Audit Office). Yet cybersecurity
capacity varies widely worldwide (ITU, 2024). The engineering question is
therefore not "what is the strongest defense?" but **"what should you buy
first when you cannot afford everything?"** (Full citations:
`report/references.md`.)

## 4. Safety statement

This project is **entirely defensive and simulated**. It contains **no
malware, ransomware, encryption payloads, exploit code, credential
tools, scanners, persistence mechanisms, or command-and-control
functionality**, and it **never touches any real system, IP address,
hospital, or person**. A "compromise" is an abstract state transition on
a synthetic graph node (`HEALTHY → COMPROMISED → DETECTED → ISOLATED →
RESTORING → RESTORED`). All networks and data are synthetic. The model
does not represent any specific ransomware family and does not predict
what would happen at any real hospital. See `docs/limitations.md`.

## 5. Repository structure

```
.
├── configs/           quick / standard / full YAML + defense_costs.yaml
├── src/grrc/          the simulation package (see below)
├── scripts/           thin entry points (run_experiments, reproduce_all, …)
├── tests/             pytest suite (unit + 12 validation cases)
├── data/raw/          per-trial CSVs (git-ignored; reproducible)
├── data/processed/    summary tables (committed)
├── outputs/           figures/ (PNG+PDF), tables/ (figure data), logs/
├── docs/              methodology, assumptions, data_dictionary,
│                      model_validation, experiment_plan, limitations,
│                      team_plan
└── report/            abstract, research_brief, references,
                       ai_transparency, presentation_script,
                       judge_questions, slide_outline (+ templates/)
```

Package modules (`src/grrc/`): `enums`, `config`, `models`,
`network_generator`, `service_dependencies`, `defenses`, `propagation`,
`simulation`, `experiments`, `optimization`, `statistics`, `plotting`,
`validation`, `report`, `cli`, `utilities`.

## 6. Installation

Requires **Python 3.11+**. From the repository root:

```bash
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -e .            # installs grrc + numpy/pandas/networkx/scipy/…
# or:  pip install -r requirements.txt
```

## 7. Quick-start (≈ 1–2 minutes)

```bash
python -m grrc.cli validate                          # 12 model checks
python scripts/reproduce_all.py --profile quick      # full mini-pipeline
```

Outputs land in `data/`, `outputs/figures/`, and `report/`.

## 8. Standard experiment (the main analysis, ≈ 10–30 min on 4 cores)

```bash
python -m grrc.cli simulate --config configs/standard.yaml   # ~16.8k main+sweep+backup trials
python -m grrc.cli optimize --config configs/standard.yaml   # 144 portfolios × 3 profiles
python -m grrc.cli analyze  --config configs/standard.yaml   # summary tables + statistics
python -m grrc.cli plot     --config configs/standard.yaml   # Figures 1–7
python -m grrc.cli report   --config configs/standard.yaml   # fill Brief/abstract from CSVs
# …or all of the above at once:
python scripts/reproduce_all.py --profile standard
```

## 9. Full experiment (expanded, hours; uses all cores)

```bash
python scripts/reproduce_all.py --profile full
```

## 10. Validation

```bash
python -m grrc.cli validate      # writes docs/model_validation.md
pytest                           # runs unit tests + the 12 validation cases
```

The 12 checks (zero-spread, guaranteed-spread, disconnected zone,
isolated backups, patch immunity, isolation, reproducibility, seed
variation, service dependencies, convergence, budget feasibility, data
integrity) must all pass before results are trusted.

## 11. Output explanation

* `data/raw/<mode>_main_results.csv` — one row per trial, every metric +
  full configuration (reproduce any row from `master_seed`+`trial_id`).
* `data/raw/<mode>_sweep_results.csv` — patch × detection grid.
* `data/raw/<mode>_backup_results.csv` — controlled backup comparison.
* `data/processed/…` — summaries, baseline comparisons (effect sizes,
  bootstrap CIs, Holm-corrected tests), Pareto frontier, best portfolios,
  cost-sensitivity, minimum-budget tables.
* `outputs/figures/figN_*.png|.pdf` + `outputs/tables/figN_*_data.csv` —
  every figure plus the exact numbers it plots.

Column-by-column definitions: `docs/data_dictionary.md`.

## 12. Reproducing every figure

```bash
python -m grrc.cli plot --config configs/standard.yaml
```

produces Figures 1–7 (network architecture; disruption by strategy;
patch × detection heat map; budget–resilience Pareto frontier; facility
comparison; backup-compromise by strategy; cost-effectiveness), each as
PNG + PDF with its underlying CSV. Captions: `outputs/figures/captions.md`.

## 13. Assumptions

Every numeric and structural assumption is registered in
`docs/assumptions.md` (A1–A22) and is configurable via YAML. Highlights:
one step = 15 modeled minutes; base spread 0.35/edge/step; patching is
85% effective (imperfect on purpose); a service needs its core node +
60% support + identity; **catastrophic disruption** = a clinical service
down > 8 consecutive steps; **defense costs are normalized points, not
dollars**, and all conclusions are re-tested at ±50% cost scaling.

## 14. Limitations

Synthetic topologies; abstract non-dollar costs; a single simplified
lateral-movement formula; no human-behavior, data-extortion, or
re-infection modeling; simplified recovery on a 48-hour horizon;
parameter-range dependence; and no country-level conclusions. The study
identifies **modeled tradeoffs under stated assumptions, not guaranteed
real-world outcomes**. Full discussion: `docs/limitations.md`.

## 15. Team roles

Member 1 — simulation & network-model lead; Member 2 — cybersecurity &
experiment lead; Member 3 — research & data-analysis lead. Full
responsibilities, the six-day schedule, and a cross-training checklist:
`docs/team_plan.md`.

## 16. AI-use disclosure summary

An AI assistant (Claude) helped design the code structure and assisted
with implementation, debugging, documentation, and writing organization.
The team reviewed and tested all code, verified every source by hand, and
generated all results by running the program. No results or citations
were fabricated; unresolved report values remain visible placeholders
rather than invented numbers. Full statement: `report/ai_transparency.md`.

## 17. Citation

If you use this project, please cite it as described in
`report/references.md` ("How to cite this project"), recording the exact
commit hash used to generate your results. License: MIT (`LICENSE`).

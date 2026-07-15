# Global Ransomware Resilience under Constraint

**A Monte Carlo analysis of cybersecurity defense portfolios for healthcare networks.**
NSRI Summer Research Hackathon 2026 — Engineering & Technology track.

A fully synthetic, **defensive** simulation study of how a ransomware-style attack
spreads through a hospital network, and which combinations of defenses buy the most
resilience when an organization cannot afford every control. There is **no malware,
exploit code, scanner, or real-system interaction anywhere in this repository** — a
"compromise" is an abstract state flag on a generated graph node.

> New here? Read [`START_HERE.md`](START_HERE.md) for a plain-language tour, then open
> the figures in [`outputs/figures/`](outputs/figures/) and the paper in
> [`report/research_brief.md`](report/research_brief.md).

---

## What the study does

We build a synthetic healthcare network (10 zones, three facility sizes) and let an
abstract compromise process — `HEALTHY → COMPROMISED → DETECTED → ISOLATED → RESTORING
→ RESTORED` — run thousands of times under different defensive postures and budgets.
Damage is measured as **weighted service-hours lost** across seven critical services,
not machines infected, because service disruption is what actually threatens patients.

**28,225 Monte Carlo trials** (standard mode, master seed `20260713`) across four
experiments: a main factorial, a patch × detection sweep, a 144-portfolio budget
optimizer, and a controlled backup comparison. Every conclusion is re-tested under
±25%/±50% cost scaling.

## Quick start

```bash
pip install -e .                                  # install the `grrc` package
python -m grrc.cli validate                       # 12 model checks (expect 12/12)
python scripts/reproduce_all.py --profile quick   # ~1–2 min: full pipeline, all outputs
```

Reproduce the submitted results (~10–30 min on a 4-core laptop):

```bash
python scripts/reproduce_all.py --profile standard
```

Because seeding uses `numpy.random.SeedSequence(master_seed, trial_id)`, identical
seeds regenerate identical results — anyone can re-derive every number and figure.

## Command reference

| Command | Does |
|---|---|
| `grrc validate` | Run the 12 behavioral validation checks → `docs/model_validation.md` |
| `grrc simulate` | Main + sweep + controlled-backup experiments → `data/raw/` |
| `grrc optimize` | Evaluate 144 portfolios, budget selection, Pareto frontier, cost sensitivity |
| `grrc analyze`  | Summary tables and statistics → `data/processed/` |
| `grrc plot`     | All publication figures → `outputs/figures/` (+ underlying CSVs) |
| `grrc report`   | Fill report templates from generated data (never invents numbers) |
| `grrc reproduce`| The full pipeline end-to-end |

Each command takes `--config configs/{quick,standard,full}.yaml`.

## Repository map

```
START_HERE.md        Plain-language guide (read first)
report/              The paper, abstract, presentation, Q&A prep, references
  research_brief.md      Full write-up (numbers auto-inserted from data)
src/grrc/            The simulator (Python package)
tests/               Unit tests + the 12 validation cases
configs/             quick / standard / full run configs; defense costs
data/raw/            One CSV row per trial (the raw evidence) + manifests
data/processed/      Summary tables and statistics
outputs/figures/     The 7 figures (PNG + PDF + underlying CSV)
docs/                Methodology, assumptions registry, data dictionary, limitations
```

## Integrity & ethics

- **Nothing is hand-typed.** Every number in the abstract and research brief is inserted
  from the generated CSVs by `grrc report`; unresolved `{{TOKENS}}` are left visible
  rather than guessed. Sources in `report/references.md` were manually verified.
- **Entirely synthetic and defensive.** No real hospital, patient, or network data; no
  malware, payloads, or attacker tooling. See [`docs/limitations.md`](docs/limitations.md).
- **AI use is disclosed** in [`report/ai_transparency.md`](report/ai_transparency.md).
- **No real-world or country-level claims.** Capacity profiles are neutral parameter
  bundles; results are modeled tradeoffs under stated assumptions, not predictions.

## Citation

See [`CITATION.cff`](CITATION.cff). Record the exact commit hash used for any results.

License: MIT.

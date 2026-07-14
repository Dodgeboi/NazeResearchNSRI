# Team Plan: Roles, Six-Day Schedule, Cross-Training

## Team roles (three members)

### Member 1 — Simulation & network-model lead
* Synthetic network generation (`network_generator.py`), graph
  structure, zone/access rules
* Critical-service dependency model (`service_dependencies.py`)
* Propagation state machine (`propagation.py`)
* Validation tests 1–10 and the pytest suite
* Owns: `docs/model_validation.md`, Figure 1

### Member 2 — Cybersecurity & experiment lead
* Defense controls and portfolios (`defenses.py`)
* Attack-entry scenarios and threat-model documentation
* Experiment configuration (`configs/*.yaml`), execution of quick/
  standard/full runs
* Budget optimizer + cost-sensitivity analysis (`optimization.py`)
* Reproducibility checks (clean-clone rerun, seed audits)
* Owns: `docs/assumptions.md`, `configs/defense_costs.yaml`, Figure 4

### Member 3 — Research & data-analysis lead
* Authoritative-source research and citation verification
  (`report/references.md` — every URL opened and checked by hand)
* Statistical analysis (`statistics.py` outputs), interpretation
* Figures 2–3, 5–7 and captions
* Research Brief, abstract, presentation script, Q&A sheet
* Owns: `report/` directory

All members review each other's pull requests; nobody merges their own
work unreviewed.

## Six-day execution schedule

### Day 1 — Foundations
- [ ] Finalize method: read `docs/methodology.md` + `docs/assumptions.md` together; agree on the catastrophic-disruption definition (A14) **before** any experiment
- [ ] Set up repository, environment (`pip install -e .`), run `pytest`
- [ ] M1: network generator complete; M2: config schema + YAML files; M3: begin source research, collect candidate citations
- [ ] Basic unit tests green (`tests/test_network_generator.py`)

### Day 2 — Core dynamics
- [ ] M1: propagation + service dependencies implemented and unit-tested
- [ ] M2: flat/basic/least-privilege architectures wired into generator
- [ ] Run validation cases 1–3, 6–9 (`python -m grrc.cli validate --fast`)
- [ ] M3: draft Motivation + Method sections of the Brief (no results)

### Day 3 — Defenses & export
- [ ] M2: patching, detection/isolation, backup strategies, entry scenarios, identity controls
- [ ] M1: validation cases 4–5 pass; raw CSV export working
- [ ] Full `python -m grrc.cli validate` passes 12/12
- [ ] M3: data dictionary review; hypothesis section (predictions) frozen in `docs/experiment_plan.md`

### Day 4 — Pilot & main run
- [ ] Quick-mode pilot end-to-end (`python scripts/reproduce_all.py --profile quick`); debug anything odd
- [ ] Convergence analysis reviewed (validation case 10)
- [ ] **Standard run** (`python -m grrc.cli simulate --config configs/standard.yaml`) + `analyze`
- [ ] Initial Figures 1–3, 5, 6 generated and sanity-checked against raw CSVs

### Day 5 — Optimization & writing
- [ ] `python -m grrc.cli optimize --config configs/standard.yaml` (includes ±25/±50% cost sensitivity)
- [ ] Statistical tables finalized; Figures 4 & 7
- [ ] `python -m grrc.cli report` fills the Brief/abstract from generated CSVs; M3 edits prose around the real numbers
- [ ] Verify every citation URL by hand; delete anything unverifiable

### Day 6 — Freeze & rehearse
- [ ] Clean rerun from a fresh clone (`git clone` → install → `reproduce_all.py --profile standard`); confirm CSVs match (same seed ⇒ identical)
- [ ] Finalize figures, abstract, AI-transparency statement
- [ ] Practice 3-minute presentation ×3; run the judge Q&A sheet as a mock panel
- [ ] Package submission; tag the release commit

## Cross-training checklist

Every member must be able to explain, unaided:

- [ ] What each **node** and **edge** represents (abstract device/system; permitted communication path — nothing real)
- [ ] How compromise spreads (per-edge per-step probability, the A5 formula, and what each factor means)
- [ ] What **segmentation** changes (which zone→zone paths exist + traversal attenuation; flat vs. basic vs. least-privilege)
- [ ] How **patching** is modeled (coverage assigns patched flags; patched targets 85% less susceptible — imperfect on purpose, A6)
- [ ] How **detection & isolation** are modeled (geometric detection with mean delay; per-step isolation success; false positives cost availability)
- [ ] How **service disruption** is calculated (core node + 60% support + identity dependency; downtime × weights × 0.25 h)
- [ ] What **Monte Carlo simulation** means (repeat a random process many times; report the distribution of outcomes, not one run)
- [ ] What the project **does not prove** (no real-hospital predictions, no country conclusions, no guaranteed outcomes — modeled tradeoffs under stated assumptions)
- [ ] Why normalized costs are **not dollar estimates** (relative weights; conclusions re-tested under ±50% scaling)

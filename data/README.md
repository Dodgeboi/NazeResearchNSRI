# Data directory

* `raw/` — one CSV row per Monte Carlo trial, written by
  `python -m grrc.cli simulate` / `optimize`. **Committed** so judges can open the raw
  evidence directly; also fully reproducible from configs + seeds (rerun with the same
  YAML and you get numerically identical files). A `*_manifest.json` records trial
  counts, master seed, and timing for each run.
* `processed/` — summary tables written by `analyze` and `optimize`.

Column definitions: `docs/data_dictionary.md`.
Reproduction: `python scripts/reproduce_all.py --profile standard`.

All data in this directory is synthetic simulation output. No real hospital, patient,
or network data exists anywhere in this project.

#!/usr/bin/env python3
"""Run the full-space paired discovery bank.

Discovery is exploratory by construction: it debugs the specification,
estimates Monte Carlo precision, and generates the finalist labels that the
confirmatory stage reports as a restricted view. Nothing here is
confirmatory, and the manifest records that.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from grrc.config import load_config
from grrc.optimization import build_candidate_specs
from grrc.experiments import run_specs
from grrc.provenance import (build_manifest, snapshot_inputs,
                             write_manifest)
from grrc.utilities import ensure_dirs, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/multiobjective_portfolio.yaml")
    parser.add_argument("--output",
                        default="data/multiobjective/discovery/discovery_results.csv")
    parser.add_argument("--trials", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.trials:
        cfg.optimization.trials_per_portfolio = args.trials
    specs, portfolios = build_candidate_specs(cfg)
    print(f"discovery: {len(specs):,} executions over {len(portfolios)} "
          f"distinct portfolios")
    raw = run_specs(cfg, specs, portfolios=portfolios, desc="multiobjective:discovery")
    out = Path(args.output); ensure_dirs(out.parent)
    write_csv(raw, out)

    # Archive the exact configuration bytes this run used, and hash the
    # archived copies rather than the live files, so the manifest stays true
    # when the study config is later edited for an unrelated reason.
    snapshots = snapshot_inputs(
        [args.config, "configs/defense_costs.yaml",
         "configs/defense_burdens.yaml"],
        out.parent / "config_snapshot")

    manifest = build_manifest(
        run_id=f"discovery:seed{cfg.seed}",
        stage="discovery",
        description="Exploratory full-space paired evaluation. Not confirmatory.",
        inputs=snapshots,
        outputs=[out],
        parameters={
            "master_seed": cfg.seed,
            "trials_per_portfolio": cfg.optimization.trials_per_portfolio,
            "distinct_portfolios": len(portfolios),
            "total_executions": len(specs),
            "sustained_outage_primary_k": cfg.simulation.sustained_outage_min_services,
        })
    write_manifest(manifest, out.parent / "discovery_run_manifest.json")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

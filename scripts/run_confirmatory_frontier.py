#!/usr/bin/env python3
"""Run the full-space confirmatory bank under a frozen protocol.

Refuses to start unless a frozen protocol exists and its self-recorded
SHA-256 still verifies, so confirmatory outputs can only ever be produced
under a design that was fixed beforehand and has not been edited since. The
protocol's digest is written into every raw row and into the run manifest,
which binds results to the design that produced them.

Refuses to overwrite existing confirmatory raw output unless ``--force`` is
given, so a rerun cannot quietly replace results that the manuscript cites.

Usage
-----
    python scripts/freeze_confirmatory_protocol.py --name mo_confirm_v1
    python scripts/run_confirmatory_frontier.py    --protocol mo_confirm_v1
"""

from __future__ import annotations

import argparse
from pathlib import Path

from grrc.config import load_config
from grrc.multiobjective import (confirmatory_candidate_counts,
                                 run_confirmatory_frontier)
from grrc.provenance import (ProvenanceError, build_manifest,
                             load_frozen_protocol, write_manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", default="multiobjective_confirmatory_v1")
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument(
        "--output",
        default="data/multiobjective/confirmatory/"
                "multiobjective_confirmatory_results.csv")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing confirmatory raw output")
    args = parser.parse_args()

    protocol = load_frozen_protocol(args.protocol)
    body = protocol["body"]
    if body.get("stage") != "confirmation":
        raise ProvenanceError(
            f"protocol '{args.protocol}' is not a confirmatory protocol")

    output = Path(args.output)
    if output.exists() and not args.force:
        raise SystemExit(
            f"{output} already exists. Confirmatory output is written once; "
            "pass --force only if you intend to discard the existing results "
            "and record the reason in study/DEVIATIONS.md.")

    cfg = load_config(args.config)

    # The protocol pinned the candidate space and the config hashes. If the
    # resolved space has changed since freezing, the protocol no longer
    # describes this run, and continuing would produce results that look
    # confirmatory but are not.
    expected = body["candidate_space"]["counts_by_profile"]
    actual = confirmatory_candidate_counts(cfg)
    if expected != actual:
        raise ProvenanceError(
            "the resolved candidate space has changed since the protocol was "
            f"frozen.\n  protocol: {expected}\n  current:  {actual}\n"
            "Freeze a new protocol under a new name rather than running this "
            "one against a different space.")

    trials = body["design"]["trials_per_candidate"]
    if not isinstance(trials, dict):
        trials = {name: int(trials) for name in actual}
    master_seed = int(body["design"]["master_seed"])
    total = sum(actual[name] * trials[name] for name in actual)
    print(f"protocol {protocol['name']} sha256 {protocol['sha256'][:12]}… "
          f"frozen {protocol['frozen_at']}")
    print(f"running {total:,} confirmatory executions over "
          f"{sum(actual.values())} profile-candidates")
    for name in sorted(actual):
        print(f"  {name:24s} {actual[name]:4d} x {trials[name]:4d}")

    path = run_confirmatory_frontier(
        cfg, output, trials_per_candidate=trials, master_seed=master_seed)

    # Bind the raw rows to the protocol that authorized them.
    import pandas as pd
    raw = pd.read_csv(path)
    raw["protocol_name"] = protocol["name"]
    raw["protocol_sha256"] = protocol["sha256"]
    raw.to_csv(path, index=False)

    manifest = build_manifest(
        run_id=f"{protocol['name']}:{protocol['sha256'][:12]}",
        stage="confirmation",
        description="Full-space confirmatory evaluation of every resolved "
                    "candidate portfolio on a fresh paired scenario bank.",
        inputs=[args.config, "configs/defense_costs.yaml",
                "configs/defense_burdens.yaml",
                Path(protocol["path"])],
        outputs=[path],
        parameters={
            "trials_per_candidate": trials,
            "master_seed": master_seed,
            "candidate_counts_by_profile": actual,
            "total_executions": total,
            "sustained_outage_primary_k":
                cfg.simulation.sustained_outage_min_services,
        },
        protocol={key: protocol[key]
                  for key in ("name", "path", "sha256", "frozen_at")},
    )
    manifest_path = write_manifest(
        manifest, path.parent / "confirmatory_run_manifest.json")
    print(f"wrote {path}")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()

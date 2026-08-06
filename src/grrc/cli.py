"""Command-line interface for the GRRC study.

Usage examples (see README for the full workflow):

    python -m grrc.cli validate
    python -m grrc.cli simulate --config configs/quick.yaml
    python -m grrc.cli optimize --config configs/standard.yaml
    python -m grrc.cli analyze  --config configs/standard.yaml
    python -m grrc.cli plot     --config configs/standard.yaml
    python -m grrc.cli report   --config configs/standard.yaml
    python -m grrc.cli reproduce --config configs/quick.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .utilities import REPO_ROOT

DEFAULT_CONFIG = REPO_ROOT / "configs" / "quick.yaml"


def _add_config_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                   help="YAML config file (default: configs/quick.yaml)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grrc",
        description="Global Ransomware Resilience under Constraint — "
                    "synthetic, defensive Monte Carlo simulation study.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="run the 12 model-validation cases "
                       "and write docs/model_validation.md")
    p.add_argument("--fast", action="store_true",
                   help="smaller convergence sample sizes (for smoke tests)")
    p.add_argument("--no-report", action="store_true",
                   help="do not rewrite docs/model_validation.md")

    p = sub.add_parser("simulate", help="run main + sweep experiments, "
                       "export raw CSVs")
    _add_config_arg(p)
    p.add_argument("--workers", type=int, default=None,
                   help="override worker process count (0=auto)")

    p = sub.add_parser("optimize", help="evaluate the candidate defense "
                       "portfolios, budget selection, Pareto frontier, "
                       "cost sensitivity")
    _add_config_arg(p)
    p.add_argument("--workers", type=int, default=None)

    p = sub.add_parser("analyze", help="produce processed summary tables "
                       "and statistics from raw CSVs")
    _add_config_arg(p)
    p.add_argument("--input", type=Path, default=None,
                   help="explicit main-results CSV (default: from config)")

    p = sub.add_parser("plot", help="generate all publication figures")
    _add_config_arg(p)

    p = sub.add_parser("report", help="fill report templates with actual "
                       "generated results (never invents numbers)")
    _add_config_arg(p)

    p = sub.add_parser("sensitivity", help="one-at-a-time sensitivity of the "
                       "conclusions to key model parameters (plausible ranges)")
    _add_config_arg(p)
    p.add_argument("--workers", type=int, default=None)

    p = sub.add_parser("reproduce", help="full pipeline: validate -> "
                       "simulate -> optimize -> analyze -> plot -> report")
    _add_config_arg(p)
    p.add_argument("--workers", type=int, default=None)
    return parser


def _load(args) -> "object":
    cfg = load_config(args.config)
    if getattr(args, "workers", None) is not None:
        cfg.experiment.workers = args.workers
    return cfg


def cmd_validate(args) -> int:
    from .validation import run_all_validations, write_validation_report
    results = run_all_validations(fast=args.fast)
    width = max(len(r.name) for r in results)
    failures = 0
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name:<{width}}  {r.details}")
        failures += (not r.passed)
    if not args.no_report:
        from .validation import write_validation_report
        path = write_validation_report(results)
        print(f"\nreport written: {path}")
    print(f"\n{len(results) - failures}/{len(results)} validation checks "
          f"passed")
    return 1 if failures else 0


def cmd_simulate(args) -> int:
    from .experiments import run_experiments
    cfg = _load(args)
    outputs = run_experiments(cfg)
    for name, path in outputs.items():
        print(f"  {name}: {path}")
    return 0


def cmd_optimize(args) -> int:
    from .optimization import optimize
    cfg = _load(args)
    outputs = optimize(cfg)
    for name, path in outputs.items():
        print(f"  {name}: {path}")
    return 0


def cmd_analyze(args) -> int:
    from .statistics import analyze
    cfg = _load(args)
    outputs = analyze(cfg, main_csv=getattr(args, "input", None))
    for name, path in outputs.items():
        print(f"  {name}: {path}")
    return 0


def cmd_plot(args) -> int:
    from .plotting import generate_figures
    cfg = _load(args)
    for path in generate_figures(cfg):
        print(f"  {path}")
    return 0


def cmd_report(args) -> int:
    from .report import populate_reports, NoTemplatesError
    cfg = _load(args)
    try:
        unresolved = populate_reports(cfg)
    except NoTemplatesError as exc:
        # Never report success while writing nothing. ASCII only: this goes to
        # consoles that may not encode typographic dashes (Windows cp1252).
        print(f"  SKIPPED - {exc}", file=sys.stderr)
        return 3
    ok = True
    for name, missing in unresolved.items():
        marker = "OK " if not missing else "!! "
        print(f"  {marker}report/{name}"
              + (f" — unresolved: {sorted(set(missing))}" if missing else ""))
        ok = ok and not missing
    return 0 if ok else 2


def cmd_sensitivity(args) -> int:
    from .sensitivity import run_sensitivity
    cfg = _load(args)
    outputs = run_sensitivity(cfg)
    for name, path in outputs.items():
        print(f"  {name}: {path}")
    return 0


def cmd_reproduce(args) -> int:
    rc = cmd_validate(argparse.Namespace(fast=True, no_report=False))
    if rc:
        print("validation failed — stopping before experiments",
              file=sys.stderr)
        return rc
    for step in (cmd_simulate, cmd_optimize, cmd_analyze, cmd_plot,
                 cmd_report):
        print(f"\n=== {step.__name__.removeprefix('cmd_')} ===")
        rc = step(args)
        # 2 = report tokens unresolved (non-fatal);
        # 3 = no report templates in this checkout (code+data bundle) —
        #     announced by the step itself, not silently ignored.
        if rc not in (0, 2, 3):
            return rc
    print("\nreproduction pipeline complete")
    return 0


COMMANDS = {
    "validate": cmd_validate, "simulate": cmd_simulate,
    "optimize": cmd_optimize, "analyze": cmd_analyze, "plot": cmd_plot,
    "report": cmd_report, "sensitivity": cmd_sensitivity,
    "reproduce": cmd_reproduce,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

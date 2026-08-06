"""Monte Carlo experiment construction, parallel execution, raw export.

Two experiment families are produced here:
  * ``main``  — full factorial: facility x profile x portfolio x entry
                point x repeated trials.
  * ``sweep`` — patch-coverage x detection-delay grid on one facility/
                profile (Figure 3).

Trial IDs are globally unique within a run (main starts at 0, sweep at
1_000_000, optimization at 10_000_000) so that ``(master_seed, trial_id)``
uniquely and reproducibly identifies every row across all raw files.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .config import Config, load_defense_costs
from .defenses import (DefensePortfolio, get_portfolio, portfolio_cost)
from .enums import BackupStrategy, SegmentationLevel
from .models import TrialSpec
from .simulation import run_trial
from .utilities import ensure_dirs, resolve_path, setup_logging, write_csv

SWEEP_ID_OFFSET = 1_000_000
OPT_ID_OFFSET = 10_000_000
BACKUP_ID_OFFSET = 5_000_000

#: Controlled backup-strategy comparison: three portfolios identical
#: except for backup connectivity, all on a flat base at each profile's
#: own baseline patch/detection. This isolates the backup effect (Fig 6)
#: instead of confounding it with the other defenses a portfolio bundles.
BACKUP_PORTFOLIOS: dict[str, DefensePortfolio] = {
    "backup_connected": DefensePortfolio(
        "backup_connected", segmentation=SegmentationLevel.FLAT,
        backup_override=BackupStrategy.CONNECTED),
    "backup_periodic": DefensePortfolio(
        "backup_periodic", segmentation=SegmentationLevel.FLAT,
        backup_override=BackupStrategy.PERIODIC),
    "backup_isolated": DefensePortfolio(
        "backup_isolated", segmentation=SegmentationLevel.FLAT,
        backup_override=BackupStrategy.ISOLATED),
}

# Worker-process globals, set once by the pool initializer so the config
# is not re-pickled for every task.
_WORKER_CFG: Config | None = None
_WORKER_PORTFOLIOS: dict[str, DefensePortfolio] | None = None


def _init_worker(cfg: Config,
                 portfolios: dict[str, DefensePortfolio] | None) -> None:
    global _WORKER_CFG, _WORKER_PORTFOLIOS
    _WORKER_CFG = cfg
    _WORKER_PORTFOLIOS = portfolios


def _run_chunk(specs: list[TrialSpec]) -> list[dict]:
    assert _WORKER_CFG is not None
    rows = []
    for spec in specs:
        portfolio = None
        if _WORKER_PORTFOLIOS is not None:
            portfolio = _WORKER_PORTFOLIOS.get(spec.portfolio)
        rows.append(run_trial(_WORKER_CFG, spec, portfolio=portfolio))
    return rows


def run_specs(cfg: Config, specs: list[TrialSpec],
              portfolios: dict[str, DefensePortfolio] | None = None,
              desc: str = "trials") -> pd.DataFrame:
    """Execute trial specs (parallel if configured) and collect rows."""
    workers = cfg.experiment.workers or (os.cpu_count() or 1)
    if workers <= 1 or len(specs) < 32:
        _init_worker(cfg, portfolios)
        rows = []
        for spec in tqdm(specs, desc=desc, unit="trial"):
            portfolio = (portfolios or {}).get(spec.portfolio)
            rows.append(run_trial(cfg, spec, portfolio=portfolio))
        return pd.DataFrame(rows)

    chunk_size = max(8, len(specs) // (workers * 16))
    chunks = [specs[i:i + chunk_size]
              for i in range(0, len(specs), chunk_size)]
    rows = []
    with ProcessPoolExecutor(
            max_workers=workers, initializer=_init_worker,
            initargs=(cfg, portfolios)) as pool:
        with tqdm(total=len(specs), desc=desc, unit="trial") as bar:
            for result in pool.map(_run_chunk, chunks):
                rows.extend(result)
                bar.update(len(result))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Spec builders
# ---------------------------------------------------------------------------

def build_main_specs(cfg: Config) -> list[TrialSpec]:
    """Full factorial design for the main experiment."""
    specs: list[TrialSpec] = []
    tid = 0
    exp = cfg.experiment
    for facility in exp.facilities:
        for profile in exp.profiles:
            for portfolio in exp.portfolios:
                get_portfolio(portfolio)  # fail fast on unknown names
                for entry in exp.entry_points:
                    for _ in range(exp.trials_per_cell):
                        specs.append(TrialSpec(
                            trial_id=tid, experiment="main",
                            facility=facility, profile=profile,
                            portfolio=portfolio, entry_point=entry,
                            master_seed=cfg.seed))
                        tid += 1
    return specs


def build_sweep_specs(cfg: Config) -> list[TrialSpec]:
    """Patch x detection grid; entry points cycle across trials."""
    specs: list[TrialSpec] = []
    sw = cfg.sweep
    entries = cfg.experiment.entry_points
    tid = SWEEP_ID_OFFSET
    for patch in sw.patch_levels:
        for delay in sw.detection_delays:
            for k in range(sw.trials_per_cell):
                specs.append(TrialSpec(
                    trial_id=tid, experiment="sweep",
                    facility=sw.facility, profile=sw.profile,
                    portfolio="baseline_flat",
                    entry_point=entries[k % len(entries)],
                    master_seed=cfg.seed,
                    patch_override=patch, detection_override=delay))
                tid += 1
    return specs


def build_backup_specs(cfg: Config) -> list[TrialSpec]:
    """Controlled backup-strategy comparison across facilities/profiles."""
    specs: list[TrialSpec] = []
    entries = cfg.experiment.entry_points
    tid = BACKUP_ID_OFFSET
    for facility in cfg.experiment.facilities:
        for profile in cfg.experiment.profiles:
            for name in BACKUP_PORTFOLIOS:
                for k in range(cfg.experiment.trials_per_cell):
                    specs.append(TrialSpec(
                        trial_id=tid, experiment="backup",
                        facility=facility, profile=profile, portfolio=name,
                        entry_point=entries[k % len(entries)],
                        master_seed=cfg.seed))
                    tid += 1
    return specs


def _annotate_costs(df: pd.DataFrame, cfg: Config,
                    costs: dict[str, float]) -> pd.DataFrame:
    """Add the normalized-cost column for catalog portfolios."""
    def cost_of(row) -> float:
        try:
            p = get_portfolio(row["portfolio"])
        except KeyError:
            return float("nan")
        return portfolio_cost(p, cfg.profiles[row["profile"]], costs)

    df["portfolio_cost"] = df.apply(cost_of, axis=1)
    return df


def run_experiments(cfg: Config,
                    defense_costs_path: str | Path | None = None) -> dict[str, Path]:
    """Run main + sweep experiments and export raw CSVs.

    Returns a dict of output name -> written path.
    """
    log = setup_logging(resolve_path(cfg.output.logs_dir), "grrc.experiments")
    raw_dir = resolve_path(cfg.output.raw_dir)
    ensure_dirs(raw_dir)
    costs_path = defense_costs_path or resolve_path(
        "configs/defense_costs.yaml")
    costs = load_defense_costs(costs_path)

    outputs: dict[str, Path] = {}
    t0 = time.time()

    main_specs = build_main_specs(cfg)
    log.info("main experiment: %d trials (%s mode, seed=%d)",
             len(main_specs), cfg.mode, cfg.seed)
    main_df = run_specs(cfg, main_specs, desc=f"{cfg.mode}:main")
    main_df = _annotate_costs(main_df, cfg, costs)
    main_path = raw_dir / f"{cfg.mode}_main_results.csv"
    write_csv(main_df, main_path)
    outputs["main"] = main_path
    log.info("wrote %s (%d rows)", main_path, len(main_df))

    if cfg.sweep.enabled:
        sweep_specs = build_sweep_specs(cfg)
        log.info("sweep experiment: %d trials", len(sweep_specs))
        sweep_df = run_specs(cfg, sweep_specs, desc=f"{cfg.mode}:sweep")
        sweep_df["portfolio_cost"] = float("nan")
        sweep_path = raw_dir / f"{cfg.mode}_sweep_results.csv"
        write_csv(sweep_df, sweep_path)
        outputs["sweep"] = sweep_path
        log.info("wrote %s (%d rows)", sweep_path, len(sweep_df))

    backup_specs = build_backup_specs(cfg)
    log.info("controlled backup experiment: %d trials", len(backup_specs))
    backup_df = run_specs(cfg, backup_specs, portfolios=BACKUP_PORTFOLIOS,
                          desc=f"{cfg.mode}:backup")
    backup_df["portfolio_cost"] = float("nan")
    backup_path = raw_dir / f"{cfg.mode}_backup_results.csv"
    write_csv(backup_df, backup_path)
    outputs["backup"] = backup_path
    log.info("wrote %s (%d rows)", backup_path, len(backup_df))

    manifest = {
        "mode": cfg.mode,
        "master_seed": cfg.seed,
        "n_main_trials": len(main_specs),
        "n_sweep_trials": len(build_sweep_specs(cfg)) if cfg.sweep.enabled
        else 0,
        "elapsed_seconds": round(time.time() - t0, 1),
        "outputs": {k: str(v) for k, v in outputs.items()},
    }
    manifest_path = raw_dir / f"{cfg.mode}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    outputs["manifest"] = manifest_path
    return outputs

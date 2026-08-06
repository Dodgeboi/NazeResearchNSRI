"""Automated model-validation cases.

Twelve behavioral checks proving the simulation acts logically (design
requirement). Each check returns a :class:`ValidationResult`; the CLI
command ``python -m grrc.cli validate`` runs all of them and writes the
outcome table to docs/model_validation.md. The pytest suite runs the same
functions, so validation is enforced both interactively and in CI-style
test runs.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, default_config
from .defenses import (DefensePortfolio, effective_settings,
                       enumerate_portfolios, get_portfolio, portfolio_cost)
from .enums import (BackupStrategy, EntryPoint, SegmentationLevel, Service,
                    Zone)
from .models import HospitalNetwork, TrialSpec
from .network_generator import generate_network
from .propagation import RansomwareSimulation
from .optimization import select_best, summarize_portfolios
from .service_dependencies import service_availability
from .simulation import run_trial
from .statistics import bootstrap_ci
from .utilities import REPO_ROOT, trial_rng


@dataclass
class ValidationResult:
    name: str
    passed: bool
    details: str


# ---------------------------------------------------------------------------
# Helper scenario builders
# ---------------------------------------------------------------------------

def _aggressive_config() -> Config:
    """Config where compromise spreads deterministically and defenses are
    disabled: base rate 1, no patching, no detection within horizon,
    no isolation, no false positives."""
    cfg = default_config()
    cfg.simulation.base_spread_rate = 1.0
    cfg.simulation.detection_model = "fixed"
    cfg.simulation.false_positive_rate = 0.0
    cfg.network.privilege_modifiers = {
        "LOW": 1.0, "STANDARD": 1.0, "ADMIN": 1.0}
    for prof in cfg.profiles.values():
        prof.patch_coverage = 0.0
        prof.detection_delay_steps = 10 ** 6  # never within the horizon
        prof.isolation_success = 0.0
        prof.legacy_fraction = 0.0
    return cfg


def _force_deterministic_edges(net: HospitalNetwork) -> None:
    """Set every stochastic edge/node factor to 1 so p(edge) == base rate."""
    net.edge_access[:] = 1.0
    net.edge_strength[:] = 1.0
    net.edge_traversal_mod[:] = np.where(
        net.edge_traversal_mod > 0.0, 1.0, 0.0)
    net.vulnerability[:] = 1.0
    net.patched[:] = False


def _reachable_from(net: HospitalNetwork, start: int) -> set[int]:
    """BFS over edges with a positive traversal modifier."""
    seen = {start}
    frontier = [start]
    while frontier:
        nxt = []
        for u in frontier:
            for eid in net.out_edges[u]:
                if net.edge_traversal_mod[eid] <= 0.0:
                    continue
                v = int(net.edge_dst[eid])
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
        frontier = nxt
    return seen


def _toy_network(edges: list[tuple[int, int]], n: int = 3) -> HospitalNetwork:
    """Minimal hand-built network for unit-level state-machine checks."""
    zones = np.zeros(n, dtype=np.int64)  # all WORKSTATION
    src = np.array([e[0] for e in edges], dtype=np.int64)
    dst = np.array([e[1] for e in edges], dtype=np.int64)
    ones = np.ones(len(edges))
    net = HospitalNetwork(
        facility_id="toy", facility_size="toy", n_nodes=n,
        zone=zones, node_type=["workstation"] * n,
        vulnerability=np.ones(n), patched=np.zeros(n, dtype=bool),
        criticality=np.ones(n), privilege=np.ones(n, dtype=np.int64),
        detect_capability=np.ones(n), is_legacy=np.zeros(n, dtype=bool),
        edge_src=src, edge_dst=dst, edge_access=ones.copy(),
        edge_strength=ones.copy(),
        edge_cross_boundary=np.zeros(len(edges), dtype=bool),
        edge_traversal_mod=ones.copy(),
    )
    net.services = {}
    net.entry_candidates = {}
    return net


def _drop_edges(net: HospitalNetwork, keep: np.ndarray) -> HospitalNetwork:
    """New network keeping only edges where ``keep`` is True."""
    return dataclasses.replace(
        net,
        edge_src=net.edge_src[keep], edge_dst=net.edge_dst[keep],
        edge_access=net.edge_access[keep],
        edge_strength=net.edge_strength[keep],
        edge_cross_boundary=net.edge_cross_boundary[keep],
        edge_traversal_mod=net.edge_traversal_mod[keep],
        out_edges=[],  # forces adjacency rebuild in __post_init__
    )


def _make_sim(cfg: Config, net: HospitalNetwork, profile: str,
              portfolio: DefensePortfolio,
              seed: int = 1) -> RansomwareSimulation:
    eff = effective_settings(cfg.profiles[profile], portfolio)
    return RansomwareSimulation(cfg, net, eff, trial_rng(cfg.seed, seed))


_FLAT_PORTFOLIO = get_portfolio("baseline_flat")


# ---------------------------------------------------------------------------
# The 12 validation cases
# ---------------------------------------------------------------------------

def check_zero_spread() -> ValidationResult:
    """1. With transmission probability zero, only the entry node is ever
    compromised."""
    cfg = _aggressive_config()
    cfg.simulation.base_spread_rate = 0.0
    spec = TrialSpec(0, "validate", "small_clinic", "resource_constrained",
                     "baseline_flat", "workstation", master_seed=cfg.seed)
    row = run_trial(cfg, spec)
    ok = row["total_compromised"] == 1 and row["lateral_movements"] == 0
    return ValidationResult(
        "zero_spread", ok,
        f"total_compromised={row['total_compromised']} (expected 1), "
        f"lateral_movements={row['lateral_movements']} (expected 0)")


def check_guaranteed_spread() -> ValidationResult:
    """2. With p=1, no defenses and all nodes vulnerable, exactly the
    graph-reachable set becomes compromised."""
    cfg = _aggressive_config()
    rng = trial_rng(cfg.seed, 42)
    net = generate_network(
        cfg, "small_clinic", "resource_constrained", rng,
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.0,
        backup_strategy="connected")
    _force_deterministic_edges(net)
    entry = int(net.entry_candidates[EntryPoint.WORKSTATION][0])
    sim = _make_sim(cfg, net, "resource_constrained", _FLAT_PORTFOLIO)
    sim.run(entry)
    compromised = set(np.flatnonzero(sim.ever_comp).tolist())
    reachable = _reachable_from(net, entry)
    ok = compromised == reachable
    return ValidationResult(
        "guaranteed_spread", ok,
        f"compromised {len(compromised)}/{net.n_nodes} nodes; "
        f"reachable set size {len(reachable)}; sets match: {ok}")


def check_disconnected_zone() -> ValidationResult:
    """3. A zone with no permitted inbound path can never be compromised."""
    cfg = _aggressive_config()
    rng = trial_rng(cfg.seed, 43)
    net = generate_network(
        cfg, "small_clinic", "resource_constrained", rng,
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.0,
        backup_strategy="connected")
    _force_deterministic_edges(net)
    imaging = set(net.nodes_in_zone(Zone.IMAGING).tolist())
    keep = ~(np.isin(net.edge_dst, list(imaging))
             & ~np.isin(net.edge_src, list(imaging)))
    net2 = _drop_edges(net, keep)
    entry = int(net2.entry_candidates[EntryPoint.WORKSTATION][0])
    sim = _make_sim(cfg, net2, "resource_constrained", _FLAT_PORTFOLIO)
    sim.run(entry)
    breached = bool(sim.ever_comp[list(imaging)].any())
    return ValidationResult(
        "disconnected_zone", not breached,
        f"imaging zone ({len(imaging)} nodes) breached: {breached} "
        f"(expected False) while {int(sim.ever_comp.sum())} other nodes "
        f"were compromised")


def check_isolated_backup() -> ValidationResult:
    """4. Fully isolated backups cannot be compromised via propagation."""
    cfg = _aggressive_config()
    spec = TrialSpec(4, "validate", "small_clinic", "resource_constrained",
                     "isolated_backups", "workstation", master_seed=cfg.seed)
    row = run_trial(cfg, spec)
    ok = (row["backup_compromised"] == 0
          and row["total_compromised"] > 1)
    return ValidationResult(
        "isolated_backup", ok,
        f"backup_compromised={row['backup_compromised']} (expected 0) "
        f"with {row['total_compromised']} nodes compromised elsewhere")


def check_patch_immunity() -> ValidationResult:
    """5. With patch_effectiveness=1 and 100% coverage, patched nodes are
    immune, so only the entry foothold is compromised."""
    cfg = _aggressive_config()
    cfg.simulation.patch_effectiveness = 1.0
    for prof in cfg.profiles.values():
        prof.patch_coverage = 1.0
        prof.legacy_fraction = 0.0  # legacy halves patch prob; remove
    spec = TrialSpec(5, "validate", "small_clinic", "resource_constrained",
                     "profile_baseline", "workstation", master_seed=cfg.seed)
    row = run_trial(cfg, spec)
    ok = row["total_compromised"] == 1
    return ValidationResult(
        "patch_immunity", ok,
        f"total_compromised={row['total_compromised']} (expected 1: "
        f"entry foothold only)")


def check_isolation_blocks_spread() -> ValidationResult:
    """6. An isolated node cannot spread, and cannot be re-infected."""
    cfg = _aggressive_config()
    net = _toy_network([(0, 1), (1, 2)])
    sim = _make_sim(cfg, net, "resource_constrained", _FLAT_PORTFOLIO)
    sim.compromise(np.array([0]), 0)
    sim.isolated[0] = True
    rng = trial_rng(cfg.seed, 99)
    for t in range(1, 20):
        sim._spread(t, rng)
    spread_blocked = not sim.comp[1] and not sim.comp[2]
    # isolated target cannot be infected
    sim2 = _make_sim(cfg, net, "resource_constrained", _FLAT_PORTFOLIO)
    sim2.compromise(np.array([0]), 0)
    sim2.isolated[1] = True
    for t in range(1, 20):
        sim2._spread(t, rng)
    target_blocked = not sim2.comp[1]
    ok = spread_blocked and target_blocked
    return ValidationResult(
        "isolation_blocks_spread", ok,
        f"isolated source spread nothing: {spread_blocked}; "
        f"isolated target stayed clean: {target_blocked}")


def check_reproducibility() -> ValidationResult:
    """7. Identical (seed, parameters) produce identical results."""
    cfg = default_config()
    spec = TrialSpec(7, "validate", "regional_hospital",
                     "intermediate_capacity", "seg_plus_detection",
                     "internet_facing", master_seed=cfg.seed)
    a = run_trial(cfg, spec)
    b = run_trial(cfg, spec)
    ok = a == b
    diffs = [k for k in a if a[k] != b[k]] if not ok else []
    return ValidationResult(
        "reproducibility", ok,
        "two runs with identical seed/parameters are identical" if ok
        else f"fields differ: {diffs}")


def check_seed_variation() -> ValidationResult:
    """8. Different seeds can produce different stochastic outcomes."""
    cfg = default_config()
    outcomes = set()
    for tid in range(12):
        spec = TrialSpec(tid, "validate", "small_clinic",
                         "resource_constrained", "baseline_flat",
                         "workstation", master_seed=cfg.seed)
        outcomes.add(run_trial(cfg, spec)["total_compromised"])
    ok = len(outcomes) > 1
    return ValidationResult(
        "seed_variation", ok,
        f"12 different trial seeds gave {len(outcomes)} distinct "
        f"total_compromised values: {sorted(outcomes)}")


def check_service_dependency() -> ValidationResult:
    """9. Services become unavailable exactly when dependencies fail."""
    cfg = default_config()
    rng = trial_rng(cfg.seed, 9)
    net = generate_network(
        cfg, "small_clinic", "high_capacity", rng,
        segmentation=SegmentationLevel.BASIC, patch_coverage=0.9,
        backup_strategy="connected")
    thr = cfg.simulation.service_functional_fraction
    all_ok = np.ones(net.n_nodes, dtype=bool)
    a0 = service_availability(net, all_ok, thr)
    baseline_up = all(a0.values())
    # kill the EHR core node -> EHR must go down
    f1 = all_ok.copy()
    f1[net.services[Service.EHR]["core"]] = False
    ehr_down = not service_availability(net, f1, thr)[Service.EHR]
    # kill identity zone -> identity-dependent services must go down
    f2 = all_ok.copy()
    f2[net.nodes_in_zone(Zone.IDENTITY)] = False
    a2 = service_availability(net, f2, thr)
    cascade = (not a2[Service.IDENTITY] and not a2[Service.EHR]
               and not a2[Service.LABORATORY]
               and a2[Service.BACKUP_RECOVERY])
    ok = baseline_up and ehr_down and cascade
    return ValidationResult(
        "service_dependency", ok,
        f"all-up baseline: {baseline_up}; EHR down when core fails: "
        f"{ehr_down}; identity failure cascades to dependent services "
        f"but not backup: {cascade}")


def check_convergence(sample_sizes: tuple[int, ...] = (100, 250, 500, 1000)
                      ) -> ValidationResult:
    """10. Monte Carlo estimates stabilize as trial counts grow."""
    cfg = default_config()
    rows = []
    for tid in range(max(sample_sizes)):
        spec = TrialSpec(500_000 + tid, "validate", "small_clinic",
                         "resource_constrained", "baseline_flat",
                         "workstation", master_seed=cfg.seed)
        rows.append(run_trial(cfg, spec)["pct_compromised"])
    values = np.asarray(rows)
    stats_lines = []
    widths, means = [], []
    for n in sample_sizes:
        lo, hi = bootstrap_ci(values[:n], seed=cfg.seed)
        means.append(values[:n].mean())
        widths.append(hi - lo)
        stats_lines.append(
            f"n={n}: mean={means[-1]:.4f}, CI width={widths[-1]:.4f}")
    shrinks = widths[-1] < widths[0]
    stable = abs(means[-1] - means[-2]) < 0.05
    ok = shrinks and stable
    return ValidationResult(
        "convergence", ok,
        "; ".join(stats_lines)
        + f" | CI shrinks: {shrinks}, last two means within 0.05: {stable}")


def check_budget_respected() -> ValidationResult:
    """11. The optimizer never selects a portfolio exceeding its budget.

    Uses a synthetic performance table over the full enumerated portfolio
    space, so the check is exact and covers every budget/cost-scale
    combination.
    """
    cfg = default_config()
    costs = {"basic_segmentation": 3, "least_privilege_segmentation": 5,
             "patch_level_upgrade": 2, "detection_improvement": 3,
             "rapid_isolation": 5, "protected_backups": 2,
             "identity_controls": 4}
    rng = np.random.default_rng(11)
    rows = []
    profile = cfg.profiles["resource_constrained"]
    for p in enumerate_portfolios():
        cost = portfolio_cost(p, profile, costs)
        mean_hours = float(rng.uniform(5, 100))
        half_width = float(rng.uniform(1, 8))
        rows.append({
            "profile": "resource_constrained", "portfolio": p.name,
            "description": p.name, "base_cost": cost,
            "mean_hours_lost": mean_hours,
            # A real summary always carries these; the fixture must too.
            "hours_lost_ci_lo": mean_hours - half_width,
            "hours_lost_ci_hi": mean_hours + half_width,
            "catastrophic_prob": float(rng.uniform(0, 1)),
            **{c: 0 for c in ("has_basic_segmentation",
                              "has_least_privilege", "has_patch_upgrade",
                              "has_detection_improvement",
                              "has_rapid_isolation",
                              "has_protected_backups",
                              "has_identity_controls")},
        })
    summary = pd.DataFrame(rows)
    baseline_hours = 100.0
    violations = []
    for scale in (0.5, 0.75, 1.0, 1.25, 1.5):
        for budget in (5, 10, 15):
            for pick in select_best(summary, "resource_constrained",
                                    budget, scale, baseline_hours):
                if pick["cost"] > budget + 1e-9:
                    violations.append(pick)
    ok = not violations
    return ValidationResult(
        "budget_respected", ok,
        f"checked 5 cost scales x 3 budgets x 4 criteria = 60 selections; "
        f"budget violations: {len(violations)}")


def check_data_integrity() -> ValidationResult:
    """12. Exported rows contain all required fields with valid values."""
    cfg = default_config()
    rows = []
    for tid, (portfolio, entry) in enumerate([
            ("baseline_flat", "workstation"),
            ("full_defense", "vendor_connection"),
            ("isolated_backups", "medical_device")]):
        spec = TrialSpec(600_000 + tid, "validate", "small_clinic",
                         "intermediate_capacity", portfolio, entry,
                         master_seed=cfg.seed)
        rows.append(run_trial(cfg, spec))
    df = pd.DataFrame(rows)
    required = [
        "trial_id", "master_seed", "facility", "profile", "portfolio",
        "entry_point", "entry_node", "n_nodes", "n_edges", "segmentation",
        "patch_coverage", "detection_delay", "backup_strategy",
        "total_compromised", "pct_compromised", "peak_compromised",
        "zones_reached", "lateral_movements", "containment_step",
        "backup_compromised", "identity_compromised",
        "weighted_service_hours_lost", "catastrophic",
        "services_disrupted_count", "recovery_step",
        "pct_services_restored", "unrecoverable_nodes",
    ]
    problems = [c for c in required if c not in df.columns]
    if not problems:
        if df[required].isna().any().any():
            problems.append("NaN values present")
        if not df["pct_compromised"].between(0, 1).all():
            problems.append("pct_compromised outside [0,1]")
        if not df["pct_services_restored"].between(0, 1).all():
            problems.append("pct_services_restored outside [0,1]")
        if (df["total_compromised"] < 1).any():
            problems.append("total_compromised < 1")
        if (df["total_compromised"] > df["n_nodes"]).any():
            problems.append("total_compromised > n_nodes")
    ok = not problems
    return ValidationResult(
        "data_integrity", ok,
        f"{len(required)} required fields checked on 3 heterogeneous "
        f"trials; problems: {problems if problems else 'none'}")


ALL_CHECKS = [
    check_zero_spread, check_guaranteed_spread, check_disconnected_zone,
    check_isolated_backup, check_patch_immunity,
    check_isolation_blocks_spread, check_reproducibility,
    check_seed_variation, check_service_dependency, check_convergence,
    check_budget_respected, check_data_integrity,
]


def run_all_validations(fast: bool = False) -> list[ValidationResult]:
    """Run all 12 checks; ``fast`` shrinks the convergence sample sizes."""
    results = []
    for check in ALL_CHECKS:
        if check is check_convergence and fast:
            results.append(check_convergence((50, 100, 200)))
        else:
            results.append(check())
    return results


def write_validation_report(results: list[ValidationResult],
                            path: Path | None = None) -> Path:
    """Write docs/model_validation.md from validation outcomes."""
    path = path or (REPO_ROOT / "docs" / "model_validation.md")
    lines = [
        "# Model Validation Results",
        "",
        "This file is generated by `python -m grrc.cli validate`. It",
        "documents the twelve automated behavioral checks that must pass",
        "before any experiment results are trusted. Each check is also",
        "enforced by the pytest suite (`tests/test_validation_cases.py`).",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "| # | Check | Result | Details |",
        "|---|-------|--------|---------|",
    ]
    for i, r in enumerate(results, 1):
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"| {i} | {r.name} | {status} | {r.details} |")
    lines += [
        "",
        "## What each check demonstrates",
        "",
        "1. **zero_spread** — with transmission probability 0 the infection",
        "   cannot move: damage stays at the single entry foothold.",
        "2. **guaranteed_spread** — with probability 1 and no defenses, the",
        "   compromised set equals exactly the graph-reachable set (the",
        "   propagation engine respects topology, nothing more or less).",
        "3. **disconnected_zone** — removing all inbound paths to a zone",
        "   makes it unreachable to the simulated attack.",
        "4. **isolated_backup** — offline/immutable backups can never be",
        "   compromised through network propagation.",
        "5. **patch_immunity** — with patch effectiveness 1.0 and full",
        "   coverage, patched nodes are immune (documented assumption A6:",
        "   default effectiveness is 0.85, i.e. patching is strong but not",
        "   perfect; this check verifies the limiting case).",
        "6. **isolation_blocks_spread** — isolated nodes neither spread nor",
        "   receive compromise.",
        "7. **reproducibility** — identical seed + parameters give",
        "   bit-identical results.",
        "8. **seed_variation** — different seeds explore different",
        "   stochastic outcomes.",
        "9. **service_dependency** — service availability reacts correctly",
        "   to core-node failure and identity-dependency failure.",
        "10. **convergence** — Monte Carlo estimates stabilize as the trial",
        "    count grows (100 -> 250 -> 500 -> 1000).",
        "11. **budget_respected** — the optimizer never selects a portfolio",
        "    whose (scaled) cost exceeds the active budget.",
        "12. **data_integrity** — exported rows contain every required",
        "    field with values in valid ranges.",
        "",
    ]
    # Create the parent directory if it does not exist: a clean checkout that
    # ships without docs/ (e.g. the code+data bundle) must still be able to run
    # `validate` — and `reproduce` starts with it.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

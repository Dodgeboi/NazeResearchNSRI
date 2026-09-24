"""Analyse the defender evaluation: containment vs clinical outcome, and the shield.

Reads data/agentic/raw/defender_evaluation.csv.gz and writes tables to
data/agentic/processed/ and data/agentic/RESULTS.md, generated from the tables
so no number in the prose is typed by hand. Paired bootstrap intervals
resample scenarios within (profile, entry point) cells. They are descriptive:
the run is exploratory and none of these contrasts was prespecified.
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "agentic" / "raw" / "defender_evaluation.csv.gz"
PROC = ROOT / "data" / "agentic" / "processed"
RESULTS = ROOT / "data" / "agentic" / "RESULTS.md"
DRAWS = 2000
SEED = 20260924

HOURS = "weighted_service_hours_lost"
K4 = "sustained_clinical_outage_k4"
K1 = "sustained_clinical_outage_k1"
SPREAD = "ever_compromised_fraction"
SELF = "self_inflicted_steps"
METRICS = (HOURS, K4, K1, SPREAD, SELF)
KEYS = ["scenario_id", "profile", "entry_point"]
MODES = ("connected", "disconnect", "zone_lockdown", "islands",
         "micro_lockdown")

LABELS = {
    "passive": "Passive (no network action)",
    "passive_replicas": "Passive, replica estate",
    "disconnect": "Disconnect-on-alert playbook",
    "disconnect_shielded": "Disconnect-on-alert + shield",
    "zone_lockdown": "Zone lockdown on alert",
    "micro_lockdown_upper_bound": "Micro lockdown on alert (upper bound)",
    "islands": "Dependency-closed islands on alert",
    "islands_shielded": "Dependency-closed islands + shield",
}
for r in ("containment", "soft", "clinical"):
    for a in ("today", "replicas"):
        LABELS[f"q_{r}_{a}"] = f"Q-learner, {r} reward, {a} estate"
        LABELS[f"q_{r}_{a}_shielded"] = (f"Q-learner, {r} reward, {a} estate"
                                         " + shield")


def _reference(condition: str, architecture: str) -> str:
    return "passive_replicas" if architecture == "replicas" else "passive"


def _resample_index(frame: pd.DataFrame, rng) -> np.ndarray:
    frame = frame.reset_index(drop=True)
    cells = [np.asarray(v) for v in
             frame.groupby(["profile", "entry_point"]).indices.values()]
    return np.concatenate(
        [c[rng.integers(0, c.size, size=(DRAWS, c.size))] for c in cells],
        axis=1)


def summary(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (cond, profile), g in pd.concat(
            [raw.assign(profile_group="pooled"),
             raw.assign(profile_group=raw.profile)]).groupby(
                 ["condition", "profile_group"], sort=False):
        total_steps = sum(g[f"steps_{m}"].sum() for m in MODES
                          if f"steps_{m}" in g)
        rows.append({
            "condition": cond, "profile": profile, "n": len(g),
            "architecture": g.architecture.iloc[0],
            "shielded": int(g.shielded.iloc[0]), "kind": g.kind.iloc[0],
            "spread": g[SPREAD].mean(), "hours": g[HOURS].mean(),
            "p_outage_k4": g[K4].mean(), "p_outage_k1": g[K1].mean(),
            "self_inflicted_steps": g[SELF].mean(),
            "p_any_self_inflicted": (g[SELF] > 0).mean(),
            "shield_interventions": g.shield_interventions.mean(),
            **{f"share_{m}": (g[f"steps_{m}"].sum() / total_steps
                              if f"steps_{m}" in g and total_steps else 0.0)
               for m in MODES},
        })
    return pd.DataFrame(rows)


def _paired(raw, ref, trt):
    a = raw[raw.condition == ref].set_index(KEYS)[list(METRICS)]
    b = raw[raw.condition == trt].set_index(KEYS)[list(METRICS)]
    b = b.reindex(a.index)
    if len(a) != len(b) or b.isna().any().any():
        raise ValueError(f"{trt} is not paired with {ref}")
    return (b - a).reset_index()


#: Head-to-head comparisons the paper states in words, so that a claim like
#: "matches the best unshielded defender" rests on a paired interval rather
#: than on two means. These were chosen after seeing pooled results; like
#: every contrast here they are exploratory, not prespecified.
KEY_PAIRS = [
    ("disconnect", "islands"),
    ("q_soft_today", "q_containment_today_shielded"),
    ("q_clinical_today", "q_containment_today_shielded"),
    ("q_containment_today", "q_soft_today"),
    ("islands", "q_containment_replicas_shielded"),
    ("q_soft_replicas", "q_containment_replicas_shielded"),
    ("q_containment_today_shielded", "q_containment_replicas_shielded"),
]


def _rng_for(*identity: str) -> np.random.Generator:
    """A bootstrap stream keyed by the contrast itself.

    One shared stream made every interval depend on which other contrasts
    were computed first, so adding a comparison moved all the others. Keying
    the stream by the contrast's own identity makes each interval a function
    of its data alone.
    """
    return np.random.default_rng(
        [SEED, zlib.crc32("|".join(identity).encode())])


def contrasts(raw: pd.DataFrame) -> pd.DataFrame:
    conds = raw.drop_duplicates("condition").set_index("condition")
    pairs = [("key", a, b) for a, b in KEY_PAIRS
             if a in conds.index and b in conds.index]
    for cond, row in conds.iterrows():
        ref = _reference(cond, row.architecture)
        if cond != ref:
            pairs.append(("vs_passive", ref, cond))
        if row.shielded:
            pairs.append(("shield_effect", cond[: -len("_shielded")], cond))
    out = []
    for family, ref, trt in pairs:
        full = _paired(raw, ref, trt)
        for profile in ["pooled", *sorted(full.profile.unique())]:
            diff = (full if profile == "pooled"
                    else full[full.profile == profile]).reset_index(drop=True)
            idx = _resample_index(diff, _rng_for(family, ref, trt, profile))
            rec = {"family": family, "reference": ref, "treatment": trt,
                   "profile": profile, "n": len(diff)}
            for m in (HOURS, K4, K1, SPREAD):
                x = diff[m].to_numpy()
                boot = x[idx].mean(axis=1)
                rec.update({f"d_{m}": x.mean(),
                            f"d_{m}_lo": float(np.percentile(boot, 2.5)),
                            f"d_{m}_hi": float(np.percentile(boot, 97.5))})
            rec["share_worse_hours"] = float((diff[HOURS] > 1e-9).mean())
            rec["share_better_hours"] = float((diff[HOURS] < -1e-9).mean())
            out.append(rec)
    return pd.DataFrame(out)


def rank_reversal(summ: pd.DataFrame) -> dict:
    """Do containment and clinical outcome rank the unshielded agents alike?"""
    pooled = summ[(summ.profile == "pooled") & (summ.shielded == 0)
                  & (summ.condition != "micro_lockdown_upper_bound")]
    tau, p = kendalltau(pooled.spread.rank(), pooled.hours.rank())
    order_contain = list(pooled.sort_values("spread").condition)
    order_clinical = list(pooled.sort_values("hours").condition)
    return {"kendall_tau": float(tau), "p_value": float(p),
            "n_agents": int(len(pooled)),
            "best_by_containment": order_contain[0],
            "best_by_clinical": order_clinical[0],
            "order_by_containment": order_contain,
            "order_by_clinical": order_clinical}


def deployment_rules(summ: pd.DataFrame) -> pd.DataFrame:
    """POST HOC: shield never, always, or only in the fast-detection profile.

    Chosen after seeing the per-profile results, and evaluated on the same
    data, so it is illustration, not evidence. Profiles are equally weighted,
    as in the pooled means.
    """
    by = summ[summ.profile != "pooled"].set_index(["condition", "profile"])
    pooled = summ[summ.profile == "pooled"].set_index("condition")
    rows = []
    for cond in pooled.index:
        if not cond.endswith("_shielded"):
            continue
        base = cond[: -len("_shielded")]
        fast_only = (by.loc[(cond, "high_capacity")].hours
                     + by.loc[(base, "intermediate_capacity")].hours
                     + by.loc[(base, "resource_constrained")].hours) / 3
        values = {"never": pooled.loc[base].hours,
                  "always": pooled.loc[cond].hours, "fast_only": fast_only}
        rows.append({"defender": base, **values,
                     "best": min(values, key=values.get)})
    return pd.DataFrame(rows)


def _fmt_ci(r, m, scale=1.0, unit="", digits=1):
    return (f"{r[f'd_{m}'] * scale:+.{digits}f}{unit} "
            f"[{r[f'd_{m}_lo'] * scale:+.{digits}f}, "
            f"{r[f'd_{m}_hi'] * scale:+.{digits}f}]")


def render(summ, con, ranks, manifest) -> str:
    pooled = summ[summ.profile == "pooled"].set_index("condition")
    n_cells = len(manifest["conditions"])
    lines = [
        "# Autonomous defenders and the dependency-closure shield — "
        "exploratory results", "",
        "> **Exploratory.** No protocol was frozen. Intervals are "
        "descriptive, not tests. Properties of the simulator under its "
        "declared assumptions, not of any hospital. Generated by "
        "`scripts/analyze_defenders.py` — do not edit by hand.", "",
        f"{n_cells} conditions x {manifest['scenarios_per_cell']} scenarios "
        f"per (profile, entry point) cell = {manifest['rows']} episodes. "
        f"Evaluation seed {manifest['eval_seed']}, disjoint from training. "
        "Decisions every "
        f"{manifest['decision_interval_steps']} steps (one simulated hour).",
        "", "## Every defender, pooled", "",
        "Containment = mean share of nodes ever compromised (lower is "
        "better) — the signal autonomous cyber-defence benchmarks score. "
        "Clinical = weighted service-hours lost and the probability of a "
        "sustained outage of all four clinical services. *Self-inflicted* = "
        "share of episodes in which the defender's own network action took an "
        "available clinical service down.", "",
        "| Defender | Containment | Clinical hours | P(sustained, all 4) | "
        "Self-inflicted | Shield interventions / episode |",
        "|---|---|---|---|---|---|",
    ]
    for cond in manifest["conditions"]:
        r = pooled.loc[cond]
        lines.append(
            f"| {LABELS.get(cond, cond)} | {r.spread:.3f} | {r.hours:.1f} | "
            f"{r.p_outage_k4:.3f} | {r.p_any_self_inflicted:.0%} | "
            f"{r.shield_interventions:.1f} |")

    lines += ["", "## Containment does not rank defenders the way clinical "
              "outcome does", "",
              f"Kendall's tau between the containment ranking and the "
              f"clinical-hours ranking of the {ranks['n_agents']} unshielded "
              f"defenders: **{ranks['kendall_tau']:+.2f}** "
              f"(p = {ranks['p_value']:.2f}). Best by containment: "
              f"`{ranks['best_by_containment']}`. Best by clinical outcome: "
              f"`{ranks['best_by_clinical']}`.", "",
              "| Rank | By containment | By clinical hours |",
              "|---|---|---|"]
    for i, (a, b) in enumerate(zip(ranks["order_by_containment"],
                                   ranks["order_by_clinical"]), 1):
        lines.append(f"| {i} | `{a}` | `{b}` |")

    for family, title in (("shield_effect", "What the shield changes "
                           "(shielded minus unshielded, paired)"),
                          ("vs_passive", "Each defender against passive "
                           "(paired, same architecture)"),
                          ("key", "Head-to-head comparisons stated in the "
                           "paper (paired)")):
        lines += ["", f"## {title}", "",
                  "| Treatment | Reference | Δ clinical hours | "
                  "Δ P(sustained, all 4) | Δ containment | Worse |",
                  "|---|---|---|---|---|---|"]
        for _, r in con[(con.family == family)
                        & (con.profile == "pooled")].iterrows():
            lines.append(
                f"| `{r.treatment}` | `{r.reference}` | {_fmt_ci(r, HOURS)} "
                f"| {_fmt_ci(r, K4, 100, ' pp')} | "
                f"{_fmt_ci(r, SPREAD, 100, ' pp')} | "
                f"{r.share_worse_hours:.0%} |")

    lines += ["", "## What the shield changes, by profile (paired)", "",
              "| Defender | Profile | Δ clinical hours | "
              "Δ P(sustained, all 4) | Δ containment | Worse |",
              "|---|---|---|---|---|---|"]
    for _, r in con[(con.family == "shield_effect")
                    & (con.profile != "pooled")].iterrows():
        lines.append(
            f"| `{r.reference}` | {r.profile} | {_fmt_ci(r, HOURS)} | "
            f"{_fmt_ci(r, K4, 100, ' pp')} | "
            f"{_fmt_ci(r, SPREAD, 100, ' pp')} | {r.share_worse_hours:.0%} |")

    rules = deployment_rules(summ)
    lines += ["", "## POST HOC: when to enable the shield", "",
              "Chosen after seeing the per-profile results and evaluated on "
              "the same data: an illustration of the design question, not "
              "evidence for any rule. Pooled clinical hours.", "",
              "| Defender | Never | Always | Fast-detection profile only | "
              "Best |", "|---|---|---|---|---|"]
    for _, r in rules.iterrows():
        lines.append(f"| `{r.defender}` | {r.never:.1f} | {r.always:.1f} | "
                     f"{r.fast_only:.1f} | {r.best} |")

    lines += ["", "## Where learned defenders spend their time (pooled "
              "share of steps by network mode)", "",
              "| Defender | connected | disconnect | zone lockdown | islands |",
              "|---|---|---|---|---|"]
    for cond in manifest["conditions"]:
        if not cond.startswith("q_"):
            continue
        r = pooled.loc[cond]
        lines.append(f"| `{cond}` | {r.share_connected:.0%} | "
                     f"{r.share_disconnect:.0%} | {r.share_zone_lockdown:.0%} "
                     f"| {r.share_islands:.0%} |")

    lines += ["", "## By profile (clinical hours; unshielded -> shielded)",
              "", "| Defender | Profile | Unshielded | Shielded |",
              "|---|---|---|---|"]
    by = summ[summ.profile != "pooled"].set_index(["condition", "profile"])
    for cond in manifest["conditions"]:
        if not cond.endswith("_shielded"):
            continue
        base = cond[: -len("_shielded")]
        for profile in sorted(summ[summ.profile != "pooled"].profile.unique()):
            lines.append(f"| `{base}` | {profile} | "
                         f"{by.loc[(base, profile)].hours:.1f} | "
                         f"{by.loc[(cond, profile)].hours:.1f} |")
    return "\n".join(lines) + "\n"


_DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
           "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}
BS = "\\"


def macro(*parts: str) -> str:
    """A LaTeX-safe command name: letters only, CamelCase, prefixed num."""
    name = "".join(w[:1].upper() + w[1:] for part in parts
                   for w in part.replace("-", "_").split("_") if w)
    return BS + "num" + "".join(_DIGITS.get(ch, ch) for ch in name)


def _latex_int(n: int) -> str:
    return f"{n:,}".replace(",", "{,}")


def write_numbers(summ, con, ranks, manifest, train_episodes,
                  path: Path) -> None:
    """Every number the paper quotes, as LaTeX macros generated from data."""
    pooled = summ[summ.profile == "pooled"].set_index("condition")
    lines = ["% Generated by scripts/analyze_defenders.py. Do not edit."]

    def define(name: str, value: str) -> None:
        lines.append(f"{BS}newcommand{{{name}}}{{{value}}}")

    cells = len(manifest.get("profiles", [])) or 3
    entries = len(manifest.get("entry_points", [])) or 5
    define(BS + "numScenariosPerCell", str(manifest["scenarios_per_cell"]))
    define(BS + "numEvalScenarios",
           _latex_int(manifest["scenarios_per_cell"] * cells * entries))
    define(BS + "numEpisodes", _latex_int(manifest["rows"]))
    define(BS + "numConditions", str(len(manifest["conditions"])))
    define(BS + "numTrainEpisodes", _latex_int(train_episodes))
    pct = BS + "%"
    for cond, r in pooled.iterrows():
        define(macro(cond, "spread"), f"{100 * r.spread:.1f}")
        define(macro(cond, "hours"), f"{r.hours:.1f}")
        define(macro(cond, "kfour"), f"{100 * r.p_outage_k4:.1f}")
        define(macro(cond, "kone"), f"{100 * r.p_outage_k1:.1f}")
        define(macro(cond, "self", "pct"),
               f"{100 * r.p_any_self_inflicted:.0f}{pct}")
        define(macro(cond, "interventions"), f"{r.shield_interventions:.1f}")
        for m in MODES:
            define(macro(cond, "share", m), f"{100 * r[f'share_{m}']:.0f}{pct}")
    for _, r in con.iterrows():
        if r.family == "key":
            tag, base = "key", f"{r.reference}_to_{r.treatment}"
        else:
            tag = "vs" if r.family == "vs_passive" else "shield"
            base = r.treatment if tag == "vs" else r.reference
        where = () if r.profile == "pooled" else (r.profile,)
        for m, key, scale in ((HOURS, "hours", 1), (K4, "kfour", 100),
                              (K1, "kone", 100), (SPREAD, "spread", 100)):
            d = r[f"d_{m}"] * scale
            lo, hi = r[f"d_{m}_lo"] * scale, r[f"d_{m}_hi"] * scale
            define(macro(tag, base, *where, key), f"{d:+.1f}")
            define(macro(tag, base, *where, key, "abs"), f"{abs(d):.1f}")
            define(macro(tag, base, *where, key, "ci"),
                   f"{d:+.1f} [{lo:+.1f}, {hi:+.1f}]")
        define(macro(tag, base, *where, "worse"),
               f"{100 * r.share_worse_hours:.0f}{pct}")
    by_profile = summ[summ.profile != "pooled"]
    for _, r in by_profile.iterrows():
        define(macro(r.condition, r.profile, "hours"), f"{r.hours:.1f}")
        define(macro(r.condition, r.profile, "spread"),
               f"{100 * r.spread:.1f}")
    def ordinal(n: int) -> str:
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd",
                                                   3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    for kind in ("containment", "clinical"):
        for i, cond in enumerate(ranks[f"order_by_{kind}"], 1):
            define(macro(cond, "rank", kind), ordinal(i))
    rules = deployment_rules(summ)
    words = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
             6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    for rule in ("never", "always", "fast_only"):
        count = int((rules.best == rule).sum())
        define(macro("posthoc", rule, "best", "count"),
               words.get(count, str(count)))
    define(BS + "numPosthocDefenders",
           words.get(len(rules), str(len(rules))))
    define(BS + "numRankTau", f"{ranks['kendall_tau']:+.2f}")
    define(BS + "numRankP", f"{ranks['p_value']:.2f}")
    define(BS + "numRankAgents", str(ranks["n_agents"]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


TABLE_ROWS = [  # (condition, label, group)
    ("passive", "Passive", "Scripted, today's estate"),
    ("zone_lockdown", "Zone lockdown", None),
    ("micro_lockdown_upper_bound", "Micro lockdown$^\\dagger$", None),
    ("disconnect", "Disconnect", None),
    ("disconnect_shielded", "\\quad + shield", None),
    ("q_containment_today", "Containment reward", "Q-learners, today's estate"),
    ("q_containment_today_shielded", "\\quad + shield", None),
    ("q_soft_today", "Soft penalty", None),
    ("q_soft_today_shielded", "\\quad + shield", None),
    ("q_clinical_today", "Clinical reward", None),
    ("q_clinical_today_shielded", "\\quad + shield", None),
    ("passive_replicas", "Passive", "Replica estate"),
    ("islands", "Islands (scripted)", None),
    ("islands_shielded", "\\quad + shield", None),
    ("q_containment_replicas", "Q, containment", None),
    ("q_containment_replicas_shielded", "\\quad + shield", None),
    ("q_soft_replicas", "Q, soft penalty", None),
    ("q_soft_replicas_shielded", "\\quad + shield", None),
    ("q_clinical_replicas", "Q, clinical", None),
    ("q_clinical_replicas_shielded", "\\quad + shield", None),
]


def write_table(summ: pd.DataFrame, path: Path) -> None:
    """Table I rows, generated from data."""
    pooled = summ[summ.profile == "pooled"].set_index("condition")
    hc = summ[summ.profile == "high_capacity"].set_index("condition")
    out = ["% Generated by scripts/analyze_defenders.py. Do not edit."]
    for cond, label, group in TABLE_ROWS:
        if cond not in pooled.index:
            continue
        if group:
            out.append(f"\\midrule\\multicolumn{{6}}{{l}}{{\\emph{{{group}}}}}\\\\")
        r = pooled.loc[cond]
        out.append(
            f"{label} & {100 * r.spread:.1f} & {r.hours:.1f} & "
            f"{hc.loc[cond].hours:.1f} & {100 * r.p_outage_k4:.1f} & "
            f"{100 * r.p_any_self_inflicted:.0f} \\\\")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


SHIELD_ROWS = [
    ("disconnect", "Disconnect (scripted)"),
    ("islands", "Islands (scripted, replicas)"),
    ("q_containment_today", "Q, containment"),
    ("q_soft_today", "Q, soft penalty"),
    ("q_clinical_today", "Q, clinical"),
    ("q_containment_replicas", "Q, containment, replicas"),
    ("q_soft_replicas", "Q, soft, replicas"),
    ("q_clinical_replicas", "Q, clinical, replicas"),
]
PROFILE_ORDER = ("high_capacity", "intermediate_capacity",
                 "resource_constrained")


def write_shield_table(con: pd.DataFrame, path: Path) -> None:
    """Table II rows: shield effect on clinical hours, by profile, paired."""
    rows = con[con.family == "shield_effect"].set_index(
        ["reference", "profile"])
    out = ["% Generated by scripts/analyze_defenders.py. Do not edit."]
    for cond, label in SHIELD_ROWS:
        cells = []
        for profile in PROFILE_ORDER:
            r = rows.loc[(cond, profile)]
            d, lo, hi = (r.d_weighted_service_hours_lost,
                         r.d_weighted_service_hours_lost_lo,
                         r.d_weighted_service_hours_lost_hi)
            text = (f"${d:+.1f}$ {{\\scriptsize$[{lo:+.1f}, "
                    f"{hi:+.1f}]$}}")
            # Bold where the whole interval is below zero: the shield helps.
            cells.append(f"\\textbf{{{text}}}" if hi < 0 else text)
        out.append(f"{label} & " + " & ".join(cells) + " \\\\")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    raw = pd.read_csv(RAW, float_precision="round_trip")
    manifest = json.loads((RAW.parent / "manifest.json").read_text("utf-8"))
    PROC.mkdir(parents=True, exist_ok=True)
    summ = summary(raw)
    con = contrasts(raw)
    ranks = rank_reversal(summ)
    summ.to_csv(PROC / "defender_summary.csv", index=False)
    con.to_csv(PROC / "paired_contrasts.csv", index=False)
    (PROC / "rank_reversal.json").write_text(json.dumps(ranks, indent=2),
                                             encoding="utf-8")
    RESULTS.write_text(render(summ, con, ranks, manifest), encoding="utf-8")
    models = ROOT / "data" / "agentic" / "models"
    episodes = max((len(json.loads(p.read_text("utf-8")))
                    for p in models.glob("q_*_returns.json")), default=0)
    write_numbers(summ, con, ranks, manifest, episodes,
                  ROOT / "docs" / "aidc26" / "generated_numbers.tex")
    write_table(summ, ROOT / "docs" / "aidc26" / "table_defenders.tex")
    write_shield_table(con, ROOT / "docs" / "aidc26" / "table_shield.tex")
    print(f"wrote {PROC}, {RESULTS} and generated_numbers.tex")


if __name__ == "__main__":
    main()

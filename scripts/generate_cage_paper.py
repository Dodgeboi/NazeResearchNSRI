#!/usr/bin/env python3
"""Generate the CAGE-2 certified-evaluation paper's numbers and tables from committed CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/cage"
PAPER = ROOT / "docs/cage_certified"
FIXED = ["b_line", "meander", "delayed_b_line", "meander_then_b_line"]
BASELINES = ["sleep", "react-remove", "react-restore", "champion", "champion+fallback"]
LLM_TAGS = {"claude-haiku-4-5-nothink": "Hn", "claude-sonnet-5-nothink": "Sn",
            "claude-haiku-4-5": "Ht"}
SHORT = {"b_line": "B\\_line", "meander": "Meander", "delayed_b_line": "Delayed",
         "meander_then_b_line": "M$\\to$B"}
NAMES = {"sleep": "Sleep", "react-remove": "React-remove", "react-restore": "React-restore",
         "champion": "Challenge winner", "champion+fallback": "Winner + fallback",
         "claude-haiku-4-5-nothink": "Haiku 4.5", "claude-sonnet-5-nothink": "Sonnet 5",
         "claude-haiku-4-5": "Haiku 4.5 + thinking"}


def f2(x):
    return f"{float(x):.2f}"


def f1(x):
    return f"{float(x):.1f}"


def pct(x):
    return f"{100 * float(x):.0f}"


def content():
    verify_manifest(DATA / "cage_certified_manifest.json")
    verify_manifest(DATA / "cage_eval_manifest.json")
    params = json.loads((DATA / "cage_eval_manifest.json").read_text())["parameters"]
    s = pd.read_csv(DATA / "certified_summary.csv")
    w = pd.read_csv(DATA / "worst_case.csv")
    rk = pd.read_csv(DATA / "rankings.csv").set_index("defender")
    stop = pd.read_csv(DATA / "stopping.csv")
    eps = pd.read_csv(DATA / "episodes.csv")

    def cell(d, a, col):
        return s[(s.defender == d) & (s.attacker == a)].iloc[0][col]

    def worst(d, scope, col):
        return w[(w.defender == d) & (w.scope == scope)].iloc[0][col]

    champ_adapt = eps[(eps.defender == "champion") & (eps.attacker == "adaptive")]
    base_stop = stop[stop.defender.isin(BASELINES) & (stop.resolved_at > 0)]
    v = {
        "CgEpisodes": str(params["episodes"]), "CgSteps": str(params["steps"]),
        "CgStepBound": f1(-params["step_bound"]),
        "CgEpisodeBound": f"{-params['step_bound'] * params['steps']:.0f}",
        "CgDefenders": str(len(BASELINES)),
        "CgChampSeenReward": f1(worst("champion", "seen", "reward_mean_seen")),
        "CgChampSeenBreachUp": f2(worst("champion", "seen", "breach_certified")),
        "CgChampDelayedReward": f1(cell("champion", "delayed_b_line", "reward_mean")),
        "CgChampDelayedBreach": pct(cell("champion", "delayed_b_line", "breach_mean")),
        "CgChampDelayedLow": f2(cell("champion", "delayed_b_line", "breach_lower")),
        "CgChampDelayedUp": f2(cell("champion", "delayed_b_line", "breach_upper")),
        "CgChampAllBreachCert": f2(worst("champion", "all", "breach_certified")),
        "CgChampAdaptBreach": pct(cell("champion", "adaptive", "breach_mean")),
        "CgChampAdaptUp": f2(cell("champion", "adaptive", "breach_upper")),
        "CgChampAdaptDelayed": str(int((champ_adapt.strategy == "delayed_b_line").sum())),
        "CgFixDelayedReward": f1(cell("champion+fallback", "delayed_b_line", "reward_mean")),
        "CgFixAllBreachCert": f2(worst("champion+fallback", "all", "breach_certified")),
        "CgFixAdaptUp": f2(cell("champion+fallback", "adaptive", "breach_upper")),
        "CgRestoreAllBreachCert": f2(worst("react-restore", "all", "breach_certified")),
        "CgRemoveAllBreachCert": f2(worst("react-remove", "all", "breach_certified")),
        "CgRestoreSeenReward": f1(worst("react-restore", "seen", "reward_mean_seen")),
        "CgChampRankMean": str(int(rk.loc["champion", "rank_mean_seen"])),
        "CgChampRankCert": str(int(rk.loc["champion", "rank_certified_all"])),
        "CgStopMin": str(int(base_stop.resolved_at.min())),
        "CgStopMax": str(int(base_stop.resolved_at.max())),
        "CgStopMedian": f"{base_stop.resolved_at.median():.0f}",
        "CgStopResolved": str(len(base_stop)),
        "CgStopPairs": str(int(stop.defender.isin(BASELINES).sum())),
    }
    val = DATA / "champion_validation.csv"
    if val.exists():
        cv = pd.read_csv(val).set_index("attacker")
        v.update({"CgValMeanderPort": f2(cv.loc["meander", "port_mean"]),
                  "CgValMeanderPub": f2(cv.loc["meander", "published_mean"]),
                  "CgValBlinePort": f2(cv.loc["b_line", "port_mean"]),
                  "CgValBlinePub": f2(cv.loc["b_line", "published_mean"]),
                  "CgValEpisodes": str(int(cv.episodes.iloc[0]))})

    llm_present = [d for d in LLM_TAGS if d in set(s.defender)]
    total_cost = 0.0
    for d in llm_present:
        t = LLM_TAGS[d]
        g = s[s.defender == d]
        records = []
        for p in sorted((DATA / "llm" / d).glob("*.jsonl")):
            records += [json.loads(line) for line in p.read_text().splitlines()]
        r = pd.DataFrame(records)
        total_cost += r.cost_usd.sum()
        have_all = set(FIXED) <= set(g.attacker)
        v.update({
            t + "Per": str(int(g.n.min())),
            t + "Episodes": str(int(g.n.sum())),
            t + "SeenReward": f1(r[r.attacker.isin(["b_line", "meander"])].reward.mean()),
            t + "DelayedReward": f1(cell(d, "delayed_b_line", "reward_mean")),
            t + "DelayedBreach": pct(cell(d, "delayed_b_line", "breach_mean")),
            t + "BlineBreach": pct(cell(d, "b_line", "breach_mean")),
            t + "AllBreachCert": f2(worst(d, "all", "breach_certified")) if have_all else "n/a",
            t + "Invalid": str(int(r.invalid.sum())), t + "Calls": str(int(r.calls.sum())),
            t + "CostEp": f"{r.cost_usd.mean():.2f}", t + "Cost": f"{r.cost_usd.sum():.2f}",
            t + "Minutes": f1(r.seconds.mean() / 60),
        })
    v["CgLlmCost"] = f"{total_cost:.2f}"
    paired = pd.read_csv(DATA / "paired.csv")
    for d in llm_present:
        t = LLM_TAGS[d]
        g = s[s.defender == d]
        v[t + "Max"] = str(int(g.n.max()))
        v[t + "Breaches"] = str(int(round((g.breach_mean * g.n).sum())))
        # cost of certifying at the winner's precision: as many episodes per fixed attacker
        records = []
        for p_ in sorted((DATA / "llm" / d).glob("*.jsonl")):
            records += [json.loads(line) for line in p_.read_text().splitlines()]
        per_ep = pd.DataFrame(records).cost_usd.mean()
        v[t + "CertCost"] = f"{per_ep * params['episodes'] * len(FIXED):.0f}"
        v[t + "CertHours"] = f"{pd.DataFrame(records).seconds.mean() * params['episodes'] * len(FIXED) / 3600:.0f}"
        row = paired[(paired.defender == d) & (paired.reference == "champion")
                     & (paired.attacker == "delayed_b_line")]
        if not row.empty:
            r = row.iloc[0]
            v[t + "PairN"] = str(int(r.n))
            v[t + "PairOnlyChamp"] = str(int(r.only_reference))
            v[t + "PairOnlyLlm"] = str(int(r.only_llm))
            v[t + "PairP"] = f"{r.sign_test_p:.3f}"
            v[t + "PairVerdict"] = str(r.verdict)

    # LLM attacker (strategy selector).
    atk_path = DATA / "attacker_summary.csv"
    if atk_path.exists():
        atk = pd.read_csv(atk_path)
        AMODEL = {"claude-haiku-4-5": "Ah", "claude-sonnet-5": "As"}
        for m, tag in AMODEL.items():
            for dname, dtag in (("champion", "Champ"), ("champion+fallback", "Fix"),
                                ("react-restore", "Restore")):
                row = atk[(atk.model == m) & (atk.defender == dname)]
                if row.empty:
                    continue
                r = row.iloc[0]
                v[tag + dtag + "Breach"] = f"{r.breach_rate:.2f}"
                v[tag + dtag + "Lo"] = f"{r.breach_lower:.2f}"
                v[tag + dtag + "Hi"] = f"{r.breach_upper:.2f}"
                v[tag + dtag + "Best"] = f"{r.best_fixed_rate:.2f}"
                v[tag + dtag + "Rand"] = f"{r.random_rate:.2f}"
                v[tag + dtag + "ExpThree"] = f"{r.exp3_rate:.2f}"
                v[tag + dtag + "Share"] = f"{100 * r.best_strategy_share:.0f}"
                v[tag + dtag + "Eps"] = str(int(r.episodes))
        v["AtkCost"] = f"{atk.cost_usd.sum():.2f}"
        v["AtkModels"] = str(atk.model.nunique())

    # Attacker family (delay sweep): the blind spot's threshold and range, and the repair.
    fam_path = DATA / "family_summary.csv"
    if fam_path.exists():
        fam = pd.read_csv(fam_path)
        ch = fam[(fam.defender == "champion") & (fam.base == "b_line")].set_index("delay")
        fix = fam[(fam.defender == "champion+fallback") & (fam.base == "b_line")]
        res = fam[(fam.defender == "react-restore") & (fam.base == "b_line")]
        hi_delays = ch[ch.index >= 2]
        v["FamChampDOne"] = f"{ch.loc[1, 'breach_rate']:.2f}" if 1 in ch.index else "n/a"
        v["FamChampDOneUp"] = f"{ch.loc[1, 'breach_upper']:.2f}" if 1 in ch.index else "n/a"
        v["FamChampDTwo"] = f"{ch.loc[2, 'breach_rate']:.2f}" if 2 in ch.index else "n/a"
        v["FamChampDTwoLo"] = f"{ch.loc[2, 'breach_lower']:.2f}" if 2 in ch.index else "n/a"
        v["FamChampMin"] = f"{hi_delays.breach_rate.min():.2f}"
        v["FamChampMax"] = f"{hi_delays.breach_rate.max():.2f}"
        v["FamChampHiMinLo"] = f"{hi_delays.breach_lower.min():.2f}"
        v["FamDelays"] = str(int(ch.index.max()))
        v["FamFixMax"] = f"{fix.breach_rate.max():.2f}"
        v["FamFixMaxUp"] = f"{fix.breach_upper.max():.2f}"
        v["FamRestoreMax"] = f"{res.breach_rate.max():.2f}"
        mdr = fam[(fam.defender == "champion") & (fam.base == "meander")]
        if not mdr.empty:
            v["FamChampMeander"] = f"{mdr.breach_rate.iloc[0]:.2f}"
            v["FamChampMeanderUp"] = f"{mdr.breach_upper.iloc[0]:.2f}"
        v["FamEps"] = str(int(fam.n.iloc[0]))

    # Primitive-action LLM attacker.
    prim_path = DATA / "primitive_summary.csv"
    if prim_path.exists():
        prim = pd.read_csv(prim_path)
        PTAG = {"sleep": "Sleep", "champion": "Champ", "champion+fallback": "Fix",
                "react-restore": "Restore"}
        for _, r in prim.iterrows():
            t = "Prim" + PTAG.get(r.defender, r.defender)
            v[t + "Breach"] = f"{r.breach_rate:.2f}"
            v[t + "Lo"] = f"{r.breach_lower:.2f}"
            v[t + "Hi"] = f"{r.breach_upper:.2f}"
            v[t + "Eps"] = str(int(r.episodes))
        v["PrimCost"] = f"{prim.cost_usd.sum():.2f}"
        v["PrimInvalid"] = f"{prim.invalid_per_episode.mean():.2f}"
        v["PrimModel"] = "Haiku~4.5" if (prim.model == "claude-haiku-4-5").any() else "n/a"

    # Second environment (CAGE Challenge 1, Scenario1b).
    e1b_path = DATA / "env1b_worst.csv"
    if e1b_path.exists():
        e1b = pd.read_csv(e1b_path)
        allw = e1b[e1b.scope == "all"].set_index("defender")
        E1 = {"sleep": "Sleep", "react-remove": "Remove", "react-restore": "Restore"}
        for d, tag in E1.items():
            if d in allw.index:
                v["EnvB" + tag + "Cert"] = f"{allw.loc[d, 'breach_certified']:.2f}"
        esum = DATA / "env1b_summary.csv"
        if esum.exists():
            v["EnvBEps"] = str(int(pd.read_csv(esum).n.max()))
        v["EnvBDefenders"] = str(len(allw))

    gen = {"cage_numbers.tex": "% Generated; do not edit.\n" + "".join(
        "\\newcommand{\\" + k + "}{" + val + "}\n" for k, val in sorted(v.items()))}

    rows = []
    for d in BASELINES + llm_present:
        row = [NAMES[d]]
        for a in FIXED + ["adaptive"]:
            m = s[(s.defender == d) & (s.attacker == a)]
            if m.empty:
                row.append("--")
                continue
            m = m.iloc[0]
            row.append(f"{f2(m.breach_mean)} ({f2(m.breach_upper)})")
        row.append(str(int(s[s.defender == d].n.min())))
        rows.append(row)
    gen["table_cage_breach_rows.tex"] = "% Generated from certified_summary.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    rows = []
    for d in BASELINES + llm_present:
        if d not in set(w.defender) or d not in rk.index:
            continue
        rows.append([NAMES[d], f1(worst(d, "seen", "reward_mean_seen")),
                     str(int(rk.loc[d, "rank_mean_seen"])),
                     f2(worst(d, "seen", "breach_certified")), f2(worst(d, "all", "breach_certified")),
                     str(int(rk.loc[d, "rank_certified_all"])),
                     SHORT[str(worst(d, "all", "breach_worst_attacker"))]])
    gen["table_cage_rank_rows.tex"] = "% Generated from worst_case.csv and rankings.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)
    if atk_path.exists():
        NAME = {"claude-haiku-4-5": "Haiku 4.5", "claude-sonnet-5": "Sonnet 5"}
        DN = {"champion": "Challenge winner", "champion+fallback": "Winner + fallback",
              "react-restore": "React-restore"}
        rows = []
        for m in ("claude-haiku-4-5", "claude-sonnet-5"):
            for dname in ("champion", "champion+fallback", "react-restore"):
                row = atk[(atk.model == m) & (atk.defender == dname)]
                if row.empty:
                    continue
                r = row.iloc[0]
                rows.append([NAME.get(m, m), DN[dname], str(int(r.episodes)),
                             f"{r.breach_rate:.2f} ({r.breach_lower:.2f}--{r.breach_upper:.2f})",
                             f"{r.best_fixed_rate:.2f}", f"{r.random_rate:.2f}", f"{r.exp3_rate:.2f}",
                             f"{100 * r.best_strategy_share:.0f}\\%"])
        gen["table_cage_attacker_rows.tex"] = "% Generated from attacker_summary.csv.\n" + "".join(
            " & ".join(r) + " \\\\\n" for r in rows)
    return gen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    gen = content()
    PAPER.mkdir(parents=True, exist_ok=True)
    if args.check:
        for name, value in gen.items():
            if (PAPER / name).read_text(encoding="utf-8") != value:
                raise AssertionError("stale generated TeX: " + name)
        print("CAGE paper values verified")
        return 0
    for name, value in gen.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(gen)} generated files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

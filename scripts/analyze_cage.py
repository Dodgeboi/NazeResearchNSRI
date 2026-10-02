#!/usr/bin/env python3
"""Certified evaluation tables for the CAGE Challenge 2 study.

Reads the committed episodes (``data/cage/episodes.csv`` for non-LLM defenders,
``data/cage/llm/<model>/<attacker>.jsonl`` for language-model defenders) and writes:

- ``certified_summary.csv``: per (defender, attacker), the mean reward, breach rate and
  impacted fraction with time-uniform 95% bounds (betting for fixed attackers, the
  martingale bound for the adaptive one);
- ``worst_case.csv``: per defender, the joint worst case over the attackers it was built
  for (``seen``) and over all fixed attackers (``all``), with the attacker attaining it;
- ``rankings.csv``: each defender's rank by mean reward on the seen attackers versus by
  certified worst case over all attackers;
- ``stopping.csv``: for each pair, the first episode at which the time-uniform bounds
  settle whether the breach rate is below a threshold, versus the fixed sample size;
- ``paired.csv``: language-model defenders against reference defenders on shared seeds
  (paired differences in breach and reward, with time-uniform bounds).

Deterministic; writes a provenance manifest.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest

from grrc.cage.certify import bounds, episodes_to_resolve, worst_case
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/cage"
ALPHA = 0.05
STEP_BOUND = -15.8
SEEN = ("b_line", "meander")
FIXED = ("b_line", "meander", "delayed_b_line", "meander_then_b_line")
BREACH_THRESHOLD = 0.2
BASELINES = ("sleep", "react-remove", "react-restore", "champion", "champion+fallback")
REFERENCES = ("champion", "react-restore")


def load():
    frames = [pd.read_csv(DATA / "episodes.csv")]
    llm_inputs = sorted((DATA / "llm").glob("*/*.jsonl"))
    rows = []
    for p in llm_inputs:
        for line in p.read_text().splitlines():
            r = json.loads(line)
            rows.append(dict(defender=r["model"], attacker=r["attacker"], adaptive=False,
                             episode=r["episode"], seed=r["seed"], strategy=r["attacker"],
                             reward=r["reward"], impacts=r["impacts"], steps=r["steps"],
                             impact_fraction=r["impact_fraction"], breached=r["breached"],
                             invalid=r.get("invalid"), cost_usd=r.get("cost_usd")))
    if rows:
        frames.append(pd.DataFrame(rows))
    df = pd.concat(frames, ignore_index=True).sort_values(["defender", "attacker", "episode"])
    return df.reset_index(drop=True), llm_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    df, llm_inputs = load()
    steps = int(df.steps.iloc[0])
    r_min = STEP_BOUND * steps

    summary = []
    for (d, a), g in df.groupby(["defender", "attacker"], sort=False):
        adaptive = bool(g.adaptive.iloc[0])
        rl, rh = bounds(g.reward, r_min, 0, ALPHA, adaptive)
        bl, bh = bounds(g.breached.astype(float), 0, 1, ALPHA, adaptive)
        il, ih = bounds(g.impact_fraction, 0, 1, ALPHA, adaptive)
        summary.append(dict(defender=d, attacker=a, adaptive=adaptive, n=len(g),
                            reward_mean=g.reward.mean(), reward_lower=rl, reward_upper=rh,
                            breach_mean=g.breached.mean(), breach_lower=bl, breach_upper=bh,
                            impact_mean=g.impact_fraction.mean(), impact_lower=il, impact_upper=ih,
                            invalid_per_episode=g["invalid"].mean() if "invalid" in g else None,
                            cost_usd=g["cost_usd"].sum() if "cost_usd" in g else None))
    summary = pd.DataFrame(summary)

    worst = []
    for d, g in df[~df.adaptive.astype(bool)].groupby("defender", sort=False):
        for scope, attackers in (("seen", SEEN), ("all", FIXED)):
            have = [a for a in attackers if a in set(g.attacker)]
            if len(have) < len(attackers):
                continue
            rew = {a: (g[g.attacker == a].reward.values, r_min, 0, False) for a in have}
            bre = {a: (g[g.attacker == a].breached.astype(float).values, 0, 1, False) for a in have}
            rv, ra, _ = worst_case(rew, ALPHA, higher_is_better=True)
            bv, ba, _ = worst_case(bre, ALPHA, higher_is_better=False)
            worst.append(dict(defender=d, scope=scope, attackers=len(have),
                              n_per_attacker=int(g.groupby("attacker").size().min()),
                              reward_certified=rv, reward_worst_attacker=ra,
                              breach_certified=bv, breach_worst_attacker=ba,
                              reward_mean_seen=g[g.attacker.isin(SEEN)].reward.mean()))
    worst = pd.DataFrame(worst)

    # Ranks only among the non-LLM defenders, which share the same number of episodes.
    ranks = worst[(worst.scope == "all") & worst.defender.isin(BASELINES)][
        ["defender", "reward_certified", "breach_certified"]].copy()
    seen_mean = worst[worst.scope == "seen"].set_index("defender").reward_mean_seen
    ranks["reward_mean_seen"] = ranks.defender.map(seen_mean)
    ranks["rank_mean_seen"] = ranks.reward_mean_seen.rank(ascending=False, method="min").astype(int)
    ranks["rank_certified_all"] = ranks.breach_certified.rank(ascending=True, method="min").astype(int)
    ranks = ranks.sort_values("rank_mean_seen")

    stopping = []
    for (d, a), g in df[~df.adaptive.astype(bool)].groupby(["defender", "attacker"], sort=False):
        n = episodes_to_resolve(g.breached.astype(float).values, 0, 1, ALPHA, BREACH_THRESHOLD,
                                higher_is_better=False)
        stopping.append(dict(defender=d, attacker=a, n=len(g), threshold=BREACH_THRESHOLD,
                             resolved_at=n if n is not None else -1,
                             verdict=("unknown" if n is None else
                                      "below" if bounds(g.breached.astype(float).values[:n], 0, 1,
                                                        ALPHA)[1] < BREACH_THRESHOLD else "above")))
    stopping = pd.DataFrame(stopping)

    # Paired comparisons on shared seeds, per attacker. Breach: among discordant seeds
    # (exactly one defender breached), the share where only the reference was breached;
    # under "no difference" it is 1/2, so a time-uniform lower bound above 1/2 certifies
    # that the language-model defender is breached less often (and an upper bound below
    # 1/2 the reverse). Discordant pairs are i.i.d. because episodes are. Reward: the
    # mean paired difference, descriptive only (its declared range is too wide to bound
    # usefully at these sample sizes).
    paired = []
    fixed = df[~df.adaptive.astype(bool)]
    for d in sorted(set(fixed.defender) - set(BASELINES)):
        for ref in REFERENCES:
            for a in FIXED:
                llm = fixed[(fixed.defender == d) & (fixed.attacker == a)].set_index("seed")
                base = fixed[(fixed.defender == ref) & (fixed.attacker == a)].set_index("seed")
                seeds = llm.index.intersection(base.index)
                if len(seeds) < 2:
                    continue
                lb = llm.loc[seeds, "breached"].astype(bool)
                rb = base.loc[seeds, "breached"].astype(bool)
                only_ref, only_llm = int((rb & ~lb).sum()), int((lb & ~rb).sum())
                disc = only_ref + only_llm
                if disc >= 2:
                    y = [1.0] * only_ref + [0.0] * only_llm
                    lo, hi = bounds(y, 0, 1, ALPHA)
                else:
                    lo, hi = 0.0, 1.0
                verdict = ("llm breached less" if lo > 0.5 else
                           "reference breached less" if hi < 0.5 else "unresolved")
                paired.append(dict(defender=d, reference=ref, attacker=a, n=len(seeds),
                                   llm_breaches=int(lb.sum()), reference_breaches=int(rb.sum()),
                                   only_reference=only_ref, only_llm=only_llm,
                                   share_lower=lo, share_upper=hi, verdict=verdict,
                                   # Conventional fixed-sample comparison (not time-uniform).
                                   sign_test_p=(binomtest(only_ref, disc, 0.5).pvalue
                                                if disc else 1.0),
                                   reward_difference=float((llm.loc[seeds, "reward"]
                                                            - base.loc[seeds, "reward"]).mean())))
    paired = pd.DataFrame(paired)

    # Adaptive LLM attacker: did it learn to exploit the winner's blind spot? Each episode
    # the model chose one scripted strategy; we compare its breach rate to the paired
    # counterfactuals of always playing one fixed strategy (on the same seeds), to the
    # best fixed strategy in hindsight, to uniform-random choice, and to the scripted EXP3
    # adaptive attacker. Episodes are i.i.d. given the defender, so the breach bound holds.
    attacker, attacker_strategy, attacker_inputs = [], [], []
    scripted = df[~df.adaptive.astype(bool)].set_index(["defender", "attacker", "seed"]).breached
    adaptive_breach = df[df.adaptive.astype(bool)].groupby("defender").breached.mean()
    for pth in sorted((DATA / "attacker").glob("*/*.jsonl")):
        raw = [json.loads(line) for line in pth.read_text().splitlines()]
        seen, recs = set(), []           # keep one record per episode (guards against re-runs)
        for r in sorted(raw, key=lambda r: r["episode"]):
            if r["episode"] not in seen:
                seen.add(r["episode"]); recs.append(r)
        if not recs:
            continue
        attacker_inputs.append(pth)
        model, d = recs[0]["model"], recs[0]["defender"]
        br = [bool(r["breached"]) for r in recs]
        lo, hi = bounds([float(b) for b in br], 0, 1, ALPHA)
        cf = {}  # counterfactual breach rate of always playing strategy s on these seeds
        for s in FIXED:
            vals = [scripted.get((d, s, r["seed"])) for r in recs]
            vals = [bool(v) for v in vals if v is not None]
            cf[s] = sum(vals) / len(vals) if vals else float("nan")
        best = max(cf, key=cf.get)
        from collections import Counter
        chosen = Counter(r["strategy"] for r in recs)
        attacker.append(dict(
            model=model, defender=d, episodes=len(recs), breaches=sum(br),
            breach_rate=sum(br) / len(br), breach_lower=lo, breach_upper=hi,
            best_fixed_strategy=best, best_fixed_rate=cf[best],
            random_rate=sum(cf[s] for s in FIXED) / len(FIXED),
            exp3_rate=float(adaptive_breach.get(d, float("nan"))),
            best_strategy_share=chosen[best] / len(recs),
            invalid=sum(1 for r in recs if r["strategy"] not in FIXED),
            cost_usd=sum(r.get("cost_usd") or 0 for r in recs)))
        for s in FIXED:
            attacker_strategy.append(dict(model=model, defender=d, strategy=s,
                                          chosen=chosen[s], counterfactual_rate=cf[s]))
    attacker = pd.DataFrame(attacker)
    attacker_strategy = pd.DataFrame(attacker_strategy)

    # Attacker family: breach rate as a function of a fixed delay, certified. Shows the
    # winner's blind spot across the whole family (not one hand-picked pause) and that the
    # one-line repair holds for every delay.
    family, family_inputs = [], []
    fpath = DATA / "family.csv"
    if fpath.exists():
        family_inputs = [fpath, DATA / "cage_family_manifest.json"]
        fam = pd.read_csv(fpath)
        for (d, a), g in fam.groupby(["defender", "attacker"], sort=False):
            bl, bh = bounds(g.breached.astype(float), 0, 1, ALPHA)
            m = re.match(r"delay(\d+)_(\w+)", str(a))
            family.append(dict(defender=d, attacker=a,
                               base=(m.group(2) if m else a),
                               delay=(int(m.group(1)) if m else -1), n=len(g),
                               breach_rate=g.breached.mean(), breach_lower=bl, breach_upper=bh))
    family = pd.DataFrame(family)

    # Primitive-action LLM attacker: the model issues raw CybORG actions. We report the
    # certified breach rate (its lower bound is an attacker-side guarantee) per defender.
    primitive, primitive_inputs = [], []
    for pth in sorted((DATA / "primitive_attacker").glob("*/*.jsonl")):
        recs = [json.loads(line) for line in pth.read_text().splitlines()]
        seen, rr = set(), []
        for r in sorted(recs, key=lambda r: r["episode"]):
            if r["episode"] not in seen:
                seen.add(r["episode"]); rr.append(r)
        if not rr:
            continue
        primitive_inputs.append(pth)
        br = [bool(r["breached"]) for r in rr]
        lo, hi = bounds([float(b) for b in br], 0, 1, ALPHA)
        primitive.append(dict(model=rr[0]["model"], defender=rr[0]["defender"], episodes=len(rr),
                              breaches=sum(br), breach_rate=sum(br) / len(br),
                              breach_lower=lo, breach_upper=hi,
                              invalid_per_episode=sum(r.get("invalid", 0) for r in rr) / len(rr),
                              cost_usd=sum(r.get("cost_usd") or 0 for r in rr)))
    primitive = pd.DataFrame(primitive)

    # Second environment (CAGE Challenge 1, Scenario1b): the protocol applied to the generic
    # defenders, certified, to show it is not specific to Scenario2.
    env1b_summary, env1b_worst, env1b_inputs = [], [], []
    e1b = DATA / "env1b/episodes.csv"
    if e1b.exists():
        env1b_inputs = [e1b, DATA / "env1b/cage_env1b_manifest.json"]
        edf = pd.read_csv(e1b)
        for (d, a), g in edf.groupby(["defender", "attacker"], sort=False):
            adaptive = bool(g.adaptive.iloc[0])
            bl, bh = bounds(g.breached.astype(float), 0, 1, ALPHA, adaptive)
            rl, rh = bounds(g.reward, r_min, 0, ALPHA, adaptive)
            env1b_summary.append(dict(defender=d, attacker=a, adaptive=adaptive, n=len(g),
                                      reward_mean=g.reward.mean(), reward_lower=rl, reward_upper=rh,
                                      breach_mean=g.breached.mean(), breach_lower=bl, breach_upper=bh))
        for d, g in edf[~edf.adaptive.astype(bool)].groupby("defender", sort=False):
            for scope, attackers in (("seen", SEEN), ("all", FIXED)):
                have = [a for a in attackers if a in set(g.attacker)]
                if len(have) < len(attackers):
                    continue
                bre = {a: (g[g.attacker == a].breached.astype(float).values, 0, 1, False) for a in have}
                bv, ba, _ = worst_case(bre, ALPHA, higher_is_better=False)
                env1b_worst.append(dict(defender=d, scope=scope, attackers=len(have),
                                        n_per_attacker=int(g.groupby("attacker").size().min()),
                                        breach_certified=bv, breach_worst_attacker=ba,
                                        reward_mean_seen=g[g.attacker.isin(SEEN)].reward.mean()))
    env1b_summary, env1b_worst = pd.DataFrame(env1b_summary), pd.DataFrame(env1b_worst)

    outputs = []
    frames = [("certified_summary", summary), ("worst_case", worst), ("rankings", ranks),
              ("stopping", stopping), ("paired", paired)]
    if not attacker.empty:
        frames += [("attacker_summary", attacker), ("attacker_strategy", attacker_strategy)]
    if not family.empty:
        frames += [("family_summary", family)]
    if not primitive.empty:
        frames += [("primitive_summary", primitive)]
    if not env1b_summary.empty:
        frames += [("env1b_summary", env1b_summary), ("env1b_worst", env1b_worst)]
    for name, frame in frames:
        path = DATA / f"{name}.csv"
        write_csv(frame, path)
        outputs.append(path)
    inputs = [Path(__file__), DATA / "episodes.csv", DATA / "cage_eval_manifest.json",
              ROOT / "src/grrc/cage/certify.py", ROOT / "src/grrc/betting.py",
              ROOT / "src/grrc/comparison.py", ROOT / "src/grrc/provenance.py",
              ROOT / "src/grrc/utilities.py"] + llm_inputs + attacker_inputs + \
             family_inputs + primitive_inputs + env1b_inputs
    manifest = build_manifest(
        run_id="cage-certified", stage="analysis",
        description="Certified (time-uniform, distribution-free) evaluation of CAGE Challenge 2 "
                    "defenders, including language-model defenders, against fixed, unseen and "
                    "adaptive attackers.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(alpha=ALPHA, step_bound=STEP_BOUND, steps=steps, seen=list(SEEN),
                        fixed=list(FIXED), breach_threshold=BREACH_THRESHOLD,
                        worst_case="joint over attackers, Bonferroni split of alpha"))
    write_manifest(manifest, DATA / "cage_certified_manifest.json")
    print(worst.round(3).to_string(index=False))
    print(ranks.round(3).to_string(index=False))


if __name__ == "__main__":
    main()

"""Pre-submission checks for docs/aidc26 that do not need a LaTeX install.

Every number macro used is generated, every reference has a label, every
citation has a bibliography entry, every figure file exists, and nothing
identifies the authors (double-blind). Exits non-zero on any failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "docs" / "aidc26"
SOURCES = ["main.tex", "results_section.tex", "discussion_section.tex"]
BS = "\\"

#: Strings that must not appear in an anonymised submission.
IDENTIFYING = ["Agrawal", "Dharanidharan", "Upadhyay", "Dodgeboi",
               "Binded-Person", "NazeResearch", "github.com/Dodgeboi"]


def claim_checks() -> list[str]:
    """Every qualitative claim in the paper, as an assertion on the data.

    The numbers in the paper regenerate from data; the words do not. If a
    re-run changes a result, this fails instead of leaving prose that no
    longer matches its numbers.
    """
    import json

    import pandas as pd

    proc = ROOT / "data" / "agentic" / "processed"
    con = pd.read_csv(proc / "paired_contrasts.csv")
    summ = pd.read_csv(proc / "defender_summary.csv")
    ranks = json.loads((proc / "rank_reversal.json").read_text("utf-8"))
    pooled = summ[summ.profile == "pooled"].set_index("condition")
    h = "weighted_service_hours_lost"
    k4 = "sustained_clinical_outage_k4"
    sp = "ever_compromised_fraction"

    def row(family, ref, trt, profile="pooled"):
        r = con[(con.family == family) & (con.reference == ref)
                & (con.treatment == trt) & (con.profile == profile)]
        assert len(r) == 1, (family, ref, trt, profile)
        return r.iloc[0]

    def spans_zero(r, m):
        return r[f"d_{m}_lo"] <= 0 <= r[f"d_{m}_hi"]

    shielded = [c[: -len("_shielded")] for c in pooled.index
                if c.endswith("_shielded")]
    learners = [c for c in pooled.index
                if c.startswith("q_") and not c.endswith("_shielded")]
    replica_learners = [c for c in learners if c.endswith("_replicas")]
    claims = {
        "disconnect improves containment and adds clinical hours":
            row("vs_passive", "passive", "disconnect")[f"d_{sp}_hi"] < 0
            and row("vs_passive", "passive", "disconnect")[f"d_{h}_lo"] > 0,
        "islands cut 'just as hard' as disconnect (within 1 point)":
            abs(pooled.loc["islands"].spread
                - pooled.loc["disconnect"].spread) < 0.01,
        "islands lose fewer hours than disconnect (interval below 0)":
            row("key", "disconnect", "islands")[f"d_{h}_hi"] < 0,
        "containment is 'informative on average' (0.3 < tau < 0.7)":
            0.3 < ranks["kendall_tau"] < 0.7,
        "containment learner 'indistinguishable from passive' pooled":
            spans_zero(row("vs_passive", "passive", "q_containment_today"), h),
        "every learner self-inflicts":
            all(pooled.loc[c].p_any_self_inflicted > 0 for c in learners),
        "no shielded defender self-inflicts":
            all(pooled.loc[f"{c}_shielded"].p_any_self_inflicted == 0
                for c in shielded),
        "soft learner on replicas is the best defender evaluated":
            pooled.hours.idxmin() == "q_soft_replicas",
        "shield helps every defender in high-capacity (all intervals < 0)":
            all(row("shield_effect", c, f"{c}_shielded",
                    "high_capacity")[f"d_{h}_hi"] < 0 for c in shielded),
        "shield costs containment/soft learners on replicas in RC (> 0)":
            all(row("shield_effect", c, f"{c}_shielded",
                    "resource_constrained")[f"d_{h}_lo"] > 0
                for c in ("q_containment_replicas", "q_soft_replicas")),
        "shield helps disconnect and containment learner pooled (< 0)":
            all(row("shield_effect", c, f"{c}_shielded")[f"d_{h}_hi"] < 0
                for c in ("disconnect", "q_containment_today")),
        "shielded containment learner 'matches' best unshielded (spans 0)":
            spans_zero(row("key", "q_soft_today",
                           "q_containment_today_shielded"), h),
        "shield leaves clinical learner unchanged (spans 0)":
            spans_zero(row("shield_effect", "q_clinical_today",
                           "q_clinical_today_shielded"), h),
        "shield costs soft learners and clinical-replicas pooled (> 0)":
            all(row("shield_effect", c, f"{c}_shielded")[f"d_{h}_lo"] > 0
                for c in ("q_soft_today", "q_soft_replicas",
                          "q_clinical_replicas")),
        "containment-replicas: hours 'barely move', sustained outage rises":
            spans_zero(row("shield_effect", "q_containment_replicas",
                           "q_containment_replicas_shielded"), h)
            and row("shield_effect", "q_containment_replicas",
                    "q_containment_replicas_shielded")[f"d_{k4}_lo"] > 0,
        "shielded replica learners beat passive in every profile":
            all(row("vs_passive", "passive_replicas", f"{c}_shielded",
                    p)[f"d_{h}"] < 0 for c in replica_learners
                for p in ("high_capacity", "intermediate_capacity",
                          "resource_constrained")),
    }
    for name, ok in claims.items():
        print(("  ok    " if ok else "  FALSE ") + name)
    return [f"claim no longer true: {n}" for n, ok in claims.items() if not ok]


def main() -> int:
    text = {f: (PAPER / f).read_text(encoding="utf-8") for f in SOURCES}
    everything = "\n".join(text.values())
    failures = []

    used = set(re.findall(re.escape(BS) + r"(num[A-Z][A-Za-z]*)", everything))
    generated = (PAPER / "generated_numbers.tex").read_text(encoding="utf-8")
    defined = set(re.findall(
        re.escape(BS + "newcommand{" + BS) + r"(num[A-Za-z]*)\}", generated))
    for name in sorted(used - defined):
        failures.append(f"undefined number macro: {BS}{name}")

    refs = set(re.findall(re.escape(BS) + r"ref\{([^}]*)\}", everything))
    labels = set(re.findall(re.escape(BS) + r"label\{([^}]*)\}", everything))
    for ref in sorted(refs - labels):
        failures.append(f"undefined reference: {ref}")

    cites = set()
    for group in re.findall(re.escape(BS) + r"cite\{([^}]*)\}", everything):
        cites |= {c.strip() for c in group.split(",")}
    bib = (PAPER / "references.bib").read_text(encoding="utf-8")
    keys = set(re.findall(r"^@\w+\{([^,]+),", bib, re.M))
    for cite in sorted(cites - keys):
        failures.append(f"citation without bib entry: {cite}")

    for fig in re.findall(re.escape(BS) + r"includegraphics(?:\[[^\]]*\])?\{([^}]*)\}",
                          everything):
        if not (PAPER / fig).exists():
            failures.append(f"missing figure file: {fig}")

    for f, t in text.items():
        for word in IDENTIFYING:
            if word.lower() in t.lower():
                failures.append(f"identifying string {word!r} in {f}")

    print("claims:")
    failures += claim_checks()
    print(f"number macros: {len(used)} used, {len(defined)} generated")
    print(f"references: {len(refs)}; citations: {len(cites)} "
          f"({len(keys - cites)} bib entries unused: {sorted(keys - cites)})")
    for failure in failures:
        print("FAIL", failure)
    print("OK" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

# AIDC @ ACSAC 2026 — submission checklist

Workshop: Agentic AI in Offensive and Defensive Cyber Operations (AIDC), with ACSAC 2026,
Los Angeles, 7 December 2026. The workshop site (aidcworkshop.github.io) is not reachable
from the build environment, so the rows below come from a web-indexed copy of the CFP plus
the author-notified deadline extension. **Confirm every value on the live site and in
HotCRP before uploading.**

| Requirement (CFP) | Value |
|---|---|
| Deadline | **2026-10-02, Anywhere on Earth** (extended from 2026-09-25); notification 2026-10-16; camera-ready 2026-10-30 |
| Format | Double-column IEEE conference, US Letter; `\documentclass[conference,compsoc]{IEEEtran}`, IEEEtran v1.8b |
| Length | Regular ≤ 12 pages; short / work-in-progress ≤ 6 pages; references and appendices excluded |
| Review | Double-blind; submissions must be properly anonymized |
| System | ACSAC HotCRP; WIP is a category selected at submission, not a title marker |
| Presentation | At least one author registers and presents |

## Primary submission (regular paper) — submit this one

**Certified Evaluation of Autonomous Cyber Defenders: A Five-Step Delay Breaks the
CAGE-2 Champion** — `docs/cage_certified/main.tex` / `main.pdf`.

| | Value |
|---|---|
| Track | Regular / full paper (≤ 12 pp excluding references) |
| Length | 7 pp total (~6.5 pp body + references), within the 12 pp regular limit |
| Template | IEEEtran conference+compsoc, US Letter (612×792 pt) — verified `pdfinfo` |
| Anonymized | Author block "Anonymous Author(s)"; empty PDF author metadata; no repository paths, URLs or names in the source or PDF (only third-party citations, e.g. Hannay, which do not identify the authors) |
| Contribution | A certified evaluation protocol (time-uniform, distribution-free bounds; adaptive-attacker martingale variant; joint worst case over unseen attackers); a framework-free NumPy port of the CAGE-2 winner; the finding that a delayed start defeats the winner (certified across a whole delay family) while a one-line repair restores the guarantee and the certified ranking reverses; two LLM attackers (a strategy selector that finds the blind spot unaided, and a primitive-action attacker that operates raw CybORG actions but rarely rediscovers the timing weakness); Claude defenders certified with the dollar/episode cost of certifying an LLM; and the protocol replicated on a second environment (CAGE Challenge 1) |
| AI-use statement | Yes (Limitations, "Artifact and AI use") |
| Reproducibility | Pinned CybORG + winner commits, hash-checked weights; all numbers generated macros; `generate_cage_paper.py --check` passes; byte-identical analysis re-runs (episodes, family, second environment); tests + `run_full_audit.py` (9/9, 29 manifests) green |

## Also available (not required to submit)

Two earlier, independently anonymized papers remain in the repo if you want to submit more
than one. They are distinct contributions and cite each other only anonymously.

| | Paper A (regular) | Paper B (WIP) |
|---|---|---|
| Title | Uncoverable by Design: The Ceiling that Seven Years of MITRE ATT&CK Mitigation Gaps Place on Autonomous Cyber Defense | A Certified Cyber Range for Automated Defenders: Provable Residual-Risk Scores Against an Adaptive Adversary |
| Source / PDF | `docs/attack_gaps/main.tex` / `main.pdf` | `docs/defense_range/main.tex` / `main.pdf` |
| Length | 8 pp incl. refs+appendix (limit 12 excl.) | 4 pp incl. refs (limit 6) |

The CAGE paper is the strongest fit for AIDC's agentic offence/defence scope; A and B
overlap it in the certificate machinery, so submitting all three invites self-overlap
review comments. If you submit only one, submit the CAGE paper.

## What only you can do

1. Confirm the extended deadline, double-blind policy and WIP category on the live AIDC
   site and in HotCRP before uploading.
2. Create or confirm the ACSAC HotCRP account; register the submission; **select the
   regular / full-paper category** (the paper is ~6.5 pp of body, within the 12 pp limit).
3. Enter the real author list and conflicts in HotCRP (never in the PDF).
4. Keep or remove the AI-use statement per ACSAC's AI policy (it does not identify authors).
5. Double-blind vs. this public repo: this repository is public and names the author. If
   the policy forbids a discoverable version, make the repo private until notification, or
   keep the paper source out of the public default branch. The PDF itself is anonymized.
6. Upload `docs/cage_certified/main.pdf` (and A/B only if you chose to submit them).

## Rebuild (CAGE paper)

    source .venv/bin/activate
    python scripts/analyze_cage.py                 # clean tree; or --allow-dirty
    python scripts/generate_cage_paper.py && python scripts/plot_cage.py
    (cd docs/cage_certified && latexmk -pdf main.tex)
    python scripts/generate_cage_paper.py --check  # numbers match the committed tables

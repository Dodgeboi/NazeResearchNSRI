# AIDC @ ACSAC 2026 — submission checklist

Workshop: Agentic AI in Offensive and Defensive Cyber Operations (AIDC), with ACSAC 2026,
Los Angeles, 7 December 2026. Requirements below were taken from the call for papers as
indexed by web search on 2026-09-24 (the workshop site, aidcworkshop.github.io, was not
reachable from the build environment). Confirm them on the site before uploading.

| Requirement (CFP) | Value |
|---|---|
| Deadline | **2026-09-25, Anywhere on Earth**; notification 2026-10-16 |
| Format | Double-column IEEE conference, US Letter; `\documentclass[conference,compsoc]{IEEEtran}`, IEEEtran v1.8b |
| Length | Regular ≤ 12 pages; short/WIP ≤ 6 pages; references and appendices excluded |
| Review | Double-blind; submissions must be properly anonymized |
| System | ACSAC HotCRP |
| Presentation | At least one author registers and presents |

## The two submissions

They are distinct contributions and cite each other only anonymously.

| | Paper A (regular) | Paper B (WIP) |
|---|---|---|
| Title | Uncoverable by Design: The Ceiling that Seven Years of MITRE ATT&CK Mitigation Gaps Place on Autonomous Cyber Defense | A Certified Cyber Range for Automated Defenders: Provable Residual-Risk Scores Against an Adaptive Adversary |
| Source / PDF | `docs/attack_gaps/main.tex` / `main.pdf` | `docs/defense_range/main.tex` / `main.pdf` |
| Contribution | Measurement of ATT&CK mitigation gaps over 15 releases, the certification ceiling they impose on any defender, documented ransomware use, gap persistence, minimal repair, greedy reference defender | Evaluation environment scoring defenders with provable certificates; typical vs adaptive adversary; four reference defenders and their optimality gap |
| Template | IEEEtran conference+compsoc, US Letter (612×792 pt) | same |
| Length | 8 pages including references and appendix (limit 12 excluding them) | 3 pages including references (limit 6) |
| Anonymized | Author block "Anonymous Author(s)", no repository paths or links, empty PDF author metadata | same; Paper A cited as "Anonymous, concurrent submission" |
| AI-use statement | Yes (Limitations, "Artifact and AI use") | Yes ("Reproducibility and AI use") |

## What only you can do

1. Create or confirm HotCRP accounts and register both submissions before the deadline.
2. Enter the real author lists and conflicts in HotCRP (not in the PDFs).
3. Decide whether to keep the AI-use statements, and check ACSAC's AI policy.
4. Check the double-blind policy on public preprints and repositories: this repository is
   public and names the authors. If the policy forbids discoverable versions, make the
   repository private until notification, or remove the papers from it.
5. For the concurrent-submission citation, tell the chairs (HotCRP comment) that A and B
   are related but distinct, if the form allows it.
6. Upload `docs/attack_gaps/main.pdf` and `docs/defense_range/main.pdf`.

## Rebuild

    python scripts/analyze_attack_history.py      # clean tree; or --allow-dirty
    python scripts/generate_gaps_paper.py && python scripts/plot_attack_history.py
    python scripts/generate_range_paper.py
    (cd docs/attack_gaps && latexmk -pdf main.tex)
    (cd docs/defense_range && latexmk -pdf main.tex)

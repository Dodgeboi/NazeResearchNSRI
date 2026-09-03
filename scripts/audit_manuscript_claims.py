#!/usr/bin/env python3
"""Automated claim audit: does the manuscript say what the artifacts show?

The WP0 audit found the manuscript defining the sustained-outage endpoint one
way while the code computed another, with a 70-test suite passing throughout,
because no test asserted the manuscript's definitions. This script closes that
gap mechanically. It is the checking half of
``generate_manuscript_numbers.py`` and it exits non-zero on any failure.

Six checks:

1. **No hand-typed result numbers.** Every number in a results or abstract
   context must come from a generated macro. Bare numerals that look like
   results are reported with their line and context.
2. **No undefined macros.** Every ``\\Num``-style macro the manuscript uses
   must exist in ``generated_numbers.tex``.
3. **No orphan macros.** A generated macro nothing uses usually means a
   claim was deleted but its supporting analysis was not, or vice versa.
4. **Endpoint definitions match the registry.** The manuscript's endpoint
   table must state the definitions ``grrc.endpoints`` holds, so prose and
   implementation cannot drift apart again.
5. **Red-line claims are absent.** The handoff and the calibration
   memorandum list claims the model cannot support. Each is matched as a
   pattern, not a literal string, so a paraphrase is caught too.
6. **Required disclosures are present.** The framing the evidence permits —
   synthetic, partially calibrated, non-identifiability, normalized units —
   must actually appear.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from grrc.endpoints import ENDPOINTS

MANUSCRIPT = Path("docs/manuscript/main.tex")
GENERATED = Path("docs/manuscript/generated_numbers.tex")

#: Claims the model cannot support, from the handoff's red-line list and the
#: calibration memorandum. Patterns, so paraphrases are caught.
RED_LINES: list[tuple[str, str]] = [
    (r"calibrated\s+to\s+(u\.?s\.?|american|real)?\s*hospitals?",
     "claims the model is calibrated to hospitals; no hospital telemetry "
     "identifies any internal coefficient"),
    (r"patching\s+is\s+\d+(\.\d+)?\s*%\s*effective",
     "states a patch effectiveness as a real-world fact"),
    (r"segmentation\s+reduces\s+spread\s+by\s+\d",
     "states a segmentation effect without labeling it a conditional model "
     "output"),
    (r"catastroph",
     "uses catastrophe language for a threshold that has had no clinical "
     "validation"),
    (r"clinical\s+catastrophe\s+threshold",
     "calls a mathematically chosen threshold a clinical threshold"),
    (r"(best|optimal|recommended)\s+portfolio\s+for\s+hospitals",
     "presents a portfolio as a procurement recommendation"),
    (r"backup\s+isolation\s+eliminates",
     "claims backup isolation eliminates compromise"),
    (r"(72|seventy-two)[- ]hours?\s+(endpoint\s+)?represents\s+full\s+recovery",
     "equates the 72-hour endpoint with full recovery"),
    (r"true\s+prevalence\s+of\s+(hospital\s+)?ransomware\s+entry",
     "treats the entry distribution as a true prevalence"),
    (r"proven\s+robust",
     "claims robustness was proven rather than tested within a prespecified "
     "range"),
    (r"\bempirically\s+estimated\b",
     "describes an evidence-constrained scenario range as an empirical "
     "estimate"),
]

#: Framing the manuscript must contain. Absence is a failure, because these
#: are what keep the reported quantities interpretable.
REQUIRED_DISCLOSURES: list[tuple[str, str]] = [
    (r"synthetic", "must describe the model as synthetic"),
    (r"partially\s+calibrated",
     "must use the 'partially calibrated' framing the evidence supports"),
    (r"normalized\s+(scenario\s+)?points?",
     "must state that cost and burden are normalized points, not dollars"),
    (r"non-?identifiab",
     "must state the non-identifiability of technical control effects"),
    (r"sustained", "must name the sustained-outage endpoint"),
    (r"\bk\s*=\s*4\b", "must state the primary k explicitly"),
]

#: Environments whose numerals are typography or structure, not results.
IGNORED_ENVIRONMENTS = (
    r"\\documentclass.*", r"\\usepackage.*", r"\\geometry.*",
    r"\\setlength.*", r"\\setcounter.*", r"\\definecolor.*",
    r"\\fontsize.*", r"\\includegraphics.*", r"\\hypersetup.*",
    r"\\captionsetup.*", r"\\renewcommand.*", r"\\newcommand.*",
    r"\\setlist.*", r"\\vspace.*", r"\\hspace.*", r"\\bibliographystyle.*",
    r"\\label.*", r"\\ref.*", r"\\cite.*", r"\\url.*", r"\\textsuperscript.*",
    r"\\begin\{.*", r"\\end\{.*", r"%.*",
)

#: Numerals that are legitimately literal in prose: years, section numbers,
#: and the model's own declared structural constants, which are generated
#: elsewhere or are definitional.
ALLOWED_LITERALS = re.compile(
    r"^(19|20)\d{2}$"        # years
    r"|^[0-9]$"              # single digits: counts of sections, services
    r"|^\d{1,2}(pt|in|em|ex|cm|mm)$"
)

#: Contexts in which a numeral is part of a name or a definition rather than
#: a measured value: an ordinal ("90th percentile"), a named algorithm or
#: standard ("SHA-256", "CVaR90"), or a horizon named in prospective prose
#: about work not yet done. These are matched against the surrounding text.
DEFINITIONAL_CONTEXT = re.compile(
    r"\d+(st|nd|rd|th)\b"                    # ordinals
    r"|SHA-\d+|CVaR\d+|MD\d|AES-\d+"        # named algorithms
    r"|\bIR\s*\d+", re.IGNORECASE)


def strip_ignorable(text: str) -> list[tuple[int, str]]:
    """Return (line number, content) for lines that can carry a claim."""
    patterns = [re.compile(p) for p in IGNORED_ENVIRONMENTS]
    kept: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if any(p.match(stripped) for p in patterns):
            continue
        kept.append((number, line))
    return kept


def sentences_with_citations(text: str) -> list[tuple[int, str]]:
    """Line numbers whose surrounding sentence carries a citation.

    A numeral attributed to a source is a *cited literature value*, not a
    result of this study, and it is legitimately literal — the manuscript
    cannot generate 374 attacks from its own tables. Such numerals are still
    reported, as an advisory to verify them against the source, but they do
    not fail the audit. A numeral with no citation anywhere near it is a
    result value and must come from a macro.
    """
    lines = text.splitlines()
    cited: set[int] = set()
    for index, line in enumerate(lines):
        # \\auditref marks a number sourced from this project's own forensic
        # audit of its predecessor rather than from a results table — the
        # 70 tests that passed, the 57 finalists that were evaluated. Those
        # are facts about a superseded artifact and cannot be regenerated,
        # so they are attributed instead.
        if "\\cite" not in line and "\\auditref" not in line:
            continue
        # A LaTeX sentence routinely wraps across lines, and the citation may
        # sit either before or after the numeral it attributes.
        for offset in range(max(0, index - 5), min(len(lines), index + 6)):
            cited.add(offset + 1)
    return sorted((number, lines[number - 1]) for number in cited)


def check_hand_typed_numbers(text: str) -> tuple[list[str], list[str]]:
    """Returns (failures, advisories)."""
    problems: list[str] = []
    advisories: list[str] = []
    cited_lines = {number for number, _ in sentences_with_citations(text)}
    numeral = re.compile(r"(?<![\\A-Za-z0-9.])(\d[\d,]*\.?\d*)\s*(\\%|%)?")
    for number, line in strip_ignorable(text):
        # Remove macro invocations before looking for bare numerals.
        cleaned = re.sub(
            r"\\(fontsize|vspace|hspace|includegraphics|setlength|"
            r"setcounter|selectfont|columnsep|headheight)"
            r"(\[[^\]]*\])?(\{[^}]*\})*", " ", line)
        cleaned = re.sub(r"\\[A-Za-z]+", " ", cleaned)
        for match in numeral.finditer(cleaned):
            token = match.group(1)
            if ALLOWED_LITERALS.match(token):
                continue
            if DEFINITIONAL_CONTEXT.search(line):
                continue
            if number in cited_lines:
                advisories.append(
                    f"line {number}: cited literature value {token!r} — "
                    "verify against the source; not generated")
                continue
            problems.append(
                f"line {number}: hand-typed number {token!r} — a result value "
                f"must come from a generated macro\n      {line.strip()}")
    return problems, advisories


def check_macros(text: str, generated: str) -> list[str]:
    defined = set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", generated))
    used = set(re.findall(r"\\([A-Z][A-Za-z]*)\b", text)) & (
        defined | {name for name in defined})
    # Any capitalised macro the manuscript uses that looks generated.
    referenced = {name for name in re.findall(r"\\([A-Z][A-Za-z]{3,})\b", text)}
    problems: list[str] = []
    likely_generated = {n for n in referenced
                        if n.startswith(("Num", "Discovery", "Confirm",
                                         "Bimodal", "Precision", "Protocol",
                                         "Enumerated", "Primary", "Outage",
                                         "Horizon", "Step"))}
    for name in sorted(likely_generated - defined):
        problems.append(
            f"manuscript uses \\{name} but generated_numbers.tex does not "
            "define it; re-run generate_manuscript_numbers.py")
    for name in sorted(defined - used):
        problems.append(
            f"generated macro \\{name} is never used; a claim was probably "
            "removed without removing its analysis, or vice versa")
    return problems


def check_endpoint_definitions(text: str) -> list[str]:
    """The manuscript must state the registry's definitions, not its own."""
    problems: list[str] = []
    normalized = re.sub(r"\s+", " ", text)
    for spec in ENDPOINTS.values():
        if spec.direction is None:
            continue
        # Match on a distinctive clause rather than the whole sentence, so
        # LaTeX line wrapping and markup do not cause false failures.
        anchor = re.sub(r"\s+", " ", spec.definition).split(",")[0]
        anchor = re.sub(r"\([^)]*\)", "", anchor).strip()
        words = [w for w in re.findall(r"[a-z]{5,}", anchor.lower())][:4]
        if not words:
            continue
        if not all(w in normalized.lower() for w in words):
            problems.append(
                f"endpoint '{spec.id}': the manuscript does not state the "
                f"registry definition (looked for {words})")
    return problems


def check_patterns(text: str, patterns: list[tuple[str, str]],
                   *, must_be_absent: bool) -> list[str]:
    problems: list[str] = []
    for pattern, message in patterns:
        found = re.search(pattern, text, flags=re.IGNORECASE)
        if must_be_absent and found:
            problems.append(
                f"red line: {message}\n      matched {found.group(0)!r}")
        if not must_be_absent and not found:
            problems.append(f"missing disclosure: {message}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manuscript", default=str(MANUSCRIPT))
    parser.add_argument("--generated", default=str(GENERATED))
    parser.add_argument("--skip-numbers", action="store_true",
                        help="skip the hand-typed-number check")
    args = parser.parse_args()

    text = Path(args.manuscript).read_text(encoding="utf-8")
    generated_path = Path(args.generated)
    generated = (generated_path.read_text(encoding="utf-8")
                 if generated_path.exists() else "")

    sections: list[tuple[str, list[str]]] = [
        ("red-line claims", check_patterns(text, RED_LINES,
                                           must_be_absent=True)),
        ("required disclosures", check_patterns(text, REQUIRED_DISCLOSURES,
                                                must_be_absent=False)),
        ("endpoint definitions", check_endpoint_definitions(text)),
    ]
    if generated:
        sections.append(("macro coverage", check_macros(text, generated)))
    else:
        sections.append(("macro coverage", [
            f"{generated_path} does not exist; run "
            "generate_manuscript_numbers.py first"]))
    advisories: list[str] = []
    if not args.skip_numbers:
        failures, advisories = check_hand_typed_numbers(text)
        sections.append(("hand-typed result numbers", failures))

    total = 0
    for name, problems in sections:
        status = "PASS" if not problems else f"FAIL ({len(problems)})"
        print(f"{status:12s} {name}")
        for problem in problems:
            print(f"      {problem}")
        total += len(problems)

    if advisories:
        print(f"\nADVISORY     {len(advisories)} cited literature values "
              "appear as literals; each must be verified against its source")
        for advisory in advisories[:20]:
            print(f"      {advisory}")

    print()
    if total:
        print(f"CLAIM AUDIT FAILED: {total} problems", file=sys.stderr)
        return 1
    print("claim audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

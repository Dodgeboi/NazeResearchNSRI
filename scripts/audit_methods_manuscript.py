#!/usr/bin/env python3
"""Scope-limited checks for the current methods paper, with legacy regression.

Checks generated data, registered assertions, citation resolution and required
scope disclosures. Does not certify arbitrary prose or enforce a ban on all
literal numbers. The preserved baseline auditor remains available separately.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from generate_interpretation_paper import content
from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'docs/manuscript'


def main():
    generated, _ = content()
    for name,value in generated.items():
        if (PAPER/name).read_text(encoding='utf-8') != value:
            raise AssertionError('stale paper data: ' + name)
    verify_manifest(PAPER/'methods_manifest.json')
    text = '\n'.join(p.read_text(encoding='utf-8') for p in [PAPER/'main.tex', *PAPER.glob('section_*.tex')])
    registry = json.loads((ROOT/'study/interpretation_contracts.json').read_text())
    anchors = re.findall(r'% claim: (\w+)', text)
    if sorted(anchors) != sorted(c['id'] for c in registry['current']):
        raise AssertionError('registered claims must each have one manuscript anchor')
    for phrase in ('retrospective', 'synthetic', 'non-identifiable', 'normalized scenario points',
                   'LLM Usage Statement', 'within each entry category'):
        if phrase not in re.sub(r'\s+', ' ', text):
            raise AssertionError('missing scope disclosure: ' + phrase)
    keys = {key.strip() for group in re.findall(r'\\cite\{([^}]+)\}',text) for key in group.split(',')}
    bib = (PAPER/'references.bib').read_text(encoding='utf-8')
    available = set(re.findall(r'@\w+\{([^,]+),',bib))
    if keys - available:
        raise AssertionError('unresolved citations: ' + str(keys - available))
    old = subprocess.run([sys.executable,'audit/baseline_claim_audit.py','--manuscript',
        'audit/baseline_manuscript/main.tex','--generated','audit/baseline_manuscript/generated_numbers.tex'],
        cwd=ROOT,capture_output=True,text=True)
    if old.returncode:
        raise AssertionError('preserved baseline audit no longer reproduces its pass')
    print(f'current manuscript checks passed; {len(keys)} citations resolve; baseline audit pass reproduced')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

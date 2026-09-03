# Reproducibility

Everything in this repository is meant to be checkable by someone who does
not trust us. The design rule throughout is **fail loudly**: reproduction
stops with an error when an input has changed, rather than continuing and
producing numbers that no longer describe the recorded run.

## Environment

**Python 3.12 or newer is required.** `numpy==2.5.1` needs it, and the
package metadata enforces it. On an older interpreter the install fails with
a dependency-resolution error that does not name the real cause, so check
your version first.

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Exact pins are in `requirements.txt`. Every run manifest records the
interpreter, platform, and the versions of the packages that can move a
number (numpy, pandas, scipy, networkx, matplotlib, pyyaml), together with
the git commit and whether the working tree was dirty.

## Verify before you trust

Three checks, in order. Each exits non-zero on failure.

```bash
pytest                                   # 165 tests, 1 expected xfail
python scripts/verify_sources.py         # archived sources + derived counts
python -m grrc.cli validate --no-report  # behavioral validation checks
```

The expected xfail is deliberate: it asserts that an "isolated" backup can
still fail, which the current model does not allow. The defect is tracked as
ISSUE-006 and the failing test keeps it visible in every run rather than only
in a document. If it ever passes unexpectedly, the model changed.

`verify_sources.py` recomputes each archived source's SHA-256 and byte size
**and** re-derives every count the registry records. That second part catches
the subtler failure of intact bytes under drifted analysis code.

## Reproduce the study

Roughly 2.5 hours of the pipeline is simulation; the rest is seconds. Every
stage writes a manifest hashing its inputs and outputs.

```bash
# 1. Discovery — exploratory. 12,000 executions, ~15 min on 2 cores.
python scripts/run_discovery.py
python scripts/analyze_portfolio_stage.py --stage discovery
python scripts/analyze_discovery_precision.py

# 2. Freeze the confirmatory protocol. Commit it BEFORE step 3.
python scripts/freeze_confirmatory_protocol.py --name my_confirmatory_v1

# 3. Confirmation — 137,600 executions, ~4 h on 2 cores.
python scripts/run_confirmatory_frontier.py --protocol my_confirmatory_v1
python scripts/analyze_portfolio_stage.py --stage confirmation \
    --protocol my_confirmatory_v1

# 4. External validation against the frozen benchmark registry.
python scripts/run_external_validation.py

# 5. Manuscript numbers, then the claim audit, then the PDF.
python scripts/generate_manuscript_numbers.py
python scripts/audit_manuscript_claims.py
cd docs/manuscript && latexmk -pdf main.tex
```

Building the PDF needs more than a minimal TeX install. On a Debian or
Ubuntu machine:

```bash
apt-get install texlive-latex-extra texlive-fonts-extra texlive-plain-generic
```

`newpxtext` lives in `texlive-fonts-extra` and `binhex.tex`, which `newpx`
pulls in, lives in `texlive-plain-generic`. Without them the build stops with
a "file not found" error that does not name the package.

A smoke run that exercises the whole pipeline in a few minutes:

```bash
python scripts/run_discovery.py --trials 3 \
    --output /tmp/smoke/discovery_results.csv
```

Committed raw and processed outputs mean every reported value can be audited
without rerunning anything.

## What makes the freeze checkable

The previous version of this study wrote its "frozen" holdout protocol from
inside its own runner, on every invocation, with no hash, commit, or
timestamp. Nothing distinguished a genuine prospective freeze from a file
written afterwards.

Now a protocol is a content-addressed artifact in `study/protocols/`:

- its own SHA-256 is computed over its canonical form and stored inside it;
- `freeze_protocol` **refuses to overwrite** an existing protocol;
- loading recomputes the digest and **raises** if the file has been edited;
- the runner will not start without a protocol that verifies, refuses to run
  if the resolved candidate space has changed since freezing, and stamps the
  digest into every raw row and into the run manifest;
- the protocol is committed to git before any confirmatory output exists, so
  the ordering is visible in the public history.

The pre-rebuild freeze **cannot** be established from the public record, and
nothing in the current work claims it can. That analysis is retrospective.

## Randomness and pairing

Every candidate within a profile replays one scenario bank: the same
topology, entry point, patch draws, and counter-style event-level random
fields keyed to stable scenario, event-type, time-step, and node or edge
positions. A portfolio cannot receive different randomness merely because its
control path changed execution order. Confirmatory scenario identifiers are
allocated in per-profile blocks that cannot collide with discovery.

Identical seeds and configs reproduce identical raw results; a test asserts
it.

## Scenario counts are justified, not declared

`analyze_discovery_precision.py` estimates, per profile and objective, the
per-scenario standard deviation and the paired requirement needed to resolve
one tenth of the interquartile range of candidate means. The requirement
varies by more than a factor of four across profiles, so scenarios are
allocated per profile rather than uniformly. The full report is embedded in
the frozen protocol. Where a count still falls below a requirement, the
affected objective is reported as under-resolved.

## Manifests and hashes

Every run and analysis writes a manifest recording, for each consumed input
and produced output, its POSIX repo-relative path, byte size, and SHA-256,
plus the code commit, dirty-tree state, environment, and a UTC timestamp.

```python
from grrc.provenance import verify_manifest
verify_manifest("data/multiobjective/confirmatory/confirmatory_run_manifest.json")
```

This raises on any mismatch. Paths are always POSIX; the superseded holdout
manifest recorded Windows separators that the declared CI runner could not
resolve.

## The manuscript contains no hand-typed result

`generate_manuscript_numbers.py` writes one LaTeX macro per reported
quantity, sourced from the committed result tables.
`audit_manuscript_claims.py` checks the other direction and exits non-zero
on: bare numerals in claim-bearing lines, undefined or orphan macros,
endpoint definitions that disagree with `grrc.endpoints`, any of the
handoff's red-line claims (matched as patterns, so paraphrases are caught),
and missing required framing.

If a run is repeated and a value moves, the manuscript moves with it. A value
that ceases to exist becomes a LaTeX compile error rather than a stale
sentence.

## Data handling

`data/observed/raw/source_manifest.json` records version, retrieval date,
license, reuse terms, mutability class, size, SHA-256, and — the part that
matters for restraint — an explicit `does_not_support` list per source.

CISA's catalog is a **mutable web feed**: its origin URL will not reproduce
the archived file, so only the snapshot and its catalog version are citable.
The THREAT file is a normalized export of the public openICPSR preview
because the original requires sign-in; replacing it with the depositor's
original is a pre-submission task, not an invisible overwrite, and the
recorded hash makes any substitution detectable.

**No restricted Medicare claims data are included in this repository.** The
only hospital-linked file is a public replication deposit.
`docs/evidence/THREAT_RECONCILIATION.md` reconciles its counts with the
published article's.

## What reproducibility does not buy you

Confidence intervals here describe Monte Carlo uncertainty **conditional on
the model**. They do not include uncertainty from missing mechanisms,
incorrect assumptions, or transfer to real hospitals. A perfectly
reproducible pipeline can reproduce a wrong answer exactly. The external
validation results in `data/multiobjective/confirmatory/external_validation.json`
are the check on that, and most of them do not pass.

## Superseded results

`data/multiobjective/archive_pre_rebuild/` holds the pre-rebuild raw and
processed data. It is retained rather than deleted, and no number in it may
be cited; its README explains why. `study/DEVIATIONS.md` records every change
and, where an argument was withdrawn, what it was.

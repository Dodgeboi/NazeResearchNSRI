#!/usr/bin/env bash
# Set up the CAGE Challenge 2 environment (CybORG) and the challenge-winning defender
# in a separate virtual environment, at pinned commits, with hash-checked weights.
#
#   bash scripts/setup_cage.sh          # creates .venv-cage and vendor/cage
#
# Sources (both MIT licensed):
#   https://github.com/cage-challenge/cage-challenge-2   (CybORG, Scenario 2)
#   https://github.com/john-cardiff/-cyborg-cage-2        (winning PPO agent + weights)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor/cage"
CAGE2_COMMIT=26ce1c1253fa9e2e73f25e6a7f2da32860c11257
CARDIFF_COMMIT=ddbf3e55d17484b1bdd62b02daff72b7774330df
BLINE_SHA=2600259b0376c1ff701db2eed311309cd7131a1691f5dd739129ffcf0d83b0e6
MEANDER_SHA=6b0cc55065165ebff46bd514c10fc15d416b9984338f2131c6df03a47c3a4315

fetch() {  # repo dir commit
  if [ ! -d "$VENDOR/$2/.git" ]; then
    git clone -q "https://github.com/$1.git" "$VENDOR/$2"
  fi
  git -C "$VENDOR/$2" fetch -q --depth 1 origin "$3" 2>/dev/null || true
  git -C "$VENDOR/$2" checkout -q "$3"
}
mkdir -p "$VENDOR"
fetch cage-challenge/cage-challenge-2 cage-challenge-2 "$CAGE2_COMMIT"
fetch john-cardiff/-cyborg-cage-2 cardiff "$CARDIFF_COMMIT"
echo "$BLINE_SHA  $VENDOR/cardiff/Models/bline/model.pth" | sha256sum -c -
echo "$MEANDER_SHA  $VENDOR/cardiff/Models/meander/model.pth" | sha256sum -c -

PY="${PYTHON:-python3.12}"
if [ ! -d "$ROOT/.venv-cage" ]; then "$PY" -m venv "$ROOT/.venv-cage"; fi
"$ROOT/.venv-cage/bin/pip" install -q -r "$ROOT/requirements-cage.txt"
"$ROOT/.venv-cage/bin/pip" install -q -e "$VENDOR/cage-challenge-2/CybORG" --no-deps
"$ROOT/.venv-cage/bin/pip" install -q -e "$ROOT" --no-deps
echo "CAGE environment ready: $ROOT/.venv-cage"

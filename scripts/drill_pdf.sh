#!/usr/bin/env bash
# Drill a PDF into TiddlyWiki tiddlers with pdfdrill, then compile them into a
# codedrill graph. Run this YOURSELF — codedrill never calls paid APIs on your behalf.
#
#   ./scripts/drill_pdf.sh <file.pdf|arxiv-id|url> [bibkey]
#
# pdfdrill location: defaults to ~/MX/PDFDRILL (override with PDFDRILL_DIR=...).
# For an arXiv id/URL, pdfdrill's FREE abstract+latex routes are used and MathPix is
# skipped by default; for a scanned/local PDF it auto-chains `model`→`mathpix` (paid)
# and needs a .env with your ROTATED keys (MATHPIX_APP_ID / MATHPIX_APP_KEY).
set -euo pipefail

PDF="${1:?usage: drill_pdf.sh <file.pdf|arxiv-id|url> [bibkey]}"
BIBKEY="${2:-}"
PDFDRILL="${PDFDRILL_DIR:-$HOME/MX/PDFDRILL}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

[ -d "$PDFDRILL/src" ] || { echo "pdfdrill not found at $PDFDRILL (set PDFDRILL_DIR)"; exit 1; }

# Load this repo's git-ignored .env (your rotated keys) into the environment.
if [ -f "$HERE/.env" ]; then set -a; . "$HERE/.env"; set +a; fi

run_pdfdrill() { PYTHONPATH="$PDFDRILL/src" python3 -m pdfdrill "$@"; }

echo ">> drilling $PDF into tiddlers with pdfdrill ($PDFDRILL) ..."
run_pdfdrill tiddlers "$PDF" ${BIBKEY:+--bibkey "$BIBKEY"}

# Locate the emitted tiddlers JSON (lives in <pdf>.drill/<bibkey>.tiddlers.json).
TW_JSON="$(run_pdfdrill artifacts "$PDF" 2>/dev/null \
            | grep -oE '[^ ]+\.tiddlers\.json' | head -n1 || true)"
if [ -z "${TW_JSON:-}" ] || [ ! -f "$TW_JSON" ]; then
  echo "could not locate the tiddlers JSON from 'pdfdrill artifacts $PDF'"; exit 1
fi

OUT="$HERE/drills/${BIBKEY:-out}"
mkdir -p "$OUT"
cp "$TW_JSON" "$OUT/source-tiddlers.json"   # keep the input in the durable store
echo ">> compiling tiddlers: $TW_JSON -> $OUT"
PYTHONPATH="$HERE/src:$PDFDRILL/src" python3 -m codedrill compile "$TW_JSON" -o "$OUT" --pdfdrill
echo ">> done. graph + knowledge-graph.json in $OUT"

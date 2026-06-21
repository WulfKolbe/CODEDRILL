#!/usr/bin/env bash
# Drill a PDF with pdfdrill (MathPix OCR) into ./drills/, then compile its code+paragraph
# tiddlers into a codedrill graph. Requires a sibling pdfdrill checkout and a .env with
# ROTATED keys. Run this YOURSELF — codedrill never calls paid APIs on your behalf.
set -euo pipefail
PDF="${1:?usage: drill_pdf.sh <file.pdf|arxiv-id|url> [bibkey]}"
BIBKEY="${2:-}"
PDFDRILL="${PDFDRILL_DIR:-../pdfdrill}"
mkdir -p pdfs drills
export PDFDRILL_ENV="$(pwd)/.env"
echo ">> drilling $PDF with pdfdrill ..."
PYTHONPATH="$PDFDRILL/src" python3 -m pdfdrill drill "$PDF" --tiddlers ${BIBKEY:+--bibkey "$BIBKEY"}
# pdfdrill writes a tiddlers JSON into its drill folder; point codedrill at it:
TW_JSON="$(PYTHONPATH="$PDFDRILL/src" python3 -m pdfdrill artifacts "$PDF" --json | python3 -c 'import sys,json;print(next(p for p in json.load(sys.stdin) if p.endswith(".json") and "tiddler" in p.lower()))')"
echo ">> compiling tiddlers: $TW_JSON"
PYTHONPATH="src:$PDFDRILL/src" python3 -m codedrill compile "$TW_JSON" -o "drills/${BIBKEY:-out}" --pdfdrill

#!/usr/bin/env bash
# Create the CODEDRILL repo under your GitHub account and push this scaffold.
# Run YOURSELF (needs your GitHub auth). codedrill cannot create repos on your behalf.
set -euo pipefail
REPO="${1:-CODEDRILL}"
git init -q
git add .
git commit -qm "codedrill: semantic compiler for TiddlyWiki code/paragraph tiddlers (bootstrap)"
git branch -M main
# Option A — GitHub CLI:
if command -v gh >/dev/null; then
  gh repo create "WulfKolbe/$REPO" --private --source=. --remote=origin --push
else
  # Option B — manual: create the empty repo on github.com first, then:
  git remote add origin "git@github.com:WulfKolbe/$REPO.git"
  git push -u origin main
fi
echo "Pushed to WulfKolbe/$REPO. Verify .env is NOT in the tree:  git ls-files | grep -c '^\.env$'  -> must be 0"

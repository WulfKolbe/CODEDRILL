#!/usr/bin/env bash
# Resume the Claude Code session that built CODEDRILL, with full context intact.
# The session id below is this project's drilling session — the "branch off a chat"
# anchor described in the README. Re-run any time to pick the work back up.
set -euo pipefail

SESSION_ID="e33b45ac-7e06-4c8e-ad45-905626b1ac8a"

cd "$(dirname "$0")"
exec claude --resume "$SESSION_ID" "$@"

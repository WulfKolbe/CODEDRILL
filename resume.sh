#!/usr/bin/env bash
# Resume the most recent Claude Code session for CODEDRILL.
# NOTE: the original build session (e33b45ac-7e06-4c8e-ad45-905626b1ac8a, 2026-06-21)
# is recorded in ~/.claude/history.jsonl but its transcript no longer exists on disk,
# so it cannot be resumed. This id is the current live session for this folder.
set -euo pipefail

SESSION_ID="cef64f5f-fe02-4fd6-83e4-c6caa3249a7a"

cd "$(dirname "$0")"
exec claude --resume "$SESSION_ID" --dangerously-skip-permissions "$@"

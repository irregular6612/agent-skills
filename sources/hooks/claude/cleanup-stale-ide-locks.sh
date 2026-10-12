#!/bin/bash
# Cleans up stale Claude Code IDE lock files whose owning PID is no longer alive.
# Triggered on SessionStart so subsequent IDE handshake attempts succeed.
set -u
LOCK_DIR="$HOME/.claude/ide"
[ -d "$LOCK_DIR" ] || exit 0

shopt -s nullglob
for lock in "$LOCK_DIR"/*.lock; do
  pid="$(basename "$lock" .lock)"
  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
    continue
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$lock"
  fi
done
exit 0

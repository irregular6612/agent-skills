#!/usr/bin/env bash
# PostToolUse hook: run the vault's single paper-note checker on saved general-v2 notes.
# The checker lives with the notes (Public/_tools/paper_note.py) and is stdlib-only.
VAULT="${PAPER_VAULT_ROOT:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes}"
CHECKER="$VAULT/Public/_tools/paper_note.py"
[ -f "$CHECKER" ] || exit 0
exec python3 "$CHECKER" hook

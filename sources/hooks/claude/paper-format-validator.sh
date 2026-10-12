#!/usr/bin/env bash
# PostToolUse hook — paper summary format validator
# Delegates to the Python implementation so the validation logic is testable
# on its own. Preserves stdin and propagates exit code.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/env python3 "$SCRIPT_DIR/paper-format-validator.py"

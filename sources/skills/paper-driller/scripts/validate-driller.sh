#!/usr/bin/env bash
# Portable canonical checks are the default. Local legacy integration is opt-in.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
case "${1:-}" in
  "") exec "${PYTHON:-python3}" "$HERE/validate_driller_static.py" ;;
  --integration)
    : "${CLAUDE_HOME:?--integration requires an explicit isolated CLAUDE_HOME}"
    : "${PAPER_VAULT_ROOT:?--integration requires an explicit PAPER_VAULT_ROOT}"
    exec bash "$HERE/validate-driller-legacy-integration.sh" ;;
  *) printf 'Usage: %s [--integration]\n' "$0" >&2; exit 2 ;;
esac

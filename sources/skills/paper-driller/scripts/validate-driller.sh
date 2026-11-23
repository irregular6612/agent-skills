#!/usr/bin/env bash
# Static check: SKILL.md and references/note-spec.md agree with the vault checker, and its tests pass.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec "${PYTHON:-python3}" "$HERE/validate_driller_static.py"

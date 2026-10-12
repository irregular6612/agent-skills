#!/usr/bin/env bash
# paper-frontmatter-hook.sh pre|post|stop — 인터프리터를 고른 뒤 Python 훅에 위임한다.
# PyYAML이 있는 인터프리터가 필요하다. 우선순위:
#   1. $PAPER_FRONTMATTER_PYTHON
#   2. ~/.claude/hooks/paper-frontmatter-venv/bin/python   (install-paper-frontmatter-hooks.py --setup-venv)
#   3. ~/.hermes/hermes-agent/venv/bin/python               (문서화된 기존 인터프리터)
#   4. python3 (PATH) — PyYAML이 없으면 Python 훅이 paper 후보에 대해 fail-closed 한다.
# 네트워크 접근 없음. stdin/exit code는 그대로 전달한다.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PAPER_FRONTMATTER_PYTHON:-}"
if [ -z "$PY" ]; then
  for c in "$DIR/paper-frontmatter-venv/bin/python" "$HOME/.hermes/hermes-agent/venv/bin/python"; do
    if [ -x "$c" ]; then PY="$c"; break; fi
  done
fi
if [ -z "$PY" ]; then PY="$(command -v python3 || true)"; fi
if [ -z "$PY" ]; then
  echo "PAPER_FRONTMATTER_HOOK_ERROR: python3 인터프리터를 찾을 수 없다 (fail-closed)" >&2
  exit 2
fi
exec "$PY" "$DIR/paper-frontmatter-hook.py" "$@"

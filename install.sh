#!/usr/bin/env bash
# agent-skills bootstrap for macOS / Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/irregular6612/agent-skills/master/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- install ditto-writer superpowers   # non-interactive
#   curl -fsSL .../install.sh | bash -s -- uninstall --all
#
# Clones (or fast-forwards) the repo into $AGENT_SKILLS_DIR (default ~/.agent-skills/repo)
# and runs install.py with the given arguments. With no arguments it opens the picker.
set -euo pipefail

REPO_URL="${AGENT_SKILLS_REPO:-https://github.com/irregular6612/agent-skills.git}"
DIR="${AGENT_SKILLS_DIR:-$HOME/.agent-skills/repo}"

die() { echo "agent-skills: $*" >&2; exit 1; }

PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PY="$cand"; break
  fi
done
[ -n "$PY" ] || die "Python 3.9+ is required (macOS: xcode-select --install, or brew install python)."
command -v git >/dev/null 2>&1 || die "git is required."

# Running from inside a checkout (./install.sh): use it as is.
SELF="${BASH_SOURCE[0]:-}"
if [ -n "$SELF" ] && [ -f "$(dirname "$SELF")/install.py" ]; then
  DIR="$(cd "$(dirname "$SELF")" && pwd -P)"
elif [ -d "$DIR/.git" ]; then
  echo "agent-skills: updating $DIR"
  git -C "$DIR" pull --ff-only --quiet || die "could not fast-forward $DIR; resolve it with git and retry."
else
  echo "agent-skills: cloning $REPO_URL -> $DIR"
  mkdir -p "$(dirname "$DIR")"
  git clone --quiet --depth 1 "$REPO_URL" "$DIR"
fi

exec "$PY" "$DIR/install.py" "$@"

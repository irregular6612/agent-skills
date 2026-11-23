#!/bin/bash
# lab_claude.sh - run ONE task on the lab Claude Code account (headless `claude -p`) and save the result.
#
#   lab_claude.sh [--name SLUG] [--dir DIR] [--allow-bash] [--timeout MIN] "task prompt"
#   echo "task prompt" | lab_claude.sh [options] -
#
# Writes <runs>/<YYYYmmdd-HHMMSS>-<slug>/{prompt.md,result.md,meta.json,stderr.log} and prints
# RUN_DIR=, RESULT=, STATUS= lines. The OAuth token is read from the macOS keychain and never printed.
#   LAB_CLAUDE_KEYCHAIN_SERVICE  keychain service holding the lab token (default claude-token-juhyeon)
#   LAB_CLAUDE_RUNS              where runs are kept (default ~/Workspace/lab-claude-runs)
#   LAB_CLAUDE_MODEL             optional model alias passed to --model
set -u
SERVICE="${LAB_CLAUDE_KEYCHAIN_SERVICE:-claude-token-juhyeon}"
RUNS="${LAB_CLAUDE_RUNS:-$HOME/Workspace/lab-claude-runs}"
NAME="task"; WORKDIR=""; ALLOW_BASH=0; TIMEOUT_MIN=30; PROMPT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --dir) WORKDIR="$2"; shift 2 ;;
    --allow-bash) ALLOW_BASH=1; shift ;;
    --timeout) TIMEOUT_MIN="$2"; shift 2 ;;
    -) PROMPT="$(cat)"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) PROMPT="$1"; shift ;;
  esac
done
[ -n "$PROMPT" ] || { echo "STATUS=error: empty prompt" >&2; exit 2; }
CLAUDE="$(command -v claude || echo "$HOME/.local/bin/claude")"
TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || echo /opt/homebrew/bin/timeout)"
SLUG="$(printf '%s' "$NAME" | tr -cs 'A-Za-z0-9' '-' | sed 's/^-//;s/-$//' | cut -c1-40)"
RUN_DIR="$RUNS/$(date +%Y%m%d-%H%M%S)-${SLUG:-task}"
mkdir -p "$RUN_DIR" || exit 2
printf '%s\n' "$PROMPT" > "$RUN_DIR/prompt.md"

TOKEN="$(security find-generic-password -s "$SERVICE" -w 2>/dev/null)" || {
  echo "STATUS=error: keychain item '$SERVICE' not readable (lab Claude token)" >&2; exit 3; }

TOOLS="Read,Write,Edit,Glob,Grep,WebFetch,WebSearch"
[ "$ALLOW_BASH" = 1 ] && TOOLS="$TOOLS,Bash"
CWD="${WORKDIR:-$RUN_DIR}"
ARGS=(-p --output-format json --permission-mode acceptEdits --allowedTools "$TOOLS" --add-dir "$RUN_DIR"
      --append-system-prompt "This is a delegated, unattended task. Do not ask questions. Write any files you create under $RUN_DIR unless the task names another path. End with a concise answer in Korean.")
[ -n "${LAB_CLAUDE_MODEL:-}" ] && ARGS+=(--model "$LAB_CLAUDE_MODEL")

( cd "$CWD" && CLAUDE_CODE_OAUTH_TOKEN="$TOKEN" "$TIMEOUT_BIN" "$((TIMEOUT_MIN * 60))" \
    "$CLAUDE" "${ARGS[@]}" < "$RUN_DIR/prompt.md" > "$RUN_DIR/raw.json" 2> "$RUN_DIR/stderr.log" )
RC=$?
unset TOKEN

python3 - "$RUN_DIR" "$RC" <<'PY'
import json, sys, pathlib
d, rc = pathlib.Path(sys.argv[1]), int(sys.argv[2])
raw = (d / "raw.json").read_text(encoding="utf-8", errors="ignore").strip()
try:
    j = json.loads(raw.splitlines()[-1]) if raw else {}
except Exception:
    j = {}
result = j.get("result") or ""
(d / "result.md").write_text(result + "\n", encoding="utf-8")
meta = {k: j.get(k) for k in ("subtype", "is_error", "num_turns", "duration_ms", "total_cost_usd", "session_id")}
meta["exit_code"] = rc
(d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
ok = rc == 0 and not j.get("is_error") and result
status = "ok" if ok else ("timeout" if rc == 124 else "error")
print(f"RUN_DIR={d}\nRESULT={d / 'result.md'}\nSTATUS={status}")
if not ok:
    err = (d / "stderr.log").read_text(encoding="utf-8", errors="ignore").strip().splitlines()
    print("ERROR=" + (err[-1][:300] if err else (j.get("subtype") or "no output")))
PY

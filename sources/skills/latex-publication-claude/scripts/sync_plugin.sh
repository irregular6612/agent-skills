#!/usr/bin/env bash
# sync_plugin.sh — 이 스킬을 플러그인 배포 사본으로 미러링
#
# 이 스킬은 두 곳에 산다:
#   원본(작업본)  ~/.claude/skills/latex-publication
#   배포 사본      <marketplace>/plugins/academic-writing/skills/latex-publication
#
# 두 사본은 내용이 같아야 하지만, 배포 사본에는 원본에 그대로 둘 수 없는
# 치환이 두 가지 있다. 손으로 rsync만 하면 이 둘이 지워져 플러그인이 깨진다.
# 그래서 이 스크립트를 쓴다.
#
#   1. 경로 규약
#      원본  ~/.claude/skills/latex-publication/...
#      사본  ${CLAUDE_PLUGIN_ROOT}/skills/latex-publication/...
#      플러그인은 사용자 홈이 아니라 플러그인 루트 아래에 설치되므로,
#      홈 경로를 그대로 두면 남의 머신에서 파일을 못 찾는다.
#
# 사용법:
#   sync_plugin.sh [--dest <플러그인 스킬 디렉토리>] [--dry-run]

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HOME/Documents/WorkSpace/claude-code-skill/plugins/academic-writing/skills/latex-publication"
DRY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest=*)  DEST="${1#*=}"; shift ;;
    --dest)    DEST="$2"; shift 2 ;;
    --dry-run) DRY="--dry-run"; shift ;;
    -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
    *) echo "ERROR: unknown arg: $1" >&2; exit 3 ;;
  esac
done

if [[ ! -d "$DEST" ]]; then
  echo "ERROR: 배포 사본 디렉토리가 없다: $DEST" >&2
  echo "       --dest 로 경로를 지정하라." >&2
  exit 3
fi

# 사본에만 있는 파일이 있으면 --delete 로 지워진다. 먼저 확인시킨다.
ONLY_IN_DEST="$(comm -23 \
  <(cd "$DEST" && find . -type f ! -name .DS_Store | sed 's|^\./||' | sort) \
  <(cd "$SRC"  && find . -type f ! -name .DS_Store | sed 's|^\./||' | sort))"
if [[ -n "$ONLY_IN_DEST" ]]; then
  echo "WARNING: 배포 사본에만 있는 파일 — 이 동기화로 삭제된다:" >&2
  echo "$ONLY_IN_DEST" | sed 's/^/  /' >&2
  if [[ -z "$DRY" ]]; then
    echo "       의도한 것이 아니면 지금 중단하라 (Ctrl-C). --dry-run 으로 먼저 확인 권장." >&2
  fi
fi

echo "[sync] $SRC"
echo "[sync]   → $DEST"
rsync -a --delete --exclude '.DS_Store' $DRY "$SRC/" "$DEST/"

if [[ -n "$DRY" ]]; then
  echo "[sync] dry-run 종료. 치환은 수행하지 않았다."
  exit 0
fi

# ---- 치환 1: 경로 규약 ----
python3 - "$DEST" <<'PY'
import pathlib, sys
dest = pathlib.Path(sys.argv[1])
OLD = "~/.claude/skills/latex-publication/"
NEW = "${CLAUDE_PLUGIN_ROOT}/skills/latex-publication/"
n_files = n_hits = 0
for f in dest.rglob("*"):
    if not f.is_file() or f.name in (".DS_Store", "sync_plugin.sh"):
        continue
    try:
        s = f.read_text()
    except (UnicodeDecodeError, OSError):
        continue
    if OLD in s:
        n_files += 1
        n_hits += s.count(OLD)
        f.write_text(s.replace(OLD, NEW))
print(f"[sync] 경로 규약 치환: {n_hits}건 / {n_files}개 파일")
PY

# ---- 검증 ----
FAIL=0
for f in scripts/compile.sh scripts/texlive_env.sh scripts/verify_build.sh scripts/sync_plugin.sh; do
  bash -n "$DEST/$f" || { echo "ERROR: $f 문법 오류" >&2; FAIL=1; }
done
python3 -c "import ast,sys;ast.parse(open(sys.argv[1]).read())" "$DEST/scripts/diagnose.py" \
  || { echo "ERROR: diagnose.py 문법 오류" >&2; FAIL=1; }
# 실제 파일을 가리키는 참조(뒤에 / 가 붙은 형태)만 잡는다.
# 문서가 원본 위치를 언급하는 것과 sync_plugin.sh 자신은 정상이다.
LEFTOVER="$(grep -rn "~/.claude/skills/latex-publication/" "$DEST" 2>/dev/null \
            | grep -v "/scripts/sync_plugin.sh:" || true)"
if [[ -n "$LEFTOVER" ]]; then
  echo "ERROR: 배포 사본에 홈 경로 참조가 남았다:" >&2
  echo "$LEFTOVER" | sed 's/^/  /' >&2
  FAIL=1
fi
[[ "$FAIL" -eq 0 ]] || exit 1

echo "[sync] ✓ 완료 — $(find "$DEST" -type f | wc -l | tr -d ' ') 파일"

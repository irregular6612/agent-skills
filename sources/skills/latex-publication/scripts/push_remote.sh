#!/usr/bin/env bash
# push_remote.sh — latex-publication Git/Overleaf push 스크립트
#
# 구 latex-project-manager/SKILL.md Command 2 (`push`) 로직을 1:1로 Bash화.
#
# 사용법:
#   push_remote.sh <project_dir> [remote_url] [--message="..."] [--force]
#
# 토큰 우선순위:
#   1. $GITHUB_TOKEN / $OVERLEAF_TOKEN env var
#   2. 사용자에게 직접 입력 요청 (stdin)
#
# Exit code:
#   0  성공
#   1  push 실패
#   3  인자/환경 오류

set -euo pipefail

# -------- 인자 파싱 --------
PROJECT_DIR=""
REMOTE_URL=""
COMMIT_MSG=""
FORCE_PUSH=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message=*) COMMIT_MSG="${1#*=}"; shift ;;
    --force) FORCE_PUSH=true; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    -*) echo "ERROR: unknown flag: $1" >&2; exit 3 ;;
    *)
      if [[ -z "$PROJECT_DIR" ]]; then
        PROJECT_DIR="$1"
      elif [[ -z "$REMOTE_URL" ]]; then
        REMOTE_URL="$1"
      else
        echo "ERROR: 인자 너무 많음: $1" >&2; exit 3
      fi
      shift
      ;;
  esac
done

if [[ -z "$PROJECT_DIR" ]]; then
  echo "사용법: push_remote.sh <project_dir> [remote_url] [--message=...] [--force]" >&2
  exit 3
fi

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "ERROR: 디렉토리 없음: $PROJECT_DIR" >&2
  exit 3
fi

cd "$PROJECT_DIR"

# -------- Phase 1: 초기화 --------
echo "[push_remote] Phase 1 — git 초기화"

if [[ ! -d .git ]]; then
  echo "[push_remote] git init"
  git init -q
fi

# .gitignore 확인 — 없으면 templates/gitignore 복사
if [[ ! -f .gitignore ]]; then
  SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  if [[ -f "$SKILL_ROOT/templates/gitignore" ]]; then
    cp "$SKILL_ROOT/templates/gitignore" .gitignore
    echo "[push_remote]   .gitignore 자동 생성 (templates/gitignore)"
  else
    echo "WARNING: .gitignore 없음 + templates/gitignore도 없음. 수동 생성 권장" >&2
  fi
fi

# user.name / user.email 기본값 (없으면 placeholder, push 안 됨)
if ! git config user.name >/dev/null 2>&1; then
  git config user.name "$(whoami)"
fi
if ! git config user.email >/dev/null 2>&1; then
  git config user.email "$(whoami)@$(hostname)"
fi

# -------- Phase 2: 토큰 처리 & remote 설정 --------
echo "[push_remote] Phase 2 — remote 설정"

# remote URL 결정
if [[ -z "$REMOTE_URL" ]]; then
  # 기존 origin 확인
  if git remote get-url origin >/dev/null 2>&1; then
    REMOTE_URL="$(git remote get-url origin)"
    echo "[push_remote]   기존 origin 사용: ${REMOTE_URL%@*}@..."
  else
    echo "ERROR: remote_url 인자도 없고 origin도 설정 안 됨" >&2
    exit 3
  fi
fi

# 서비스 자동 감지 + 토큰 주입
inject_token() {
  local url="$1"
  local token="$2"
  local user="${3:-}"

  if [[ "$url" =~ github.com ]]; then
    # https://github.com/user/repo.git → https://user:token@github.com/user/repo.git
    # 또는 git@github.com:user/repo.git → 그대로 (SSH는 토큰 불필요)
    if [[ "$url" =~ ^git@ ]]; then
      echo "$url"
    else
      [[ -z "$user" ]] && user="git"
      echo "${url/https:\/\//https://$user:$token@}"
    fi
  elif [[ "$url" =~ overleaf.com ]]; then
    # https://git.overleaf.com/PROJECT_ID → https://git:token@git.overleaf.com/PROJECT_ID
    echo "${url/https:\/\//https://git:$token@}"
  else
    echo "$url"
  fi
}

# 토큰 확보 (env var 우선)
if [[ "$REMOTE_URL" =~ github.com ]]; then
  TOKEN="${GITHUB_TOKEN:-}"
  USER="${GITHUB_USER:-$(whoami)}"
  SERVICE="GitHub"
elif [[ "$REMOTE_URL" =~ overleaf.com ]]; then
  TOKEN="${OVERLEAF_TOKEN:-}"
  USER=""
  SERVICE="Overleaf"
else
  TOKEN=""
  USER=""
  SERVICE="Other"
fi

if [[ "$SERVICE" != "Other" ]] && [[ -z "$TOKEN" ]] && [[ ! "$REMOTE_URL" =~ ^git@ ]]; then
  echo "[push_remote]   $SERVICE 토큰 (\$${SERVICE^^}_TOKEN env var 미설정)" >&2
  read -r -s -p "  → 토큰 입력 (입력 안 보임): " TOKEN
  echo
  if [[ -z "$TOKEN" ]]; then
    echo "ERROR: 토큰 미입력. push 불가" >&2
    exit 3
  fi
fi

AUTHED_URL="$(inject_token "$REMOTE_URL" "$TOKEN" "$USER")"

# remote 갱신 (토큰 포함 URL은 .git/config에 들어가지만 .gitignore가 .git 자체는 제외하므로 commit엔 안 들어감)
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$AUTHED_URL"
else
  git remote add origin "$AUTHED_URL"
fi

# -------- Phase 3: 커밋 --------
echo "[push_remote] Phase 3 — 커밋"

# 안전한 add: tex, bib, gitkeep, gitignore, README만 (전체 add는 위험)
SAFE_PATTERNS=(
  "*.tex"
  "*.bib"
  "*.sty"
  "*.cls"
  "**/figures/.gitkeep"
  ".gitignore"
  "README.md"
  "README"
  "build_and_compile.sh"
  "latexmkrc"
)

# 실제로 존재하는 파일만 add
ADDED_ANY=false
for pattern in "${SAFE_PATTERNS[@]}"; do
  # globbing
  if compgen -G "$pattern" > /dev/null 2>&1; then
    git add $pattern 2>/dev/null || true
    ADDED_ANY=true
  fi
done
# figures 디렉토리 (이미지 파일들)
if [[ -d figures ]] || compgen -G "*/figures" > /dev/null 2>&1; then
  git add "*/figures/" 2>/dev/null || git add figures/ 2>/dev/null || true
fi

# 토큰 / 민감 파일 잔존 확인
DANGER_PATTERNS=("\.env" "credentials" "_token" "secret")
for p in "${DANGER_PATTERNS[@]}"; do
  if git diff --cached --name-only | grep -iE "$p" >/dev/null; then
    echo "WARNING: 민감 파일 staged: $(git diff --cached --name-only | grep -iE $p)" >&2
    echo "  → 계속하려면 Enter, 중단하려면 Ctrl-C" >&2
    read -r
  fi
done

# 커밋
if ! git diff --cached --quiet; then
  if [[ -z "$COMMIT_MSG" ]]; then
    COMMIT_MSG="chore: update LaTeX project ($(date +%Y-%m-%d))"
  fi
  git commit -m "$COMMIT_MSG" -q
  echo "[push_remote]   커밋: $COMMIT_MSG"
else
  echo "[push_remote]   변경사항 없음 (커밋 skip)"
fi

# -------- Phase 4: Push --------
echo "[push_remote] Phase 4 — push"

# default branch 자동 감지
BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo main)"

PUSH_ARGS=("origin" "$BRANCH")
if [[ "$FORCE_PUSH" == "true" ]]; then
  PUSH_ARGS=("--force" "${PUSH_ARGS[@]}")
fi

# 최초 push 시 upstream 설정
if ! git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
  PUSH_ARGS=("-u" "${PUSH_ARGS[@]}")
fi

if git push "${PUSH_ARGS[@]}"; then
  echo "[push_remote]   ✓ push 성공: ${REMOTE_URL%@*} ($BRANCH)"
else
  echo "ERROR: push 실패. 토큰 권한/URL 확인" >&2
  exit 1
fi

# -------- Phase 5: Critique (검증) --------
echo "[push_remote] Phase 5 — 검증"

# tracked 파일 확인
TRACKED_COUNT=$(git ls-files | wc -l | tr -d ' ')
echo "[push_remote]   tracked 파일 $TRACKED_COUNT개"

# 토큰이 tracked content에 잔존?
if git ls-files -z | xargs -0 grep -lE 'ghp_|gho_|_TOKEN=' 2>/dev/null | head -5; then
  echo "WARNING: 위 파일에 토큰 패턴 감지. 즉시 검토 권장" >&2
fi

# .git/config의 토큰은 정상 (git push 인증용)
echo "[push_remote] ✓ 완료"

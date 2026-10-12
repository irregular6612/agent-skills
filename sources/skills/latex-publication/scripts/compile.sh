#!/usr/bin/env bash
# compile.sh — 프로젝트가 정한 엔진·TeX Live로 Overleaf와 같은 명령을 실행한다
#
# 엔진을 추측하지 않는다. 아래 순서로 해석하고, 어디에도 없으면 실패한다.
#   1. --engine= / --texlive=            이번 실행에만 적용
#   2. <프로젝트>/CLAUDE.md (없으면 AGENTS.md) 의 두 줄
#          latex-engine: pdflatex
#          latex-texlive: 2025
#      main.tex 디렉토리부터 위로 올라가며 찾는다.
#   3. 없으면 exit 4 — 사용자에게 물어야 한다는 뜻이다. 기본값으로 때우지 않는다.
#
# 해석은 scripts/texlive_env.sh 한 곳이 담당한다.
# 쓸 수 있는 조합 보기:  compile.sh --list-engines
#
# Overleaf가 실제로 실행하는 명령
# (overleaf/overleaf services/clsi/app/js/LatexRunner.js, main 브랜치):
#
#   latexmk -cd -jobname=output -auxdir=$COMPILE_DIR -outdir=$COMPILE_DIR \
#           -synctex=1 -interaction=batchmode -time -xelatex main.tex
#
# 사용법:
#   compile.sh <main.tex> [옵션]
#
# 옵션:
#   --engine=ENGINE   pdflatex | latex | xelatex | lualatex (이번 실행만)
#   --texlive=YYYY    TeX Live 연도 (이번 실행만)
#   --list-engines    이 머신에서 쓸 수 있는 조합을 출력하고 종료
#   --jobname=NAME    기본 output — Overleaf와 동일. 바꾸면 그만큼 parity가 깨진다
#   --force           latexmk -f (에러 나도 계속). Overleaf 현행은 이 플래그 없음
#   --no-bibtex       latexmk -bibtex-
#
# 환경변수:
#   TEXLIVE_BIN_DIR   추가로 훑을 TeX Live bin 디렉토리
#
# Exit code:
#   0 성공 / 1 컴파일 에러 / 2 요청한 엔진·연도 없음 / 3 인자 오류
#   4 엔진 설정이 없음 — 사용자에게 물어야 한다

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------- 인자 파싱 --------
MAIN_TEX=""
JOBNAME="output"
FORCE="no"
USE_BIBTEX="yes"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jobname=*)  JOBNAME="${1#*=}"; shift ;;
    --force)      FORCE="yes"; shift ;;
    --no-bibtex)  USE_BIBTEX="no"; shift ;;
    --engine=*)   export LATEX_ENGINE_OVERRIDE="${1#*=}"; shift ;;
    --texlive=*)  export LATEX_TEXLIVE_YEAR_OVERRIDE="${1#*=}"; shift ;;
    --list-engines)
      bash "$SCRIPT_DIR/texlive_env.sh" --list
      exit $? ;;
    --docker|--native|--image=*|--passes=*|--bibtex)
      echo "WARNING: $1 무시됨. 컨테이너 빌드 경로는 없고," >&2
      echo "         패스 횟수와 bibtex 실행 여부는 latexmk가 정한다 (Overleaf와 동일)." >&2
      shift ;;
    -h|--help)    sed -n '2,28p' "$0"; exit 0 ;;
    -*)
      echo "ERROR: unknown flag: $1" >&2
      exit 3 ;;
    *)
      if [[ -z "$MAIN_TEX" ]]; then MAIN_TEX="$1"
      else echo "ERROR: 다중 positional 인자 지원 안 함: $1" >&2; exit 3; fi
      shift ;;
  esac
done

if [[ -z "$MAIN_TEX" ]]; then
  echo "ERROR: <main.tex> 인자 필수" >&2
  echo "사용법: compile.sh <main.tex> [--engine=ENGINE] [--texlive=YYYY] [--jobname=output]" >&2
  exit 3
fi
if [[ ! -f "$MAIN_TEX" ]]; then
  echo "ERROR: 파일이 없습니다: $MAIN_TEX" >&2
  exit 3
fi

BASE_DIR="$(cd "$(dirname "$MAIN_TEX")" && pwd)"
TEX_NAME="$(basename "$MAIN_TEX")"

# -------- 엔진·배포판 해석 --------
# CLAUDE.md 탐색은 main.tex 가 있는 디렉토리에서 시작한다.
# 설정이 없으면 texlive_env.sh 가 exit 4 로 끝난다. 기본값으로 때우지 않는다.
export PROJECT_DIR="$BASE_DIR"
# shellcheck source=texlive_env.sh
source "$SCRIPT_DIR/texlive_env.sh"
echo "[compile.sh] engine=$LATEX_ENGINE  TeX Live $LATEX_TEXLIVE_YEAR  (출처: $LATEX_ENGINE_SOURCE)"
echo "[compile.sh] $TL_BIN"

# -------- magic comment가 다른 엔진을 가리키면 거부 --------
# Overleaf는 magic comment를 무시하지만, 로컬 에디터는 이걸 보고 다른 엔진을
# 띄운다. 두 경로가 갈라지는 걸 막기 위해 여기서 잡는다.
if head -n 5 "$MAIN_TEX" | grep -qiE '^%\s*!\s*TEX\s+program\s*=' ; then
  MAGIC="$(head -n 5 "$MAIN_TEX" | grep -iE '^%\s*!\s*TEX\s+program\s*=' | head -1 \
           | sed -E 's/.*=[[:space:]]*//; s/[[:space:]]*$//' | tr 'A-Z' 'a-z')"
  if [[ -n "$MAGIC" && "$MAGIC" != "$LATEX_ENGINE" ]]; then
    echo "ERROR: $MAIN_TEX 의 magic comment는 '$MAGIC' 인데 빌드 엔진은 '$LATEX_ENGINE' 이다." >&2
    echo "       엔진 출처: $LATEX_ENGINE_SOURCE" >&2
    echo "       둘 중 하나를 고쳐라. 첫 줄을 '% !TEX program = $LATEX_ENGINE' 로 바꾸거나," >&2
    echo "       프로젝트 설정의 latex-engine 을 '$MAGIC' 으로 바꾼다." >&2
    echo "       (Overleaf는 magic comment를 무시하지만 로컬 에디터는 이걸 보고 다른 엔진을 띄운다)" >&2
    exit 2
  fi
fi

# -------- Overleaf와 동일한 latexmk 인자 --------
# -cd            : main.tex 디렉토리로 이동 후 실행
# -jobname       : 산출물 basename (Overleaf는 output 고정)
# -auxdir/-outdir: Overleaf는 컴파일 디렉토리 지정. -cd 이후 cwd와 같으므로 '.'
# -synctex=1     : SyncTeX
# -interaction=batchmode : 비대화식 (Overleaf와 동일. nonstopmode 아님)
# -time          : 실행 시간 리포트
LATEXMK_ARGS=(
  -cd
  "-jobname=$JOBNAME"
  -auxdir=.
  -outdir=.
  -synctex=1
  -interaction=batchmode
  -time
  "$LATEX_ENGINE_FLAG"
)
[[ "$FORCE" == "yes" ]]     && LATEXMK_ARGS+=(-f)
[[ "$USE_BIBTEX" == "no" ]] && LATEXMK_ARGS+=(-bibtex-)
LATEXMK_ARGS+=("$TEX_NAME")

echo "[compile.sh] jobname=$JOBNAME"
echo "[compile.sh] latexmk ${LATEXMK_ARGS[*]}"

RC=0
( cd "$BASE_DIR" && PATH="$PATH" latexmk "${LATEXMK_ARGS[@]}" ) || RC=$?

LOG="$BASE_DIR/$JOBNAME.log"
PDF="$BASE_DIR/$JOBNAME.pdf"

if [[ "$RC" -ne 0 ]]; then
  echo "ERROR: latexmk 실패 (exit $RC)." >&2
  if [[ -f "$LOG" ]]; then
    echo "--- $JOBNAME.log 에러 라인 ---" >&2
    grep -nE '^(!|! LaTeX Error|! Package .* Error|! Undefined)' "$LOG" | head -20 >&2 || true
    echo "--- 마지막 30줄 ---" >&2
    tail -30 "$LOG" >&2 || true
  fi
  exit 1
fi

if [[ -f "$PDF" ]]; then
  echo "[compile.sh] ✓ 성공: $PDF"
  if [[ -f "$LOG" ]]; then
    WARN_COUNT=$(grep -cE 'LaTeX Warning:|Citation .* undefined|Reference .* undefined|Overfull \\hbox' "$LOG" 2>/dev/null || true)
    WARN_COUNT=${WARN_COUNT:-0}
    if [[ "$WARN_COUNT" -gt 0 ]]; then
      echo "[compile.sh] 경고 $WARN_COUNT건 — $JOBNAME.log 확인 권장"
    fi
  fi
else
  echo "ERROR: PDF 생성 실패 ($PDF 없음)" >&2
  exit 1
fi

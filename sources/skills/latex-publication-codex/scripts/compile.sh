#!/usr/bin/env bash
# compile.sh — latex-publication 통합 3-pass 컴파일 스크립트
#
# 사용법:
#   compile.sh <main.tex> [--engine=xelatex|pdflatex] [--passes=N] [--bibtex]
#
# Engine 자동 감지 우선순위:
#   1. --engine= 플래그
#   2. % !TEX program = magic comment
#   3. 한글/CJK 문자 자동 감지 → xelatex
#   4. 기본값: pdflatex
#
# Exit code:
#   0  성공
#   1  컴파일 에러
#   2  bibtex 에러
#   3  인자 오류

set -euo pipefail

# -------- 인자 파싱 --------
MAIN_TEX=""
ENGINE=""
PASSES=3
RUN_BIBTEX="auto"  # auto | yes | no

while [[ $# -gt 0 ]]; do
  case "$1" in
    --engine=*)
      ENGINE="${1#*=}"
      shift
      ;;
    --passes=*)
      PASSES="${1#*=}"
      shift
      ;;
    --bibtex)
      RUN_BIBTEX="yes"
      shift
      ;;
    --no-bibtex)
      RUN_BIBTEX="no"
      shift
      ;;
    -h|--help)
      sed -n '2,17p' "$0"
      exit 0
      ;;
    -*)
      echo "ERROR: unknown flag: $1" >&2
      exit 3
      ;;
    *)
      if [[ -z "$MAIN_TEX" ]]; then
        MAIN_TEX="$1"
      else
        echo "ERROR: 다중 positional 인자 지원 안 함: $1" >&2
        exit 3
      fi
      shift
      ;;
  esac
done

if [[ -z "$MAIN_TEX" ]]; then
  echo "ERROR: <main.tex> 인자 필수" >&2
  echo "사용법: compile.sh <main.tex> [--engine=xelatex|pdflatex] [--passes=N]" >&2
  exit 3
fi

if [[ ! -f "$MAIN_TEX" ]]; then
  echo "ERROR: 파일이 없습니다: $MAIN_TEX" >&2
  exit 3
fi

# -------- Engine 자동 감지 --------
if [[ -z "$ENGINE" ]]; then
  # 1. magic comment 확인 (첫 5줄)
  if head -n 5 "$MAIN_TEX" | grep -qE '^%\s*!\s*TEX\s+program\s*=\s*xelatex' ; then
    ENGINE="xelatex"
  elif head -n 5 "$MAIN_TEX" | grep -qE '^%\s*!\s*TEX\s+program\s*=\s*pdflatex' ; then
    ENGINE="pdflatex"
  # 2. 한글 자동 감지
  elif grep -q '[가-힣]' "$MAIN_TEX" 2>/dev/null; then
    ENGINE="xelatex"
    echo "[compile.sh] 한글 감지됨 → engine=xelatex 자동 선택"
  else
    ENGINE="pdflatex"
  fi
fi

# Engine validation
case "$ENGINE" in
  pdflatex|xelatex|lualatex) ;;
  *)
    echo "ERROR: 지원 안 하는 engine: $ENGINE (지원: pdflatex, xelatex, lualatex)" >&2
    exit 3
    ;;
esac

if ! command -v "$ENGINE" >/dev/null 2>&1; then
  echo "ERROR: $ENGINE 미설치. TeX Live 설치 또는 PATH 확인" >&2
  exit 3
fi

# -------- 파일명 base 추출 --------
BASE="$(basename "${MAIN_TEX%.tex}")"
DIR="$(dirname "$MAIN_TEX")"

# 작업 디렉토리로 이동 (bibtex이 cwd에서 .aux 찾음)
cd "$DIR"

echo "[compile.sh] engine=$ENGINE main=$BASE.tex passes=$PASSES bibtex=$RUN_BIBTEX"

# -------- Pass 1 --------
echo "[compile.sh] Pass 1 of $PASSES..."
"$ENGINE" -interaction=nonstopmode "$BASE.tex" > /dev/null || {
  echo "ERROR: $ENGINE Pass 1 실패. $BASE.log 마지막 30줄:" >&2
  tail -30 "$BASE.log" >&2 || true
  exit 1
}

# -------- BibTeX 실행 여부 결정 --------
SHOULD_BIBTEX="no"
if [[ "$RUN_BIBTEX" == "yes" ]]; then
  SHOULD_BIBTEX="yes"
elif [[ "$RUN_BIBTEX" == "auto" ]]; then
  # \bibliography 또는 \citep/\citet/\cite가 있고 .bib 파일이 있을 때
  if [[ -f "$BASE.aux" ]] && grep -qE '\\(bibdata|citation)' "$BASE.aux" 2>/dev/null; then
    SHOULD_BIBTEX="yes"
  fi
fi

if [[ "$SHOULD_BIBTEX" == "yes" ]]; then
  if ! command -v bibtex >/dev/null 2>&1; then
    echo "WARNING: bibtex 미설치, citation 해소 skip" >&2
  else
    echo "[compile.sh] bibtex 실행..."
    bibtex "$BASE" > /dev/null || {
      echo "WARNING: bibtex 에러 (계속 진행). $BASE.blg 마지막 20줄:" >&2
      tail -20 "$BASE.blg" >&2 || true
      # bibtex 에러는 fatal 아님 (일부 citation undefined로 계속 진행)
    }
  fi
fi

# -------- Pass 2 ~ N --------
for i in $(seq 2 "$PASSES"); do
  echo "[compile.sh] Pass $i of $PASSES..."
  "$ENGINE" -interaction=nonstopmode "$BASE.tex" > /dev/null || {
    echo "ERROR: $ENGINE Pass $i 실패. $BASE.log 마지막 30줄:" >&2
    tail -30 "$BASE.log" >&2 || true
    exit 1
  }
done

# -------- 결과 보고 --------
if [[ -f "$BASE.pdf" ]]; then
  echo "[compile.sh] ✓ 성공: $DIR/$BASE.pdf"

  # 경고 카운트
  WARN_COUNT=$(grep -cE 'LaTeX (Warning|Error):|Citation.*undefined|Overfull \\hbox' "$BASE.log" 2>/dev/null || echo 0)
  if [[ "$WARN_COUNT" -gt 0 ]]; then
    echo "[compile.sh] 경고 $WARN_COUNT건 — $BASE.log 확인 권장"
  fi
else
  echo "ERROR: PDF 생성 실패" >&2
  exit 1
fi

#!/usr/bin/env bash
# texlive_env.sh — 엔진과 TeX Live 배포판을 해석하는 단일 원천
#
# 이 스킬은 엔진을 임의로 고르지 않는다. 프로젝트가 정한 값을 따른다.
# 값이 어디에도 없으면 추측하지 않고 "물어봐야 한다"는 뜻의 exit 4로 끝난다.
#
# 해석 순서 (먼저 잡히는 것이 이긴다):
#   1. 명시 override      LATEX_ENGINE / LATEX_TEXLIVE_YEAR 환경변수
#                         (compile.sh 의 --engine= / --texlive= 가 이걸 설정한다)
#   2. 프로젝트 설정      main.tex 디렉토리부터 위로 올라가며 CLAUDE.md,
#                         그다음 AGENTS.md 에서 아래 두 줄을 찾는다:
#                             latex-engine: pdflatex
#                             latex-texlive: 2025
#   3. 없음               exit 4. 호출자(스킬)가 사용자에게 물어야 한다.
#
# 사용법:
#   source texlive_env.sh                 # PROJECT_DIR 를 미리 export 해둘 것
#   bash texlive_env.sh --list            # 이 머신에서 쓸 수 있는 엔진 전부
#   bash texlive_env.sh --print-bin       # 해석된 bin 디렉토리
#   bash texlive_env.sh --print-env       # 해석 결과 전부
#   bash texlive_env.sh --resolve-only    # 해석만 하고 결과 출력 (검증용)
#
# export 하는 것:
#   LATEX_ENGINE        pdflatex | latex | xelatex | lualatex
#   LATEX_ENGINE_FLAG   latexmk 에 넘길 플래그
#   LATEX_TEXLIVE_YEAR  4자리 연도
#   LATEX_ENGINE_SOURCE 값을 어디서 얻었는지 (override | <설정파일 경로>)
#   TL_BIN              해당 배포판의 bin 디렉토리
#
# Exit code:
#   0 성공 / 2 요청한 엔진·연도를 못 찾음 / 4 설정이 없음(사용자에게 물어야 함)

# ---- 엔진 → latexmk 플래그 (Overleaf CLSI LatexRunner.js 매핑 그대로) ----
_engine_flag() {
  case "$1" in
    pdflatex) echo "-pdf" ;;
    latex)    echo "-pdfdvi" ;;
    xelatex)  echo "-xelatex" ;;
    lualatex) echo "-lualatex" ;;
    *)        return 1 ;;
  esac
}

# ---- 이 머신에 설치된 TeX Live 배포판 전부 나열 ----
# 각 줄: <year>\t<bin_dir>\t<engine,engine,...>
_tl_scan() {
  local cand bin year ver engines e
  local -a seen=()
  for cand in "${TEXLIVE_BIN_DIR:-}" \
              "$HOME"/texlive/*/bin/*/ \
              /usr/local/texlive/*/bin/*/ \
              /Library/TeX/texbin/; do
    [[ -n "$cand" ]] || continue
    bin="${cand%/}"
    [[ -d "$bin" ]] || continue
    [[ -x "$bin/latexmk" ]] || continue
    # 심볼릭 링크로 같은 곳을 두 번 보는 것을 막는다 (/Library/TeX/texbin 등)
    local real; real="$(cd "$bin" && pwd -P)"
    local dup=0 s
    for s in "${seen[@]:-}"; do [[ "$s" == "$real" ]] && dup=1; done
    [[ "$dup" -eq 0 ]] || continue
    seen+=("$real")

    year=""
    for e in pdflatex xelatex lualatex; do
      if [[ -x "$bin/$e" ]]; then
        ver="$("$bin/$e" --version 2>/dev/null | head -1)"
        year="$(printf '%s' "$ver" | sed -nE 's/.*TeX Live ([0-9]{4}).*/\1/p')"
        [[ -n "$year" ]] && break
      fi
    done
    [[ -n "$year" ]] || continue

    engines=""
    for e in pdflatex latex xelatex lualatex; do
      [[ -x "$bin/$e" ]] && engines="${engines:+$engines,}$e"
    done
    printf '%s\t%s\t%s\n' "$year" "$bin" "$engines"
  done | sort -u
}

# ---- 프로젝트 설정 파일에서 값을 읽는다 ----
# $1: 탐색 시작 디렉토리. 위로 올라가며 CLAUDE.md → AGENTS.md 순으로 본다.
# 성공 시 "engine<TAB>year<TAB>파일경로" 출력.
_tl_read_project_config() {
  local dir="${1:-$PWD}" f engine year
  dir="$(cd "$dir" 2>/dev/null && pwd)" || return 1
  while :; do
    for f in "$dir/CLAUDE.md" "$dir/AGENTS.md"; do
      [[ -f "$f" ]] || continue
      engine="$(grep -iE '^[[:space:]]*[-*]?[[:space:]]*latex-engine[[:space:]]*:' "$f" 2>/dev/null \
                | head -1 | sed -E 's/.*:[[:space:]]*//; s/[[:space:]]*(#.*)?$//' | tr 'A-Z' 'a-z')"
      year="$(grep -iE '^[[:space:]]*[-*]?[[:space:]]*latex-texlive[[:space:]]*:' "$f" 2>/dev/null \
                | head -1 | sed -E 's/.*:[[:space:]]*//; s/[[:space:]]*(#.*)?$//')"
      if [[ -n "$engine" && -n "$year" ]]; then
        printf '%s\t%s\t%s\n' "$engine" "$year" "$f"
        return 0
      fi
      if [[ -n "$engine" || -n "$year" ]]; then
        echo "ERROR: $f 에 latex-engine 과 latex-texlive 중 하나만 있다. 둘 다 필요하다." >&2
        return 2
      fi
    done
    [[ "$dir" != "/" && "$dir" != "$HOME" ]] || break
    dir="$(dirname "$dir")"
  done
  return 1
}

# ---- 사람이 읽는 목록 ----
_tl_print_list() {
  local rows; rows="$(_tl_scan)"
  if [[ -z "$rows" ]]; then
    echo "설치된 TeX Live 없음." >&2
    return 2
  fi
  echo "이 머신에서 쓸 수 있는 조합:"
  printf '\n  %-6s  %-9s  %s\n' "연도" "엔진" "경로"
  printf '  %-6s  %-9s  %s\n' "------" "---------" "----"
  local year bin engines e
  while IFS=$'\t' read -r year bin engines; do
    [[ -n "$year" ]] || continue
    IFS=',' read -ra _es <<< "$engines"
    for e in "${_es[@]}"; do
      printf '  %-6s  %-9s  %s\n' "$year" "$e" "$bin"
    done
  done <<< "$rows"
  cat <<'HELP'

프로젝트에 고정하려면 그 프로젝트의 CLAUDE.md 에 두 줄을 넣는다:

    latex-engine: xelatex
    latex-texlive: 2025

한 번만 다르게 쓰려면:

    compile.sh main.tex --engine=pdflatex --texlive=2025
HELP
}

# ---- 목록만 요청받았으면 여기서 끝 ----
if [[ "${BASH_SOURCE[0]}" == "${0}" && "${1:-}" == "--list" ]]; then
  _tl_print_list
  exit $?
fi

# =========================== 해석 ===========================
_tl_die() {
  local code="$1"; shift
  echo "ERROR: $*" >&2
  exit "$code"
}

LATEX_ENGINE=""
LATEX_TEXLIVE_YEAR=""
LATEX_ENGINE_SOURCE=""

# 1. 명시 override
if [[ -n "${LATEX_ENGINE_OVERRIDE:-}" || -n "${LATEX_TEXLIVE_YEAR_OVERRIDE:-}" ]]; then
  LATEX_ENGINE="${LATEX_ENGINE_OVERRIDE:-}"
  LATEX_TEXLIVE_YEAR="${LATEX_TEXLIVE_YEAR_OVERRIDE:-}"
  LATEX_ENGINE_SOURCE="override"
fi

# 2. 프로젝트 설정 (빠진 값만 채운다)
if [[ -z "$LATEX_ENGINE" || -z "$LATEX_TEXLIVE_YEAR" ]]; then
  _cfg="$(_tl_read_project_config "${PROJECT_DIR:-$PWD}")" || _cfg_rc=$?
  if [[ "${_cfg_rc:-0}" -eq 2 ]]; then
    exit 3
  fi
  if [[ -n "${_cfg:-}" ]]; then
    IFS=$'\t' read -r _c_engine _c_year _c_file <<< "$_cfg"
    [[ -n "$LATEX_ENGINE" ]] || { LATEX_ENGINE="$_c_engine"; }
    [[ -n "$LATEX_TEXLIVE_YEAR" ]] || { LATEX_TEXLIVE_YEAR="$_c_year"; }
    if [[ "$LATEX_ENGINE_SOURCE" == "override" ]]; then
      LATEX_ENGINE_SOURCE="override + $_c_file"
    else
      LATEX_ENGINE_SOURCE="$_c_file"
    fi
  fi
fi

# 3. 그래도 비었으면 물어봐야 한다
if [[ -z "$LATEX_ENGINE" || -z "$LATEX_TEXLIVE_YEAR" ]]; then
  {
    echo "ERROR: 어떤 엔진과 TeX Live로 빌드할지 정해져 있지 않다."
    echo "       추측하지 않는다. 아래 중 하나로 정해야 한다."
    echo
    echo "  a) 이 프로젝트에 고정 — <프로젝트>/CLAUDE.md 에 두 줄 추가:"
    echo "         latex-engine: <엔진>"
    echo "         latex-texlive: <연도>"
    echo "  b) 이번 한 번만 — compile.sh <main.tex> --engine=<엔진> --texlive=<연도>"
    echo
    _tl_print_list
  } >&2
  exit 4
fi

LATEX_ENGINE="$(printf '%s' "$LATEX_ENGINE" | tr 'A-Z' 'a-z')"
LATEX_ENGINE_FLAG="$(_engine_flag "$LATEX_ENGINE")" \
  || _tl_die 2 "지원하지 않는 엔진: $LATEX_ENGINE (pdflatex|latex|xelatex|lualatex)"

[[ "$LATEX_TEXLIVE_YEAR" =~ ^[0-9]{4}$ ]] \
  || _tl_die 2 "TeX Live 연도가 4자리 숫자가 아니다: $LATEX_TEXLIVE_YEAR"

# ---- 요청한 연도 + 엔진을 가진 배포판 찾기 ----
# 'latex' 엔진은 latexmk 가 latex/dvipdf 경로로 부르므로 latex 바이너리를 본다.
TL_BIN=""
while IFS=$'\t' read -r _y _bin _engines; do
  [[ "$_y" == "$LATEX_TEXLIVE_YEAR" ]] || continue
  [[ -x "$_bin/$LATEX_ENGINE" ]] || continue
  TL_BIN="$_bin"
  break
done <<< "$(_tl_scan)"

if [[ -z "$TL_BIN" ]]; then
  {
    echo "ERROR: TeX Live $LATEX_TEXLIVE_YEAR 의 $LATEX_ENGINE 을 찾지 못했다."
    echo "       요청 출처: ${LATEX_ENGINE_SOURCE:-(불명)}"
    echo
    _tl_print_list
  } >&2
  exit 2
fi

# ---- 경로 이름이 아니라 엔진이 스스로 보고하는 값으로 연도 재확인 ----
_tl_ver="$("$TL_BIN/$LATEX_ENGINE" --version 2>/dev/null | head -1)"
if [[ "$_tl_ver" != *"TeX Live $LATEX_TEXLIVE_YEAR"* ]]; then
  _tl_die 2 "$TL_BIN/$LATEX_ENGINE 이 TeX Live $LATEX_TEXLIVE_YEAR 가 아니다: ${_tl_ver:-(버전 확인 실패)}"
fi
unset _tl_ver _cfg _cfg_rc _c_engine _c_year _c_file

export LATEX_ENGINE LATEX_ENGINE_FLAG LATEX_TEXLIVE_YEAR LATEX_ENGINE_SOURCE TL_BIN
PATH="$TL_BIN:$PATH"
export PATH

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  case "${1:-}" in
    --print-bin) echo "$TL_BIN" ;;
    *)
      echo "LATEX_ENGINE=$LATEX_ENGINE"
      echo "LATEX_ENGINE_FLAG=$LATEX_ENGINE_FLAG"
      echo "LATEX_TEXLIVE_YEAR=$LATEX_TEXLIVE_YEAR"
      echo "LATEX_ENGINE_SOURCE=$LATEX_ENGINE_SOURCE"
      echo "TL_BIN=$TL_BIN"
      ;;
  esac
fi

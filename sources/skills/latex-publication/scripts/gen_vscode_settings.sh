#!/usr/bin/env bash
# gen_vscode_settings.sh — 프로젝트 설정에 맞는 .vscode/settings.json 생성
#
# 에디터(LaTeX Workshop)가 compile.sh 와 다른 엔진·다른 TeX Live 로 빌드하면
# "저장하면 되는데 스크립트로는 다르다" 같은 문제가 생긴다. 그래서 recipe 를
# 손으로 쓰지 않고, texlive_env.sh 가 해석한 값으로 찍어낸다.
#
# 사용법:
#   gen_vscode_settings.sh <프로젝트_디렉토리> [--engine=E] [--texlive=Y] [--stdout]
#
# 기본 동작: <프로젝트>/.vscode/settings.json 에 쓴다. 이미 있으면 덮어쓰기 전에
# 확인을 요구한다 (--force 로 생략).
#
# Exit: 0 성공 / 2 엔진·연도 없음 / 3 인자 오류 / 4 설정 없음(사용자에게 물을 것)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJ=""; TO_STDOUT="no"; FORCE="no"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --engine=*)  export LATEX_ENGINE_OVERRIDE="${1#*=}"; shift ;;
    --texlive=*) export LATEX_TEXLIVE_YEAR_OVERRIDE="${1#*=}"; shift ;;
    --stdout)    TO_STDOUT="yes"; shift ;;
    --force)     FORCE="yes"; shift ;;
    -h|--help)   sed -n '2,17p' "$0"; exit 0 ;;
    -*)          echo "ERROR: unknown flag: $1" >&2; exit 3 ;;
    *)           [[ -z "$PROJ" ]] && PROJ="$1" || { echo "ERROR: 인자 과다: $1" >&2; exit 3; }; shift ;;
  esac
done

[[ -n "$PROJ" ]] || { echo "ERROR: <프로젝트_디렉토리> 인자 필수" >&2; exit 3; }
[[ -d "$PROJ" ]] || { echo "ERROR: 디렉토리 없음: $PROJ" >&2; exit 3; }
PROJ="$(cd "$PROJ" && pwd)"

export PROJECT_DIR="$PROJ"
# shellcheck source=texlive_env.sh
source "$SCRIPT_DIR/texlive_env.sh"

read -r -d '' JSON <<JSON_EOF || true
{
  "//": "latex-publication skill 이 생성. LOCAL-ONLY: Overleaf 에 커밋하지 말 것.",
  "//1": "gen_vscode_settings.sh 가 프로젝트 설정에서 찍어낸 파일이다. 손으로 고치지 말고",
  "//2": "CLAUDE.md 의 latex-engine / latex-texlive 를 고친 뒤 다시 생성할 것.",
  "//3": "engine=$LATEX_ENGINE  TeX Live=$LATEX_TEXLIVE_YEAR  (출처: $LATEX_ENGINE_SOURCE)",
  "//4": "명령과 인자는 Overleaf CLSI(LatexRunner.js)가 실행하는 것과 동일.",

  "latex-workshop.latex.recipe.default": "first",
  "latex-workshop.latex.recipes": [
    {
      "name": "Overleaf parity ($LATEX_ENGINE, TeX Live $LATEX_TEXLIVE_YEAR)",
      "tools": ["latexmk-overleaf"]
    }
  ],
  "latex-workshop.latex.tools": [
    {
      "name": "latexmk-overleaf",
      "command": "latexmk",
      "args": [
        "-cd",
        "-jobname=output",
        "-auxdir=.",
        "-outdir=.",
        "-synctex=1",
        "-interaction=batchmode",
        "-time",
        "$LATEX_ENGINE_FLAG",
        "%DOC%"
      ]
    }
  ],

  "//5": "이 프로젝트가 쓰는 TeX Live 의 bin 디렉토리. 비우면 에디터가 시스템",
  "//6": "기본 TeX Live(다른 연도)로 빌드해 compile.sh 와 결과가 갈린다.",
  "latex-workshop.latex.path": "$TL_BIN",

  "//7": "outDir 은 프로젝트 루트. Overleaf 는 compile dir(=프로젝트 루트)에 산출물을 둔다.",
  "latex-workshop.latex.outDir": "%DIR%",

  "latex-workshop.latex.autoBuild.run": "onSave",
  "latex-workshop.latex.autoClean.run": "onFailed",
  "latex-workshop.latex.clean.subfolder.enabled": false,

  "latex-workshop.view.pdf.viewer": "tab",
  "latex-workshop.synctex.afterBuild.enabled": true,

  "latex-workshop.message.badbox.show": false,
  "latex-workshop.message.warning.show": true,
  "latex-workshop.message.error.show": true
}
JSON_EOF

if [[ "$TO_STDOUT" == "yes" ]]; then
  printf '%s\n' "$JSON"
  exit 0
fi

OUT="$PROJ/.vscode/settings.json"
if [[ -f "$OUT" && "$FORCE" != "yes" ]]; then
  if ! grep -q "gen_vscode_settings.sh" "$OUT" 2>/dev/null; then
    echo "ERROR: $OUT 가 이미 있고 이 스크립트가 만든 것이 아니다." >&2
    echo "       덮어쓰려면 --force. 내용을 먼저 확인할 것." >&2
    exit 3
  fi
fi

mkdir -p "$PROJ/.vscode"
printf '%s\n' "$JSON" > "$OUT"
echo "[gen] $OUT"
echo "[gen] engine=$LATEX_ENGINE  TeX Live $LATEX_TEXLIVE_YEAR  (출처: $LATEX_ENGINE_SOURCE)"

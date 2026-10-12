#!/usr/bin/env bash
# verify_build.sh — Phase 5 verification for latex-korean-setup skill.
#
# Smoke-tests Korean rendering by:
#   1. Building examples/korean-test.tex with xelatex in a temp directory
#   2. Extracting text from the resulting PDF and grepping for Korean
#   3. Optionally repeating against the user's project (Overleaf simulation)
#
# Usage:
#   verify_build.sh                    # Test only the skill's example
#   verify_build.sh /path/to/project   # Also Overleaf-simulate the project

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE_TEX="$SKILL_DIR/examples/korean-test.tex"
MD_INJECT_SAMPLE_MD="$SKILL_DIR/examples/md_inject/sample-section.md"
MD_INJECT_SAMPLE_TARGET="$SKILL_DIR/examples/md_inject/sample-target.tex"
MD_INJECT_SAMPLE_OUTPUT="$SKILL_DIR/examples/md_inject/sample-output.tex"
GREEN='\033[32m'; RED='\033[31m'; YELLOW='\033[33m'; CYAN='\033[36m'; NC='\033[0m'
PASS=0; FAIL=0
RUN_MD_INJECT_SMOKE=0

# Parse --md-inject-smoke flag (does not consume positional args)
NEW_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --md-inject-smoke) RUN_MD_INJECT_SMOKE=1 ;;
    *) NEW_ARGS+=("$arg") ;;
  esac
done
if ((${#NEW_ARGS[@]})); then
  set -- "${NEW_ARGS[@]}"
else
  set --
fi

check() {
  local label="$1"; local ok="$2"
  if [[ "$ok" == "true" ]]; then
    echo -e "  ${GREEN}✅${NC} $label"
    PASS=$((PASS+1))
  else
    echo -e "  ${RED}❌${NC} $label"
    FAIL=$((FAIL+1))
  fi
}

require() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo -e "${RED}❌ Required command not found: $cmd${NC}"
    echo "   Install MacTeX (brew install --cask mactex-no-gui) or TeX Live."
    exit 2
  fi
}

# ── Pre-flight ──────────────────────────────────────────────────
echo -e "${CYAN}── latex-publication — Phase 5 Verify ──${NC}"

# 이 스크립트는 스킬 자체의 회귀 검증이지 사용자 프로젝트 빌드가 아니다.
# 그래서 프로젝트 설정을 찾지 않고, 검증용 엔진을 명시해서 고정한다.
# 다른 조합으로 검증하려면 VERIFY_ENGINE / VERIFY_TEXLIVE 를 준다.
export LATEX_ENGINE_OVERRIDE="${VERIFY_ENGINE:-xelatex}"
export LATEX_TEXLIVE_YEAR_OVERRIDE="${VERIFY_TEXLIVE:-2025}"
# shellcheck source=texlive_env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/texlive_env.sh"
echo -e "  engine=${LATEX_ENGINE} TeX Live ${LATEX_TEXLIVE_YEAR} — ${TL_BIN}"

require pdftotext

# ── Test 1: Build the skill's standalone example ────────────────
echo
echo -e "${CYAN}Test 1: standalone korean-test.tex${NC}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp "$EXAMPLE_TEX" "$TMP/korean-test.tex"

if (cd "$TMP" && "$TL_BIN/$LATEX_ENGINE" -interaction=nonstopmode -halt-on-error korean-test.tex >/dev/null 2>&1); then
  check "xelatex build succeeded" "true"
else
  check "xelatex build succeeded" "false"
  echo -e "  ${YELLOW}↳ Build log tail:${NC}"
  tail -20 "$TMP/korean-test.log" | sed 's/^/    /'
fi

if [[ -f "$TMP/korean-test.pdf" ]]; then
  TEXT=$(pdftotext "$TMP/korean-test.pdf" - 2>/dev/null || echo "")
  if echo "$TEXT" | grep -q '한글'; then
    check "PDF contains Korean text ('한글' detected)" "true"
  else
    check "PDF contains Korean text" "false"
    echo -e "  ${YELLOW}↳ Extracted text (first 200 chars):${NC}"
    echo "$TEXT" | head -c 200 | sed 's/^/    /'
  fi
else
  check "PDF was generated" "false"
fi

# ── Test 2: Optional Overleaf round-trip simulation ─────────────
if [[ $# -ge 1 ]]; then
  PROJECT="$1"
  if [[ ! -d "$PROJECT" ]]; then
    echo -e "${RED}❌ Project directory not found: $PROJECT${NC}"
    exit 2
  fi

  echo
  echo -e "${CYAN}Test 2: Overleaf round-trip simulation for $PROJECT${NC}"

  # Find main .tex with the SAME detection logic as scripts/diagnose.py:
  #   1) if --target <tex> or $VERIFY_TARGET_TEX is set, use it
  #   2) any .tex whose "% !TEX root = X" points to an existing file → that file
  #   3) largest .tex containing \documentclass (legacy heuristic, last resort)
  MAIN_TEX=""
  if [[ -n "${VERIFY_TARGET_TEX:-}" ]]; then
    if [[ -f "$VERIFY_TARGET_TEX" ]]; then
      MAIN_TEX="$VERIFY_TARGET_TEX"
    elif [[ -f "$PROJECT/$VERIFY_TARGET_TEX" ]]; then
      MAIN_TEX="$PROJECT/$VERIFY_TARGET_TEX"
    fi
  fi
  if [[ -z "$MAIN_TEX" ]]; then
    # Scan for % !TEX root = X magic comment; X is resolved relative to each file's dir.
    while IFS= read -r -d '' f; do
      hdr=$(head -c 2000 "$f" 2>/dev/null)
      tex_root=$(printf '%s' "$hdr" \
        | sed -nE 's|^%[[:space:]]*!TEX[[:space:]]+root[[:space:]]*=[[:space:]]*([^[:space:]]+).*|\1|p' \
        | head -1)
      if [[ -n "$tex_root" ]]; then
        root_abs="$(cd "$(dirname "$f")" && cd "$(dirname "$tex_root")" 2>/dev/null && pwd)/$(basename "$tex_root")"
        if [[ -f "$root_abs" ]]; then
          MAIN_TEX="$root_abs"
          break
        fi
      fi
    done < <(find "$PROJECT" -name '*.tex' -not -path '*/build/*' -not -path '*/.git/*' -not -path '*/.build/*' -print0 2>/dev/null)
  fi
  if [[ -z "$MAIN_TEX" ]]; then
    MAIN_TEX=$(grep -lr '\\documentclass' "$PROJECT" --include='*.tex' 2>/dev/null \
      | grep -v '/build/' | grep -v '/.git/' | grep -v '/.build/' \
      | xargs -I{} wc -c {} 2>/dev/null \
      | sort -rn | head -1 | awk '{print $2}')
  fi

  if [[ -z "$MAIN_TEX" ]]; then
    check "Main .tex detected" "false"
  else
    check "Main .tex detected: $(basename "$MAIN_TEX")" "true"

    # Sub-test: no system absolute paths in source
    HITS=$(grep -rn -E '(/Users/|/home/|~/[A-Za-z])' "$PROJECT" \
      --include='*.tex' --include='*.sty' --include='*.bib' --include='*.cls' \
      --exclude-dir=build --exclude-dir=.git 2>/dev/null \
      | grep -v '^Binary' | wc -l | tr -d ' ')
    if [[ "$HITS" == "0" ]]; then
      check "No system absolute paths in .tex/.sty/.bib/.cls" "true"
    else
      check "No system absolute paths ($HITS occurrences found)" "false"
    fi

    # Sub-test: copy project minus IDE config to fresh dir, build
    SIM=$(mktemp -d)
    rsync -a --exclude '.vscode' --exclude '.cursor' --exclude '.git' \
          --exclude 'build' --exclude '*.aux' --exclude '*.log' \
          --exclude '*.pdf' --exclude '*.fls' --exclude '*.fdb_latexmk' \
          "$PROJECT/" "$SIM/" 2>/dev/null

    SIM_MAIN_REL="${MAIN_TEX#$PROJECT/}"
    SIM_MAIN_DIR=$(dirname "$SIM/$SIM_MAIN_REL")
    SIM_MAIN_BASE=$(basename "$MAIN_TEX")

    if (cd "$SIM_MAIN_DIR" && "$TL_BIN/$LATEX_ENGINE" -interaction=nonstopmode -halt-on-error "$SIM_MAIN_BASE" >/dev/null 2>&1); then
      check "Overleaf simulation: builds without IDE config" "true"
    else
      check "Overleaf simulation: builds without IDE config" "false"
      LOG="${SIM_MAIN_BASE%.tex}.log"
      if [[ -f "$SIM_MAIN_DIR/$LOG" ]]; then
        echo -e "  ${YELLOW}↳ Last 15 lines of $LOG:${NC}"
        tail -15 "$SIM_MAIN_DIR/$LOG" | sed 's/^/    /'
      fi
    fi
    rm -rf "$SIM"
  fi
fi

# ── Test 3: Optional MD→TeX injection smoke test ────────────────
if (( RUN_MD_INJECT_SMOKE == 1 )); then
  echo
  echo -e "${CYAN}Test 3: md_inject smoke (sample-section.md → sample-target.tex)${NC}"
  if ! command -v pandoc >/dev/null 2>&1; then
    check "pandoc available" "false"
  else
    check "pandoc available" "true"
    SMOKE_DIR=$(mktemp -d)
    mkdir -p "$SMOKE_DIR/docs"
    cp "$MD_INJECT_SAMPLE_MD" "$SMOKE_DIR/docs/sample-section.md"
    cp "$MD_INJECT_SAMPLE_TARGET" "$SMOKE_DIR/main.tex"
    if python3 "$SKILL_DIR/scripts/md_inject/md_inject.sh" "$SMOKE_DIR" \
         --md-root docs --workers 2 --no-verify >/dev/null 2>&1 \
       || bash "$SKILL_DIR/scripts/md_inject/md_inject.sh" "$SMOKE_DIR" \
         --md-root docs --workers 2 --no-verify >/dev/null 2>&1; then
      check "md_inject.sh end-to-end succeeded" "true"
    else
      check "md_inject.sh end-to-end succeeded" "false"
    fi
    # Verify that a fragment was produced (flat_id sanitizes '-' → '_')
    if [[ -f "$SMOKE_DIR/.build/md_inject/sample_section.tex.fragment" ]]; then
      check "fragment file produced" "true"
    else
      check "fragment file produced" "false"
    fi
    # h1_strip removes the MD H1, so the fragment's injected Korean is
    # detected by more distinctive prose (「생존 압력」 is colored in source).
    if grep -q '생존 압력' "$SMOKE_DIR/main.tex" 2>/dev/null; then
      check "main.tex contains injected Korean content" "true"
    else
      check "main.tex contains injected Korean content" "false"
    fi
    # Try to build the injected main.tex
    if (cd "$SMOKE_DIR" && "$TL_BIN/$LATEX_ENGINE" -interaction=nonstopmode -halt-on-error main.tex >/dev/null 2>&1); then
      check "xelatex on injected main.tex succeeded" "true"
    else
      check "xelatex on injected main.tex succeeded" "false"
      echo -e "  ${YELLOW}↳ Build log tail:${NC}"
      tail -15 "$SMOKE_DIR/main.log" 2>/dev/null | sed 's/^/    /'
    fi
    rm -rf "$SMOKE_DIR"
  fi
fi

# ── Summary ─────────────────────────────────────────────────────
echo
echo -e "${CYAN}─────────────────────────────────────${NC}"
if [[ "$FAIL" -eq 0 ]]; then
  echo -e "${GREEN}All checks passed: $PASS/$PASS${NC}"
  exit 0
else
  echo -e "${RED}Failed: $FAIL  Passed: $PASS${NC}"
  exit 1
fi

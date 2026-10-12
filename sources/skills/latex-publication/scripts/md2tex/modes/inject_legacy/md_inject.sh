#!/usr/bin/env bash
# md_inject.sh — Phase 6→7→9→10 orchestrator (Python-only fast path)
#
# Top-level entrypoint that chains:
#   Phase 6  md_inject_plan.py      (plan)
#   Phase 7  md_inject_convert.py   (parallel convert)
#   Phase 9  md_inject_apply.py     (atomic apply)
#   Phase 10 verify_build.sh        (xelatex smoke)
#
# Phase 8 (LLM fragment auditor) runs in the SKILL.md workflow between
# Phase 7 and Phase 9 when invoked via the skill; this Bash wrapper is
# the headless fast path that skips LLM steps.
#
# Usage:
#   md_inject.sh [project_dir]
#                [--target main.tex]
#                [--md-root docs/]
#                [--manifest md-inject.yaml]
#                [--workers N]
#                [--no-auto-cite]
#                [--dry-run]
#                [--no-verify]
#                [--force]

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
PLAN_PY="$SKILL_DIR/scripts/md2tex/modes/inject_legacy/md_inject_plan.py"
CONV_PY="$SKILL_DIR/scripts/md2tex/modes/inject_legacy/md_inject_convert.py"
APPLY_PY="$SKILL_DIR/scripts/md2tex/modes/inject_legacy/md_inject_apply.py"
VERIFY_SH="$SKILL_DIR/scripts/verify_build.sh"

GREEN='\033[32m'; RED='\033[31m'; YELLOW='\033[33m'; CYAN='\033[36m'; NC='\033[0m'

PROJECT="."
TARGET=""
MD_ROOT="docs"
MANIFEST=""
WORKERS=8
AUTO_CITE=1
DRY_RUN=0
NO_VERIFY=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)        TARGET="$2"; shift 2 ;;
    --md-root)       MD_ROOT="$2"; shift 2 ;;
    --manifest)      MANIFEST="$2"; shift 2 ;;
    --workers)       WORKERS="$2"; shift 2 ;;
    --no-auto-cite)  AUTO_CITE=0; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    --no-verify)     NO_VERIFY=1; shift ;;
    --force)         FORCE=1; shift ;;
    -h|--help)
      sed -n '3,30p' "$0"; exit 0 ;;
    --*)             echo "unknown flag: $1"; exit 2 ;;
    *)               PROJECT="$1"; shift ;;
  esac
done

PROJECT="$(cd "$PROJECT" && pwd)"
echo -e "${CYAN}── md_inject: project ${PROJECT} ──${NC}"

# Phase 6 — plan
PLAN_JSON="$PROJECT/.build/md_inject/plan.json"
echo -e "${CYAN}Phase 6: planning...${NC}"
PLAN_ARGS=(--md-root "$MD_ROOT" --out "$PLAN_JSON")
if [[ -n "$TARGET" ]];   then PLAN_ARGS+=(--target "$TARGET"); fi
if [[ -n "$MANIFEST" ]]; then PLAN_ARGS+=(--manifest "$MANIFEST"); fi
python3 "$PLAN_PY" "$PROJECT" "${PLAN_ARGS[@]}"

# If plan has no injections, bail out
if ! python3 -c "import json, sys; p=json.load(open(sys.argv[1])); sys.exit(0 if p.get('injections') else 1)" "$PLAN_JSON"; then
  echo -e "${YELLOW}No injections planned. Add % MD-INJECT markers to your main.tex, then re-run.${NC}"
  exit 0
fi

# Phase 7 — convert
echo
echo -e "${CYAN}Phase 7: converting (workers=${WORKERS})...${NC}"
CONV_ARGS=(--plan "$PLAN_JSON" --workers "$WORKERS")
(( AUTO_CITE == 0 )) && CONV_ARGS+=(--no-auto-cite)
(( FORCE == 1 )) && CONV_ARGS+=(--force)
python3 "$CONV_PY" "${CONV_ARGS[@]}"

# Phase 9 — apply
echo
echo -e "${CYAN}Phase 9: applying...${NC}"
APPLY_ARGS=(--plan "$PLAN_JSON")
(( DRY_RUN == 1 )) && APPLY_ARGS+=(--dry-run)
(( FORCE == 1 )) && APPLY_ARGS+=(--force)
python3 "$APPLY_PY" "${APPLY_ARGS[@]}"

# Phase 10 — verify
if (( NO_VERIFY == 1 || DRY_RUN == 1 )); then
  echo -e "${YELLOW}(skipped verify)${NC}"
  exit 0
fi

echo
echo -e "${CYAN}Phase 10: verifying build...${NC}"
bash "$VERIFY_SH" "$PROJECT"

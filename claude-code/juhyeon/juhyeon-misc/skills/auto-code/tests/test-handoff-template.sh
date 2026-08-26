#!/usr/bin/env bash
# handoff 템플릿이 필수 자리표시자와 SDD 실행 지시를 갖췄는지 검사한다.
set -uo pipefail

TPL="$HOME/.claude/skills/auto-code/references/handoff-template.md"

FAILED=0
note() { echo "FAIL - $1"; FAILED=$((FAILED + 1)); }

[ -f "$TPL" ] || { note "템플릿 없음: $TPL"; echo "failed: $FAILED"; exit 1; }

for ph in '{{PLAN_PATH}}' '{{SPEC_PATH}}' '{{DESIGN_DOC}}' '{{TOPIC}}' '{{DATE}}' '{{GLOBAL_CONSTRAINTS}}' '{{OPEN_RISKS}}'; do
  grep -qF "$ph" "$TPL" || note "자리표시자 누락: $ph"
done

grep -qF 'superpowers:subagent-driven-development' "$TPL" || note "SDD 호출 지시 누락"

if [ "$FAILED" -eq 0 ]; then
  echo "ok   - handoff 템플릿 검증 통과"
else
  echo "failed: $FAILED"
fi
[ "$FAILED" -eq 0 ]

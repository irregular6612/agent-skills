#!/usr/bin/env bash
# auto-code SKILL.md의 구조 요건을 검사한다.
set -uo pipefail

SKILL="$HOME/.claude/skills/auto-code/SKILL.md"

FAILED=0
note() { echo "FAIL - $1"; FAILED=$((FAILED + 1)); }

[ -f "$SKILL" ] || { note "SKILL.md 없음: $SKILL"; echo "failed: $FAILED"; exit 1; }

grep -q '^name: auto-code' "$SKILL" || note "frontmatter name이 auto-code가 아님"
grep -q '^description:' "$SKILL"       || note "description 누락"

# 4단계 + Stage 0이 모두 명시되는가
for stage in 'Stage 0' 'Stage 1' 'Stage 2' 'Stage 3' 'Stage 4'; do
  grep -qF "$stage" "$SKILL" || note "단계 누락: $stage"
done

# 게이트를 스크립트로 호출하는가 (패턴 복사 금지 원칙)
grep -qF 'scripts/gate.sh' "$SKILL" || note "gate.sh 호출 없음"
grep -qE 'gate\.sh 1' "$SKILL" || note "GATE1 호출 없음"
grep -qE 'gate\.sh 2' "$SKILL" || note "GATE2 호출 없음"
grep -qE 'gate\.sh 3' "$SKILL" || note "GATE3 호출 없음"

# 의존 자산을 실제로 참조하는가
grep -qF 'spec-bridge' "$SKILL"           || note "spec-bridge 디스패치 없음"
grep -qF 'handoff-template.md' "$SKILL"   || note "handoff 템플릿 참조 없음"
grep -qF 'grilling' "$SKILL"              || note "grilling 호출 없음"
grep -qF 'domain-modeling' "$SKILL"       || note "domain-modeling 호출 없음"

# Stage 1-b 어댑터가 명시되는가. grilling은 파일을 안 쓰므로 이 단계가 빠지면
# 브릿지에 넘길 입력이 존재하지 않는다 — 파이프라인이 조용히 끊긴다.
grep -qF 'Stage 1-b' "$SKILL"             || note "설계문서 어댑터(Stage 1-b) 없음"
grep -qF 'docs/superpowers/designs' "$SKILL" || note "설계문서 출력 경로 없음"

# 삭제된 gstack에 다시 의존하지 않는가 (회귀 방지)
grep -qF 'gstack' "$SKILL"                && note "gstack 의존 잔존 — 삭제된 스킬이다"
grep -qF 'writing-plans' "$SKILL"         || note "writing-plans 호출 없음"

# 참조 대상 실재 확인 (dangling 방지)
for dep in \
  "$HOME/.claude/skills/auto-code/scripts/gate.sh" \
  "$HOME/.claude/skills/auto-code/references/bridge-contract.md" \
  "$HOME/.claude/skills/auto-code/references/handoff-template.md" \
  "$HOME/.claude/agents/spec-bridge.md"; do
  [ -f "$dep" ] || note "참조 대상 부재: $dep"
done

if [ "$FAILED" -eq 0 ]; then
  echo "ok   - SKILL.md 구조 검증 통과"
else
  echo "failed: $FAILED"
fi
[ "$FAILED" -eq 0 ]

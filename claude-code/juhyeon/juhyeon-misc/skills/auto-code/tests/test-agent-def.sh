#!/usr/bin/env bash
# spec-bridge 에이전트 정의의 필수 조건을 검사한다.
set -uo pipefail

AGENT="$HOME/.claude/agents/spec-bridge.md"
CONTRACT="$HOME/.claude/skills/auto-code/references/bridge-contract.md"

FAILED=0
note() { echo "FAIL - $1"; FAILED=$((FAILED + 1)); }

[ -f "$AGENT" ] || { note "에이전트 정의 없음: $AGENT"; echo "failed: $FAILED"; exit 1; }

grep -q '^name: spec-bridge' "$AGENT" || note "frontmatter name이 spec-bridge가 아님"
grep -q '^model: sonnet' "$AGENT"     || note "model: sonnet 핀 고정 누락"
grep -q '^description:' "$AGENT"      || note "description 누락"

# 계약 파일을 실제로 참조하는가
grep -qF 'bridge-contract.md' "$AGENT" || note "bridge-contract.md 참조 없음"

# 반환 형식 3개 키를 본문에 명시하는가
for key in 'SPEC_PATH:' 'FILLED:' 'OPEN_QUESTIONS:'; do
  grep -qF "$key" "$AGENT" || note "반환 키 누락: $key"
done

# 참조 대상이 실제로 존재하는가 (dangling 참조 방지)
[ -f "$CONTRACT" ] || note "참조 대상 부재: $CONTRACT"

if [ "$FAILED" -eq 0 ]; then
  echo "ok   - spec-bridge 정의 검증 통과"
else
  echo "failed: $FAILED"
fi
[ "$FAILED" -eq 0 ]

#!/usr/bin/env bash
# check_sync.sh — SKILL.md ↔ agents/academic-reviewer.md 동기화 드리프트 가드 (v4 cycle, V4-B)
#
# changelog v3.x "Sync 의무" 3개 항목이 양쪽 파일에 모두 존재하는지 검증한다.
# v3 root cause(prohibition이 agent.md에만 있고 SKILL.md에는 없던 누락)의 재발 방지용.
# pre-commit hook 또는 수동 실행. 경로는 환경변수로 override 가능.
#
# 종료코드: 0 = sync OK / 1 = drift 발견 / 2 = 파일 없음
set -u

SKILL="${SKILL_MD:-$HOME/.claude/skills/iterative-academic-writer/SKILL.md}"
AGENT="${AGENT_MD:-$HOME/.claude/agents/academic-reviewer.md}"

for f in "$SKILL" "$AGENT"; do
  [ -f "$f" ] || { echo "ERROR: 파일 없음 — $f" >&2; exit 2; }
done

fail=0
note() { printf '  %-26s %s\n' "$1" "$2"; }

echo "=== Sync item 1: C1-C9 채점 표 (Score 0/1/2) ==="
s=$(grep -c 'Score 0 | Score 1 | Score 2' "$SKILL")
a=$(grep -c 'Score 0 | Score 1 | Score 2' "$AGENT")
note "SKILL 채점 헤더 (≥1):" "$s"
note "agent 채점 헤더 (≥1):" "$a"
{ [ "$s" -ge 1 ] && [ "$a" -ge 1 ]; } || { echo "  DRIFT: 채점 표 헤더 누락" >&2; fail=1; }

echo "=== Sync item 2: W1-W17 catalog ==="
w1=$(grep -cE '\| W1  \| Unverified citation' "$SKILL")
w17=$(grep -cE '\| W17 \| Numeric results' "$SKILL")
ref=$(grep -cE 'W1[~-]W17' "$AGENT")
note "SKILL W1 rows (≥2: body+inline):" "$w1"
note "SKILL W17 rows (≥2):" "$w17"
note "agent W1-W17 참조 (≥1):" "$ref"
{ [ "$w1" -ge 2 ] && [ "$w17" -ge 2 ] && [ "$ref" -ge 1 ]; } \
  || { echo "  DRIFT: W catalog 불일치 (SKILL 2-copy 또는 agent ref 누락)" >&2; fail=1; }

echo "=== Sync item 3: prohibition rules ==="
for phrase in 'JSON 출력 금지' 'pass/fail 판단 금지'; do
  s=$(grep -c "$phrase" "$SKILL")
  a=$(grep -c "$phrase" "$AGENT")
  note "[$phrase]" "SKILL=$s agent=$a (each ≥1)"
  { [ "$s" -ge 1 ] && [ "$a" -ge 1 ]; } \
    || { echo "  DRIFT: '$phrase' 한쪽 누락" >&2; fail=1; }
done

echo ""
if [ "$fail" -eq 0 ]; then
  echo "PASS: 3개 sync 항목 모두 SKILL.md ↔ agent.md 동기화 상태"
else
  echo "FAIL: drift 발견 — changelog v3.x 'Sync 의무' 참조 후 양쪽 동시 갱신" >&2
fi
exit "$fail"

#!/usr/bin/env bash
# check_sync.sh — Critic 단일 기준 문서 연결과 중복 방지 검사
# 종료코드: 0 = sync OK / 1 = drift 발견 / 2 = 파일 없음
set -u

SKILLDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
REPO="$(cd "$SKILLDIR/../../.." && pwd -P)"
SKILL="${SKILL_MD:-$SKILLDIR/SKILL.md}"
AGENT="${AGENT_MD:-$REPO/sources/agents/academic-reviewer-claude.md}"
CODEX_AGENT="$REPO/sources/agents/academic-reviewer-codex.toml"
PROTOCOL="${PROTOCOL_MD:-$SKILLDIR/references/critic-review-protocol.md}"

for f in "$SKILL" "$AGENT" "$CODEX_AGENT" "$PROTOCOL"; do
  [ -f "$f" ] || { echo "ERROR: 파일 없음 — $f" >&2; exit 2; }
done

fail=0
note() { printf '  %-32s %s\n' "$1" "$2"; }
require_pattern() {
  label="$1"
  pattern="$2"
  file="$3"
  count=$(grep -cE "$pattern" "$file" || true)
  note "$label" "$count"
  [ "$count" -ge 1 ] || { echo "  DRIFT: $label 누락" >&2; fail=1; }
}

echo "=== Single source: critic-review-protocol.md ==="
require_pattern "25 Principles" '^## 25 Principles$' "$PROTOCOL"
require_pattern "Critical rubric" 'Score 0.*Score 1.*Score 2' "$PROTOCOL"
require_pattern "W1 catalog" '^\| W1 \|' "$PROTOCOL"
require_pattern "W17 catalog" '^\| W17 \|' "$PROTOCOL"
require_pattern "Critic prompt template" '^## Critic Prompt Template$' "$PROTOCOL"
require_pattern "Output rules" '^## Output Rules$' "$PROTOCOL"
require_pattern "Language-aware rule" '요청 언어의 자연스러운 학술 문체' "$PROTOCOL"
require_pattern "Allowed structured lists" '구조화가 더 정확한 부분은 목록을' "$PROTOCOL"
require_pattern "Scoped uncertainty" '정의상 고정된 값에는 요구하지' "$PROTOCOL"
require_pattern "Remove unsupported proposition" '미검증 명제 전체를' "$SKILL"

echo "=== Consumers reference the single source ==="
require_pattern "SKILL protocol reference" 'references/critic-review-protocol\.md' "$SKILL"
require_pattern "Agent protocol reference" 'critic-review-protocol\.md' "$AGENT"
require_pattern "Codex protocol reference" 'critic-review-protocol\.md' "$CODEX_AGENT"

echo "=== Duplicate rubric guard ==="
for f in "$SKILL" "$AGENT" "$CODEX_AGENT"; do
  score_tables=$(grep -cE 'Score 0.*Score 1.*Score 2' "$f" || true)
  w17_rows=$(grep -cE '^\| W17 \|' "$f" || true)
  note "$(basename "$f") score/W17 copies" "$score_tables/$w17_rows"
  { [ "$score_tables" -eq 0 ] && [ "$w17_rows" -eq 0 ]; } || {
    echo "  DRIFT: protocol 밖에 평가표가 복사됨 — $f" >&2
    fail=1
  }
done

echo ""
if [ "$fail" -eq 0 ]; then
  echo "PASS: Critic 평가 기준은 protocol 한 곳에 있고 두 consumer가 이를 참조함"
else
  echo "FAIL: Critic protocol 연결 또는 단일 기준 원칙 위반" >&2
fi
exit "$fail"

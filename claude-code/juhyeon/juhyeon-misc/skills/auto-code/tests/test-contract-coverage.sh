#!/usr/bin/env bash
# 설계문서 스키마의 모든 섹션이 bridge-contract.md 매핑표에 등장하는지 검사한다.
#
# 단일 원천은 auto-code SKILL.md의 Stage 1-b "#### 스키마" 펜스 블록이다.
# 어댑터가 쓰는 섹션과 브릿지가 읽는 섹션이 갈라지면 이 테스트가 먼저 깨진다.
# (구 버전은 ~/.claude/skills/office-hours/SKILL.md를 원천으로 삼았다. 그
# 스킬이 사라지면 SEARCH가 비어 skip으로 조용히 통과했다 — 지금은 원천이
# 이 저장소 안에 있으므로 skip 경로 자체가 없다.)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACT="$HERE/../references/bridge-contract.md"
SKILL="$HERE/../SKILL.md"

# 스키마가 실제로 추출됐는지 확인하는 하한. 추출 경계가 어긋나면 0개가 나오고
# 아래 루프가 한 번도 안 돌아 MISSING=0으로 조용히 통과한다 — vacuous-pass다.
MIN_SECTIONS=5

MISSING=0
note() { echo "FAIL - $1"; MISSING=$((MISSING + 1)); }

[ -f "$CONTRACT" ] || { echo "FAIL - 계약 파일 없음: $CONTRACT"; exit 1; }
[ -f "$SKILL" ]    || { echo "FAIL - SKILL.md 없음: $SKILL"; exit 1; }

# Stage 1-b 스키마 블록 안의 '## 섹션명'을 뽑는다.
# 경계: '#### 스키마' 부터 '#### 철칙' 직전까지.
SECTIONS=$(awk '
  /^#### 스키마/ { intpl = 1; next }
  /^#### 철칙/   { intpl = 0 }
  intpl && /^## / { print }
' "$SKILL" | sort -u)

COUNT=$(printf '%s\n' "$SECTIONS" | grep -c '^## ' || true)
if [ "$COUNT" -lt "$MIN_SECTIONS" ]; then
  note "스키마 섹션 추출 실패: ${COUNT}개만 발견 (최소 ${MIN_SECTIONS}개 필요)"
  echo "       SKILL.md Stage 1-b의 '#### 스키마' / '#### 철칙' 경계를 확인할 것"
fi

while IFS= read -r line; do
  [ -n "$line" ] || continue
  name="${line#\#\# }"
  grep -qF "$name" "$CONTRACT" || note "매핑표에 없는 설계문서 섹션: $name"
done <<< "$SECTIONS"

# GATE1이 요구하는 네 섹션이 스키마에 실제로 있는가.
# 어댑터가 이 중 하나라도 빠뜨리면 자기가 쓴 문서가 자기 게이트에 걸린다.
for req in 'Problem Statement' 'Constraints' 'Recommended Approach' 'Success Criteria'; do
  printf '%s\n' "$SECTIONS" | grep -qF "## $req" || note "스키마에 GATE1 필수 섹션 없음: $req"
done

# 스키마가 Status 줄을 담는가 — GATE1의 승인 확인 장치.
awk '/^#### 스키마/{i=1;next} /^#### 철칙/{i=0} i' "$SKILL" | grep -qF '**Status:**' \
  || note "스키마에 Status 줄 없음 (GATE1의 승인 확인이 성립 불가)"

for anchor in '## 산출 스키마' '## 매핑표' '## 출처 표기 규칙' '### Domain Notes 처리'; do
  grep -qF "$anchor" "$CONTRACT" || note "필수 앵커 누락: $anchor"
done

if [ "$MISSING" -eq 0 ]; then
  echo "ok   - 설계문서 섹션 ${COUNT}개 전부 매핑됨, GATE1 필수 4섹션·Status·앵커 존재"
else
  echo "missing: $MISSING"
fi
[ "$MISSING" -eq 0 ]

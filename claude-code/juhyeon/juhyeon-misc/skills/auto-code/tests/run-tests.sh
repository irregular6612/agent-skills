#!/usr/bin/env bash
# auto-code 게이트 스모크 테스트.
# 각 픽스처를 gate.sh에 넣고 기대 종료코드와 대조한다.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="$HERE/../scripts/gate.sh"
FIX="$HERE/fixtures"

PASS=0
FAIL=0

# check <설명> <게이트번호> <픽스처파일> <기대종료코드>
check() {
  local desc="$1" gate="$2" file="$3" want="$4"
  bash "$GATE" "$gate" "$FIX/$file" >/dev/null 2>&1
  local got=$?
  if [ "$got" -eq "$want" ]; then
    echo "ok   - $desc (exit $got)"
    PASS=$((PASS + 1))
  else
    echo "FAIL - $desc (want exit $want, got $got)"
    FAIL=$((FAIL + 1))
  fi
}

check "GATE1 정상 문서는 통과"            1 gate1-good.md               0
check "GATE1 DRAFT 상태는 거부"           1 gate1-bad-draft.md          1
check "GATE1 필수 섹션 누락은 거부"        1 gate1-bad-missing-section.md 1
# 회귀: 필수 섹션이 펜스 예시 안에만 있으면 실제 섹션이 아니므로 거부해야 한다.
# 펜스 인지 전에는 예시만으로 통과했다(실측).
check "GATE1 펜스 안에만 있는 섹션은 거부"  1 gate1-bad-fenced-only-section.md 1
check "GATE2 정상 spec은 통과"            2 gate2-good.md               0
# 회귀: 펜스 코드블록 안의 스키마 리스팅이 실제 섹션보다 앞에 와도
# has_body()가 오탐하지 않아야 한다. 펜스 인지 전에는 여기서 실패했다.
check "GATE2 펜스 스키마 리스팅 오탐 없음"  2 gate2-good-fenced-schema.md 0
check "GATE2 빈 블록은 거부"              2 gate2-bad-empty-block.md    1
check "GATE2 미해소 추론 태그는 거부"      2 gate2-bad-inference-tag.md  1
# 회귀: 계약이 요구하는 문서 모양(펜스 안에 '## Open Questions'를 담은 산출
# 스키마) 때문에 [추론] 스캐너가 통째로 건너뛰어지면 안 된다. 조기 exit이
# 펜스 판정보다 앞에 있던 시절 이 픽스처는 통과했다(실측).
check "GATE2 펜스 스키마 뒤 미해소 추론 거부" 2 gate2-bad-fenced-schema-inference.md 1
check "GATE3 정상 plan은 통과"            3 gate3-good.md               0
check "GATE3 Global Constraints 누락 거부" 3 gate3-bad-no-constraints.md 1
check "GATE3 Interfaces 블록 누락 거부"    3 gate3-bad-no-interfaces.md  1
# 회귀: Task 헤더가 펜스 예시 안에만 있는 계획서는 SDD가 task를 0건 추출한다.
# 게이트에서 잡아야 한다. 펜스 인지 전에는 통과했다(실측).
check "GATE3 펜스 안에만 있는 Task는 거부"  3 gate3-bad-fenced-only-task.md 1

echo
echo "passed: $PASS, failed: $FAIL"
[ "$FAIL" -eq 0 ]

#!/usr/bin/env bash
# auto-code 파이프라인 단계 경계 게이트.
#
# 사용법: gate.sh <1|2|3> <artifact-path>
#   1 = Stage 1-b 설계문서 계약
#   2 = 브릿지 spec 계약
#   3 = writing-plans 산출 plan의 SDD 파싱 가능성
#
# 종료코드: 0 통과 / 1 계약 위반 / 2 사용법 오류
set -uo pipefail

GATE="${1:-}"
FILE="${2:-}"

usage() {
  echo "usage: gate.sh <1|2|3> <artifact-path>" >&2
  exit 2
}

fail() {
  echo "GATE${GATE} FAIL: $1" >&2
  exit 1
}

[ -n "$GATE" ] || usage
[ -n "$FILE" ] || usage
[ -f "$FILE" ] || fail "파일 없음: $FILE"

# ---------------------------------------------------------------------------
# 공유 펜스 상태 기계.
#
# 세 게이트 전부 "펜스 코드블록 안의 줄은 문서의 구조가 아니다"라는 같은 규칙을
# 쓴다. 계약 문서(bridge-contract.md)의 산출 스키마와 writing-plans 계획서의
# 예시 Task 블록이 모두 펜스 안에 실제 헤더 문자열을 담고 있기 때문이다.
# 펜스를 모르면 두 방향으로 다 틀린다:
#   - 오탐: 스키마 리스팅의 '## Architecture'를 실제 섹션으로 붙잡아 "본문 비어있음"
#   - 미탐: 예시 블록의 '### Task 1:'만으로 GATE3 통과 → SDD에서 터짐
#
# fence_scan()은 펜스 마커 줄이면 상태를 갱신하고 1을 반환한다(호출부는 next).
# CommonMark처럼 여는 마커의 길이/문자를 기억해, 더 짧거나 다른 문자의 마커는
# 닫지 못하게 한다. 계획서가 ````markdown 안에 ```js를 중첩하는 실제 모양을
# 그대로 처리해야 하기 때문이다. 닫는 마커는 정보 문자열이 없어야 한다.
AWK_FENCE='
function fence_scan(line,   ch, len) {
  if (match(line, /^[`~][`~][`~]+/) != 1) { return 0 }
  ch  = substr(line, 1, 1)
  len = RLENGTH
  if (!FENCE) { FENCE = 1; FCH = ch; FLEN = len; return 1 }
  if (ch == FCH && len >= FLEN && line ~ /^[`~]+[ \t]*$/) { FENCE = 0 }
  return 1
}
'

# 펜스 밖에서 패턴이 등장하는 줄이 있는가.
#   $1 = 패턴, $2 = fixed(부분 문자열) | regex(ERE)
# 종료코드 0이면 존재. 백슬래시가 -v 대입에서 처리되는 것을 피하려고
# 호출부는 정규식에 '\*' 대신 '[*]'를 쓴다.
#
# 인라인 코드 스팬은 지운다 — GATE2의 [추론] 스캐너와 같은 규율이다.
# "`## Success Criteria`는 펜스 안에만 있다" 같은 산문 속 언급은 그 섹션이
# 존재한다는 증거가 아니다. 펜스만 걸러내면 이 언급이 요건을 만족시켜 버린다.
has_unfenced() {
  awk -v pat="$1" -v mode="$2" "$AWK_FENCE"'
    { if (fence_scan($0)) next }
    FENCE { next }
    { line = $0; gsub(/`[^`]*`/, "", line) }
    (mode == "fixed") ? (index(line, pat) > 0) : (line ~ pat) { found = 1; exit }
    END { exit !found }
  ' "$FILE"
}

# 헤더 바로 아래에 비어있지 않은 본문 줄이 있는지 검사.
# 다음 '## ' 헤더를 만나기 전에 내용이 나와야 한다.
# 펜스 안의 줄은 헤더로 치지 않는다 — 단, 헤더를 이미 찾은 뒤(=본문 안의
# 코드블록)의 내용 줄은 본문으로 인정한다.
has_body() {
  local hdr="$1"
  awk -v hdr="$hdr" "$AWK_FENCE"'
    { if (fence_scan($0)) next }
    FENCE                { if (found && NF) { print "yes"; exit } ; next }
    index($0, hdr) == 1  { found = 1; next }
    found && /^## /      { exit }
    found && NF          { print "yes"; exit }
  ' "$FILE"
}

case "$GATE" in
  1)
    has_unfenced '^Status: APPROVED' regex || fail "Status: APPROVED 아님 (설계문서 승인 미완료)"
    # 펜스 인지 필수: 설계문서가 "템플릿은 이렇게 생겼다"며 섹션 목록을 코드블록에
    # 실어두면, 펜스를 모르는 grep은 그 예시만으로 필수 섹션이 있다고 판정한다.
    # 브릿지는 그 문서에서 실제 본문을 찾지 못한다.
    for s in '## Problem Statement' '## Constraints' '## Recommended Approach' '## Success Criteria'; do
      has_unfenced "$s" fixed || fail "필수 섹션 누락: $s"
    done
    ;;
  2)
    for s in '## Architecture' '## Data Flow' '## Error Handling' '## Testing Strategy' '## Global Constraints'; do
      has_unfenced "$s" fixed || fail "블록 누락: $s"
      [ -n "$(has_body "$s")" ] || fail "블록 본문 비어있음: $s"
    done
    # 미해소 [추론] 태그 탐지. 네 조건을 동시에 만족하는 줄만 위반이다:
    #   1) 펜스 코드블록 바깥             — 출처 표기 문법 예시는 제외
    #   2) '## Open Questions' 이전 구간  — 이월된 항목은 명시적 기록이므로 허용
    #   3) 리스트 항목('- ' 또는 '* ')    — 실제 제약/항목만 대상
    #   4) 인라인 코드 스팬 제거 후       — 규칙을 설명하는 `[추론]` 언급은 제외
    # 1과 4가 없으면 이 규칙을 문서화한 spec이 자기 게이트에 걸린다(실측 확인).
    # 순서가 중요하다: 펜스 판정이 Open Questions 조기 exit보다 **먼저**여야 한다.
    # 계약의 산출 스키마는 펜스 안에 '## Open Questions'를 담고 있고 브릿지는 그
    # 스키마를 그대로 따라 쓰므로, 조기 exit이 앞에 있으면 계약을 지킨 spec일수록
    # 리스트 항목을 한 줄도 못 읽고 무조건 통과한다 — 검사 자체가 사라진다(실측).
    if awk "$AWK_FENCE"'
      { if (fence_scan($0)) next }
      FENCE                { next }
      /^## Open Questions/ { exit }
      /^[-*] /             { gsub(/`[^`]*`/, ""); print }
    ' "$FILE" | grep -qF '[추론]'; then
      fail "미해소 [추론] 태그 존재 — OPEN_QUESTIONS로 승격하거나 Open Questions로 이월할 것"
    fi
    ;;
  3)
    has_unfenced '^## Global Constraints' regex || fail "## Global Constraints 누락"
    # SDD task-brief 자신의 추출 정규식은 '^#+[ \t]+Task[ \t]+[0-9]+'로 더 느슨하다
    # (헤더 수준 무관, 콜론 불필요). 여기서는 의도적으로 '^### Task N:'만 통과시킨다.
    # writing-plans 템플릿이 실제로 내는 형태가 그것이고, 느슨하게 받아 두면
    # '## Task 1' 같은 변종이 게이트를 통과한 뒤 SDD의 task 경계 분할에서
    # 어긋난다. 오탐(엄격) 쪽으로 기울여 Stage 3에서 사람이 보강하게 한다.
    #
    # 펜스 인지 필수: 계획서는 "Task 블록은 이렇게 쓴다"는 예시를 펜스 안에 싣는
    # 것이 정상이다(이 저장소의 실제 계획서가 그렇다). 펜스를 모르면 예시만 있고
    # 진짜 Task가 없는 계획서가 통과한 뒤 SDD의 task 추출에서 0건이 나온다.
    has_unfenced '^### Task [0-9]+:' regex || fail "### Task N: 헤더 없음 (SDD task-brief가 추출 불가)"
    has_unfenced '^[*][*]Files:[*][*]' regex || fail "**Files:** 블록 없음"
    has_unfenced '^[*][*]Interfaces:[*][*]' regex || fail "**Interfaces:** 블록 없음"
    ;;
  *)
    echo "unknown gate: $GATE" >&2
    usage
    ;;
esac

echo "GATE${GATE} PASS: $FILE"

#!/usr/bin/env bash
# 게이트를 합성 픽스처가 아니라 실제 산출물에 대고 돌린다.
# 이 저장소는 auto-code 파이프라인을 수동으로 한 바퀴 돌아
# 진짜 spec과 plan을 남겼다. 그것이 회귀 기준이다.
set -uo pipefail

GATE="$HOME/.claude/skills/auto-code/scripts/gate.sh"
SPEC="$HOME/.claude/docs/superpowers/specs/2026-08-05-auto-code-design.md"
PLAN="$HOME/.claude/docs/superpowers/plans/2026-08-05-auto-code.md"
TPL="$HOME/.claude/skills/auto-code/references/handoff-template.md"

FAILED=0
note() { echo "FAIL - $1"; FAILED=$((FAILED + 1)); }

# GATE 2: 실제 spec이 브릿지 계약을 만족하는가
if [ -f "$SPEC" ]; then
  if bash "$GATE" 2 "$SPEC" >/dev/null 2>&1; then
    echo "ok   - 실제 spec이 GATE2 통과"
  else
    note "실제 spec이 GATE2 실패: $(bash "$GATE" 2 "$SPEC" 2>&1 >/dev/null)"
  fi
else
  note "실제 spec 없음: $SPEC"
fi

# GATE 3: 실제 plan을 SDD task-brief가 파싱 가능한가
if [ -f "$PLAN" ]; then
  if bash "$GATE" 3 "$PLAN" >/dev/null 2>&1; then
    echo "ok   - 실제 plan이 GATE3 통과"
  else
    note "실제 plan이 GATE3 실패: $(bash "$GATE" 3 "$PLAN" 2>&1 >/dev/null)"
  fi
  # Task 헤더가 1개 이상 잡히는가 (task-brief가 실제로 뽑을 대상).
  # plan 본문에 게이트 픽스처가 인라인돼 있어 이 개수는 실제 Task 수보다 클 수 있다.
  # 정확한 수를 단언하지 않고 존재만 확인한다.
  n=$(grep -cE '^### Task [0-9]+:' "$PLAN")
  [ "$n" -ge 1 ] || note "plan에서 Task 헤더를 하나도 못 찾음"
  echo "ok   - plan에서 Task 헤더 ${n}개 인식 (픽스처 포함 가능)"
else
  note "실제 plan 없음: $PLAN"
fi

# handoff 템플릿이 치환 후 자리표시자를 남기지 않는가 (Success Criteria 3)
if [ -f "$TPL" ]; then
  tmp=$(mktemp)
  sed -e "s|{{TOPIC}}|auto-code|g" \
      -e "s|{{DATE}}|2026-08-05|g" \
      -e "s|{{PLAN_PATH}}|$PLAN|g" \
      -e "s|{{SPEC_PATH}}|$SPEC|g" \
      -e "s|{{DESIGN_DOC}}|(없음 - 이 세션은 brainstorming 경로로 진행)|g" \
      -e "s|{{GLOBAL_CONSTRAINTS}}|(plan의 Global Constraints 참조)|g" \
      -e "s|{{OPEN_RISKS}}|없음|g" \
      "$TPL" > "$tmp"
  if grep -q '{{' "$tmp"; then
    note "치환 후에도 자리표시자 잔존: $(grep -o '{{[A-Z_]*}}' "$tmp" | sort -u | tr '\n' ' ')"
  else
    echo "ok   - handoff 템플릿 전 자리표시자 치환 가능"
  fi
  rm -f "$tmp"
else
  note "handoff 템플릿 없음: $TPL"
fi

# GATE 1: 실제 설계문서에 대고 돌린다.
# Stage 1-b는 설계문서를 <repo>/docs/superpowers/designs/ 아래에 남긴다.
# 픽스처도 함께 훑어 표본이 0건이 되는 것을 막는다 — 아직 파이프라인을 한 바퀴
# 돌지 않은 저장소에서는 designs/가 비어 있는 것이 정상이기 때문이다.
# 산출물마다 승인 여부가 달라 PASS/FAIL이 섞이는 것이 정상이다. 단언하는 것은:
#   - 종료코드가 0(통과) 또는 1(계약 위반)이며 2(사용법 오류)는 절대 아니다
#   - 최소 한 건은 통과한다 — 전부 거부되면 GATE1이 망가진 것이다
D1_DOCS=()
for d in "$HOME"/.claude/docs/superpowers/designs/*-grill.md \
         "$HOME/.claude/skills/auto-code/tests/fixtures"/gate1-*.md; do
  [ -f "$d" ] && D1_DOCS+=("$d")
done

if [ "${#D1_DOCS[@]}" -eq 0 ]; then
  note "GATE1 실물 표본 0건 — 픽스처조차 못 찾았다 (경로 오류 의심)"
else
  g1_pass=0
  g1_seen=0
  for d in "${D1_DOCS[@]}"; do
    bash "$GATE" 1 "$d" >/dev/null 2>&1
    rc=$?
    g1_seen=$((g1_seen + 1))
    case "$rc" in
      0) g1_pass=$((g1_pass + 1)) ;;
      1) ;;
      *) note "GATE1이 예상 밖 종료코드 $rc 반환 (사용법 오류 의심): $d" ;;
    esac
  done
  echo "ok   - GATE1 실물 ${g1_seen}건 검사, ${g1_pass}건 통과 / $((g1_seen - g1_pass))건 계약 위반으로 거부"
  [ "$g1_pass" -ge 1 ] || note "GATE1이 실제 설계문서를 하나도 통과시키지 못함 (${g1_seen}건 전부 거부)"
fi

if [ "$FAILED" -eq 0 ]; then
  echo "ok   - 실제 아티팩트 회귀 검증 통과"
else
  echo "failed: $FAILED"
fi
[ "$FAILED" -eq 0 ]

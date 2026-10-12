#!/usr/bin/env bash
# lint_review_output.sh — academic-reviewer 출력 회귀 린터 (v4 cycle, V4-A)
#
# v3 cycle에서 발견·수정한 3건 실패 모드를 captured 리뷰 출력에 대해 자동 검증한다:
#   1. JSON 블록 누출        (V3-C: ```json 삽입)
#   2. pass/fail verdict 누출 (V3-B: "Pass: false" / "Overall Score: N")
#   3. 임의 Issue ID          (V3-A: catalog 범위 밖 [Wn]/[Cn]/[Sn])
#
# 생성(generation)은 LLM이 담당하므로 end-to-end 자동화 불가 — 이 린터는
# academic-reviewer가 만든 출력을 파일로 캡처한 뒤 그 파일을 검사한다.
#
# 사용법:  lint_review_output.sh <reviewer_output.md>
# 종료코드: 0 = 통과 / 1 = 위반 발견 / 2 = 사용법 오류
set -u

file="${1:-}"
if [ -z "$file" ] || [ ! -f "$file" ]; then
  echo "usage: $0 <reviewer_output_file>" >&2
  exit 2
fi

fail=0

# --- Check 1: JSON 블록 누출 (V3-C) ---
if grep -qE '```[[:space:]]*json' "$file"; then
  echo "FAIL [json-block]: \`\`\`json 블록 발견 — 출력은 마크다운만 허용" >&2
  fail=1
fi

# --- Check 2: pass/fail verdict 누출 (V3-B) ---
if grep -qiE 'Pass[[:space:]]*:[[:space:]]*(true|false)' "$file"; then
  echo "FAIL [verdict]: 'Pass: true/false' verdict 발견 — 종료 판단은 orchestrator 책임" >&2
  fail=1
fi
if grep -qiE 'Overall[[:space:]]+Score[[:space:]]*:' "$file"; then
  echo "FAIL [verdict]: 'Overall Score:' 발견 — verdict 출력 금지" >&2
  fail=1
fi

# --- Check 3: 임의 Issue ID (V3-A) ---
# 허용 범위: C1-C9 / W1-W17 / S1-S3.
# PR1-5·SoP1-5·IS1-4는 multi-char prefix라 본 정규식이 잡지 않음(의도적 — false-positive 회피).
bad_ids=$(grep -oE '\[(C|W|S)[0-9]+\]' "$file" | tr -d '[]' | sort -u | awk '
  /^C/ { n = substr($0,2)+0; if (n < 1 || n > 9)  print }
  /^W/ { n = substr($0,2)+0; if (n < 1 || n > 17) print }
  /^S/ { n = substr($0,2)+0; if (n < 1 || n > 3)  print }
')
if [ -n "$bad_ids" ]; then
  echo "FAIL [arbitrary-id]: catalog 범위 밖 Issue ID 발견:" >&2
  echo "$bad_ids" | sed 's/^/  - /' >&2
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "PASS: $file — JSON 누출 없음 / verdict 없음 / 모든 C·W·S ID catalog 매칭"
fi
exit "$fail"

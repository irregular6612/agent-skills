#!/usr/bin/env bash
# paper-driller 정적 검증 하버스. 모든 체크 통과 시 exit 0.
set -u
ROOT="${CLAUDE_HOME:-$HOME/.claude}"
AGENTS="$ROOT/agents"
SKILL="$ROOT/skills/paper-driller/SKILL.md"
REF="$ROOT/skills/paper-driller/references/insight-digest-spec.md"
fail=0
pass(){ echo "PASS  $1"; }
bad(){ echo "FAIL  $1"; fail=1; }

# frontmatter 값 추출 (파일 상단 --- 블록의 key: value)
fm(){ awk -v k="$2" 'f&&/^---/{exit} /^---/{f=1;next} f&&$1==k":"{ $1="";sub(/^ /,"");print;exit}' "$1"; }

check_model(){ # file expected_model
  local m; m="$(fm "$1" model)"
  [ "$m" = "$2" ] && pass "model($2): $(basename "$1")" || bad "model expected '$2' got '$m': $(basename "$1")"
}
check_effort(){ # file expected_effort
  local e; e="$(fm "$1" effort)"
  [ "$e" = "$2" ] && pass "effort($2): $(basename "$1")" || bad "effort expected '$2' got '$e': $(basename "$1")"
}
check_no_effort(){ # file
  local e; e="$(fm "$1" effort)"
  [ -z "$e" ] && pass "no-effort(haiku): $(basename "$1")" || bad "effort should be absent got '$e': $(basename "$1")"
}
exists(){ [ -f "$1" ] && pass "exists: ${1#$ROOT/}" || bad "missing: ${1#$ROOT/}"; }
absent(){ [ ! -e "$1" ] && pass "absent: ${1#$ROOT/}" || bad "should be deleted: ${1#$ROOT/}"; }
grep_has(){ grep -q "$2" "$1" 2>/dev/null && pass "ref '$2' in $(basename "$1")" || bad "ref '$2' MISSING in $(basename "$1")"; }
grep_absent(){ grep -q "$2" "$1" 2>/dev/null && bad "stale ref '$2' in $(basename "$1")" || pass "no-stale '$2' in $(basename "$1")"; }

# --- 파일 존재/부재 ---
exists "$AGENTS/paper-spine.md"
exists "$AGENTS/paper-section-driller.md"
exists "$AGENTS/paper-digest-composer.md"
exists "$AGENTS/paper-meta.md"
exists "$AGENTS/paper-evidence.md"
exists "$AGENTS/paper-comparison.md"
exists "$REF"
absent "$AGENTS/paper-holistic-analyzer.md"

# --- 모델/effort ---
check_model "$AGENTS/paper-spine.md" opus;            check_effort "$AGENTS/paper-spine.md" max
check_model "$AGENTS/paper-digest-composer.md" opus;  check_effort "$AGENTS/paper-digest-composer.md" max
check_model "$AGENTS/paper-section-driller.md" sonnet; check_effort "$AGENTS/paper-section-driller.md" xhigh
check_model "$AGENTS/paper-evidence.md" sonnet;        check_effort "$AGENTS/paper-evidence.md" xhigh
check_model "$AGENTS/paper-comparison.md" sonnet;      check_effort "$AGENTS/paper-comparison.md" xhigh
check_model "$AGENTS/paper-meta.md" haiku;             check_no_effort "$AGENTS/paper-meta.md"

# --- SKILL.md 참조 일관성 ---
grep_has "$SKILL" "paper-spine"
grep_absent "$SKILL" "paper-holistic-analyzer"
grep_has "$SKILL" "insight-digest-spec"

# --- 공유 reference 참조 (composer + SKILL Bite 모드) ---
grep_has "$AGENTS/paper-digest-composer.md" "insight-digest-spec"

# --- smoke-fix 계약 체크 (2026-06-03) ---
SPINE="$AGENTS/paper-spine.md"
SECT="$AGENTS/paper-section-driller.md"
# F6: 헤더 stale 제거
grep_absent "$SKILL" "1개 arxiv 논문"
# F1: Phase A 비-arxiv 전문 경로 (PDF 캐시 Read + redirect)
grep_has "$SKILL" "캐시된 PDF"
grep_has "$SKILL" "redirect"
# F5: 출력 언어 전달
grep_has "$SKILL" "output_lang"
grep_has "$SPINE" "output_lang"
grep_has "$SECT" "output_lang"
# F3: profile 2축 (structure × scholarly)
grep_has "$SKILL" "structure"
grep_has "$SKILL" "scholarly"
grep_has "$SPINE" "structure:"
grep_has "$SPINE" "scholarly:"
# F4: free(일반) 출력 템플릿
grep_has "$SKILL" "free 프로파일 출력 템플릿"
# F7: vault root 해석
grep_has "$SKILL" "vault_root"

echo "----"
[ "$fail" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "SOME FAIL"; exit 1; }

#!/usr/bin/env bash
# paper-driller 정적 검증 하버스. 모든 체크 통과 시 exit 0.
set -u
# Plugin root (…/<plugin>/) in plugin layout, ~/.claude in the legacy layout.
# This script lives at <root>/skills/<skill>/scripts/, so climb three levels.
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
AGENTS="$ROOT/agents"
SKILL="$ROOT/skills/paper-driller/SKILL.md"
REF="$ROOT/skills/paper-driller/references/insight-digest-spec.md"
READABILITY_REF="$ROOT/skills/paper-driller/references/readability-spec.md"
PREREAD_REF="$ROOT/skills/paper-driller/references/preread-v2-spec.md"
SCHEMA_REF="$ROOT/skills/paper-driller/references/paper-schema.json"
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
grep_has(){ grep -q -- "$2" "$1" 2>/dev/null && pass "ref '$2' in $(basename "$1")" || bad "ref '$2' MISSING in $(basename "$1")"; }
grep_absent(){ grep -q -- "$2" "$1" 2>/dev/null && bad "stale ref '$2' in $(basename "$1")" || pass "no-stale '$2' in $(basename "$1")"; }

# --- 파일 존재/부재 ---
exists "$AGENTS/paper-preread-analyst.md"
exists "$AGENTS/paper-spine.md"
exists "$AGENTS/paper-section-driller.md"
exists "$AGENTS/paper-digest-composer.md"
exists "$AGENTS/paper-meta.md"
exists "$AGENTS/paper-evidence.md"
exists "$AGENTS/paper-comparison.md"
exists "$REF"
exists "$READABILITY_REF"
exists "$PREREAD_REF"
exists "$SCHEMA_REF"
absent "$AGENTS/paper-holistic-analyzer.md"

# --- 모델/effort ---
check_model "$AGENTS/paper-preread-analyst.md" sonnet; check_effort "$AGENTS/paper-preread-analyst.md" high
check_model "$AGENTS/paper-spine.md" opus;            check_effort "$AGENTS/paper-spine.md" max
check_model "$AGENTS/paper-digest-composer.md" opus;  check_effort "$AGENTS/paper-digest-composer.md" max
check_model "$AGENTS/paper-section-driller.md" sonnet; check_effort "$AGENTS/paper-section-driller.md" xhigh
check_model "$AGENTS/paper-evidence.md" sonnet;        check_effort "$AGENTS/paper-evidence.md" xhigh
check_model "$AGENTS/paper-comparison.md" sonnet;      check_effort "$AGENTS/paper-comparison.md" xhigh
check_model "$AGENTS/paper-meta.md" haiku;             check_no_effort "$AGENTS/paper-meta.md"

# --- SKILL.md 참조 일관성 ---
grep_has "$SKILL" "paper-preread-analyst"
grep_has "$SKILL" "기본 subagent 호출 예산: 1회"
grep_has "$SKILL" "author-stated | analyst-inference | unknown"
grep_has "$SKILL" "paper-spine"
grep_absent "$SKILL" "paper-holistic-analyzer"
grep_has "$SKILL" "insight-digest-spec"
grep_has "$SKILL" "readability-spec"

# --- 공유 reference 참조 ---
grep_has "$AGENTS/paper-digest-composer.md" "insight-digest-spec"
grep_has "$AGENTS/paper-digest-composer.md" "readability-spec"
grep_has "$AGENTS/paper-digest-composer.md" "preread-v2-spec"
grep_has "$AGENTS/paper-preread-analyst.md" "preread-v2-spec"
grep_has "$AGENTS/paper-preread-analyst.md" "<<<READING_DECISION>>>"
grep_has "$AGENTS/paper-preread-analyst.md" "claim_origin"
grep_has "$AGENTS/paper-section-driller.md" "readability-spec"

# --- 핵심 계약 체크 ---
SPINE="$AGENTS/paper-spine.md"
SECT="$AGENTS/paper-section-driller.md"
grep_absent "$SKILL" "1개 arxiv 논문"
grep_has "$SKILL" "캐시된 PDF"
grep_has "$SKILL" "redirect"
grep_has "$SKILL" "output_lang"
grep_has "$SPINE" "output_lang"
grep_has "$SECT" "output_lang"
grep_has "$SKILL" "structure"
grep_has "$SKILL" "scholarly"
grep_has "$SPINE" "structure:"
grep_has "$SPINE" "scholarly:"
grep_has "$SPINE" "profile:"
grep_has "$SPINE" "source_coverage:"
EVIDENCE="$AGENTS/paper-evidence.md"
grep_has "$EVIDENCE" 'mode`: `preread` | `deep`'
grep_has "$EVIDENCE" "source_location"
grep_has "$EVIDENCE" "최대 5개"
grep_has "$SKILL" "free 프로파일 출력 템플릿"
grep_has "$SKILL" "vault_root"
grep_has "$SKILL" "destination"
grep_has "$SKILL" "type: paper"
grep_has "$SKILL" "AI 전용"
grep_has "$SKILL" "--mode preread|deep"
grep_has "$SKILL" "기본값: preread"
grep_has "$SKILL" "source-coverage"
grep_has "$SKILL" "Wiki Integration"
grep_has "$SKILL" "paper-schema.json"
grep_has "$ROOT/hooks/paper-format-validator.py" "paper-schema.json"
grep_has "$AGENTS/paper-preread-analyst.md" "<<<ONE_MINUTE>>>"
grep_has "$AGENTS/paper-preread-analyst.md" "<<<READING_MAP>>>"
grep_has "$AGENTS/paper-preread-analyst.md" "기본 1회, retry/검증 포함 최대 2회"
grep_absent "$SKILL" "Benchmark·Evaluation"
grep_absent "$SKILL" "| Memory |"
grep_absent "$SKILL" "| Skill_LM |"
grep_absent "$SKILL" "| Meta-cognition |"
grep_absent "$SKILL" "Papers/\[Category\]/"

echo "----"
[ "$fail" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "SOME FAIL"; exit 1; }

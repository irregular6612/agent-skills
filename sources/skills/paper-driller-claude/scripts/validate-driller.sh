#!/usr/bin/env bash
# paper-driller 정적 검증 하네스. 모든 체크 통과 시 exit 0.
# v3(템플릿 선택·manifest 검증) 계약과 legacy v2 계약을 함께 확인한다.
set -u
ROOT="${CLAUDE_HOME:-$HOME/.claude}"
AGENTS="$ROOT/agents"
SKILLDIR="$ROOT/skills/paper-driller"
SKILL="$SKILLDIR/SKILL.md"
REFS="$SKILLDIR/references"
WORKFLOW="$REFS/workflow.md"
LEGACY="$REFS/legacy-workflow.md"
GENERAL="$REFS/templates/general-v1.md"
REF="$REFS/insight-digest-spec.md"
READABILITY_REF="$REFS/readability-spec.md"
PREREAD_REF="$REFS/preread-v2-spec.md"
SCHEMA_REF="$REFS/paper-schema.json"
VALIDATOR="$ROOT/hooks/paper-format-validator.py"
FM_HOOK="$ROOT/hooks/paper-frontmatter-hook.py"
FM_INSTALLER="$ROOT/hooks/install-paper-frontmatter-hooks.py"
VAULT="${PAPER_VAULT_ROOT:-~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes}"
ENGINE="$VAULT/Public/_tools/paper_frontmatter.py"
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

# --- 파일 존재/부재 (legacy agent는 보존, 신규 reference는 필수) ---
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
exists "$WORKFLOW"
exists "$LEGACY"
exists "$GENERAL"
exists "$VALIDATOR"
exists "$ROOT/skills/paper-digest/SKILL.md"
absent "$AGENTS/paper-holistic-analyzer.md"

# --- 모델/effort (legacy agent 계약 유지) ---
check_model "$AGENTS/paper-preread-analyst.md" sonnet; check_effort "$AGENTS/paper-preread-analyst.md" high
check_model "$AGENTS/paper-spine.md" opus;            check_effort "$AGENTS/paper-spine.md" max
check_model "$AGENTS/paper-digest-composer.md" opus;  check_effort "$AGENTS/paper-digest-composer.md" max
check_model "$AGENTS/paper-section-driller.md" sonnet; check_effort "$AGENTS/paper-section-driller.md" xhigh
check_model "$AGENTS/paper-evidence.md" sonnet;        check_effort "$AGENTS/paper-evidence.md" xhigh
check_model "$AGENTS/paper-comparison.md" sonnet;      check_effort "$AGENTS/paper-comparison.md" xhigh
check_model "$AGENTS/paper-meta.md" haiku;             check_no_effort "$AGENTS/paper-meta.md"

# --- SKILL.md (v3) ---
lines=$(wc -l < "$SKILL" | tr -d ' ')
[ "$lines" -le 150 ] && pass "SKILL.md length $lines <= 150" || bad "SKILL.md length $lines > 150"
grep_has "$SKILL" "Paper Driller v3"
grep_has "$SKILL" "--template"
grep_has "$SKILL" "auto"
grep_has "$SKILL" "general-v1"
grep_has "$SKILL" "paper-note-v3"
grep_has "$SKILL" "workflow.md"
grep_has "$SKILL" "legacy-workflow.md"
grep_has "$SKILL" "paper-schema.json"
grep_has "$SKILL" "paper-format-validator.py"
grep_has "$SKILL" "--check-template"
grep_has "$SKILL" "--manifest"
grep_has "$SKILL" "--mode preread|deep"
grep_has "$SKILL" "기본값: preread"
grep_has "$SKILL" "vault_root"
grep_has "$SKILL" "destination"
grep_has "$SKILL" "type: paper"
grep_has "$SKILL" "source-coverage"
grep_has "$SKILL" "visual-check"
grep_has "$SKILL" "visual-scope"
grep_has "$SKILL" "Wiki Integration"
grep_has "$SKILL" "author-stated | analyst-inference | unknown"
grep_has "$SKILL" "AUTO:body"
grep_has "$SKILL" "USER:notes"
grep_has "$SKILL" "paper-digest"
grep_has "$SKILL" "PDF 위치에서 저장 경로를 추측하지 않는다"
# frontmatter schema v4 (13 keys, DRILLER:meta body block, URL identity)
grep_has "$SKILL" "정확히 13개 키"
grep_has "$SKILL" "Read-Depth"
grep_has "$SKILL" "DRILLER:meta"
grep_has "$SKILL" "paper_frontmatter.py"
grep_has "$SKILL" "--meta"
grep_absent "$SKILL" "arXiv-ID\`/\`DOI\`/정규화"
grep_absent "$SKILL" "Public/AI/\` 아래에서만 필수"
grep_has "$SKILL" "readability-spec"
grep_has "$SKILL" "insight-digest-spec"
grep_absent "$SKILL" "paper-holistic-analyzer"
grep_absent "$SKILL" "--level"
grep_absent "$SKILL" "Benchmark·Evaluation"
grep_absent "$SKILL" "Papers/\[Category\]/"
grep_absent "$SKILL" "1개 arxiv 논문"
# Astra4 correction contract
grep_has "$SKILL" "--approved-switch"
grep_has "$SKILL" "not-seen"
grep_has "$SKILL" "확보한 범위에서 확인하지 못했다"
grep_has "$SKILL" "paper-deep-v2"
grep_has "$SKILL" "query는 그대로"
# integration correction 2026-09-22: PyYAML 있는 인터프리터, 검사 두 층 분리, 래퍼
grep_has "$SKILL" "paper-frontmatter-venv"
grep_has "$SKILL" "paper_frontmatter.sh"
grep_absent "$SKILL" 'python3 ~/.claude/hooks/paper-format-validator.py'
grep_absent "$SKILL" 'python3 "$VAULT/Public/_tools/paper_frontmatter.py"'

# --- workflow.md ---
grep_has "$WORKFLOW" "manifest_version"
grep_has "$WORKFLOW" "doc_id"
grep_has "$WORKFLOW" "main_body"
grep_has "$WORKFLOW" "not-seen"
grep_has "$WORKFLOW" "user-narrowed"
grep_has "$WORKFLOW" "controlled_update_fields"
grep_has "$WORKFLOW" "--previous"
grep_has "$WORKFLOW" "--check-template"
grep_has "$WORKFLOW" "캐시된 PDF"
grep_has "$WORKFLOW" "redirect"
grep_has "$WORKFLOW" "output_lang"
grep_has "$WORKFLOW" "build_catalog.py"
grep_has "$WORKFLOW" "paper-understand"
grep_has "$WORKFLOW" "claude -p"
grep_has "$WORKFLOW" "--approved-switch"
grep_has "$WORKFLOW" "TMPDIR"
grep_absent "$WORKFLOW" "/tmp/paper-driller/"
grep_has "$WORKFLOW" "거절을 \`general-v1\` 선택으로 해석하지 않는다"
grep_has "$WORKFLOW" "경로 대소문자와 query는 그대로 둔다"
grep_has "$WORKFLOW" "template-id\`는 필수"
grep_has "$WORKFLOW" "BEGIN DRILLER:meta"
grep_has "$WORKFLOW" "Read-Depth:"
grep_has "$WORKFLOW" "paper_frontmatter.py"
grep_has "$WORKFLOW" "derive_doc_ids"
grep_absent "$WORKFLOW" 'arXiv-ID: "N/A"'
grep_absent "$WORKFLOW" "Evidence-Quality: "
grep_absent "$WORKFLOW" "isTargetPaper: "
grep_has "$WORKFLOW" "paper-frontmatter-venv"
grep_has "$WORKFLOW" "paper_frontmatter.sh"
grep_absent "$WORKFLOW" 'python3 ~/.claude/hooks/paper-format-validator.py'
grep_absent "$WORKFLOW" 'python3 "$VAULT/Public/_tools/paper_frontmatter.py"'

# --- general-v1 템플릿 ---
grep_has "$GENERAL" '"id": "general-v1"'
grep_has "$GENERAL" '"visual_section": "본문 도표"'
grep_has "$GENERAL" "paper-digest"
grep_has "$GENERAL" "### Figure 3"
grep_has "$GENERAL" "해당 없음"
grep_has "$GENERAL" "viewed | caption-only | not-seen"
grep_has "$GENERAL" "범위 한계는 한 번만 밝힌다"
grep_has "$GENERAL" "인과관계"
grep_has "$GENERAL" "도표 목록 미확인"
if python3 "$VALIDATOR" --check-template "$GENERAL" >/dev/null 2>&1; then pass "validator --check-template general-v1"; else bad "validator --check-template general-v1"; fi
# 템플릿 디렉터리 안의 모든 템플릿이 정적 검사를 통과해야 한다
for t in "$REFS"/templates/*.md; do
  [ -e "$t" ] || continue
  if python3 "$VALIDATOR" --check-template "$t" >/dev/null 2>&1; then pass "template ok: $(basename "$t")"; else bad "template INVALID: $(basename "$t")"; fi
done

# --- schema / validator ---
if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$SCHEMA_REF" 2>/dev/null; then pass "schema JSON parses"; else bad "schema JSON invalid"; fi
grep_has "$SCHEMA_REF" '"paper-note-v3"'
grep_has "$SCHEMA_REF" '"controlled_update_fields"'
grep_has "$SCHEMA_REF" '"visual_check"'
grep_has "$SCHEMA_REF" '"manifest"'
grep_has "$SCHEMA_REF" '"audience_level": "intro"'
grep_has "$SCHEMA_REF" '"comment_max_chars": 80'
grep_has "$SCHEMA_REF" '"paper-deep-v2"'
grep_has "$SCHEMA_REF" '"deep_extra_h2"'
grep_has "$SCHEMA_REF" '"url_normalisation"'
grep_has "$SCHEMA_REF" '"schema_version": 4'
grep_has "$SCHEMA_REF" '"Read-Depth"'
grep_has "$SCHEMA_REF" '"driller_meta"'
grep_has "$SCHEMA_REF" '"identity"'
grep_absent "$SCHEMA_REF" '"ai_only"'
grep_absent "$SCHEMA_REF" '"arXiv-ID"'
if python3 - "$SCHEMA_REF" <<'PY' 2>/dev/null
import json,sys
s=json.load(open(sys.argv[1]))
keys=s["frontmatter"]["keys"]
exp=["type","Reading-Status","Read-Depth","Author","Journal/Conference","Published Year","Topic","Review-Date","Comment","URL","Category","linked-bases","Lab"]
sys.exit(0 if keys==exp else 1)
PY
then pass "schema frontmatter.keys == 13 canonical keys"; else bad "schema frontmatter.keys != 13 canonical keys"; fi
if [ -f "$ENGINE" ]; then
  pass "engine exists: Public/_tools/paper_frontmatter.py"
  if grep -q '"Read-Depth",' "$ENGINE" && grep -q '"Lab",' "$ENGINE"; then pass "engine PAPER_KEYS has Read-Depth/Lab"; else bad "engine PAPER_KEYS missing Read-Depth/Lab"; fi
else
  bad "engine missing: $ENGINE (set PAPER_VAULT_ROOT)"
fi
exists "$FM_HOOK"
exists "$FM_INSTALLER"
exists "$ROOT/hooks/paper-frontmatter-hook.sh"
[ -f "$VAULT/Public/_tools/paper_frontmatter.sh" ] && pass "exists: vault Public/_tools/paper_frontmatter.sh" || bad "missing: vault Public/_tools/paper_frontmatter.sh"
grep_has "$FM_HOOK" "stop_hook_active"
grep_has "$FM_HOOK" "MultiEdit"
grep_has "$VALIDATOR" "def derive_doc_ids"
grep_has "$VALIDATOR" "DRILLER:meta"
grep_has "$VALIDATOR" "def load_engine"
grep_absent "$VALIDATOR" "for anc in \[p, \*p.parents\]"   # 대상 노트 상위 디렉터리에서 엔진을 찾지 않는다
grep_has "$VALIDATOR" "def _vault_root"
grep_has "$VALIDATOR" "--meta"
grep_absent "$VALIDATOR" "SCOPE_GLOBS"
grep_absent "$VALIDATOR" "is_ai_domain"
grep_has "$VALIDATOR" "--approved-switch"
grep_has "$VALIDATOR" "def raw_frontmatter_segments"
grep_has "$VALIDATOR" "def find_auto_markers"
grep_has "$VALIDATOR" "urlsplit"
grep_has "$VALIDATOR" "paper-schema.json"
grep_has "$VALIDATOR" "--check-template"
grep_has "$VALIDATOR" "--manifest"
grep_has "$VALIDATOR" "--previous"
grep_has "$VALIDATOR" "def expected_visual_check"
if python3 -m py_compile "$VALIDATOR" 2>/dev/null; then pass "validator compiles"; else bad "validator does not compile"; fi

# --- legacy 계약 (legacy-workflow.md로 이동, 내용 보존) ---
grep_has "$LEGACY" "paper-preread-analyst"
grep_has "$LEGACY" "기본 subagent 호출 예산: 1회"
grep_has "$LEGACY" "paper-spine"
grep_has "$LEGACY" "free 프로파일 출력 템플릿"
grep_has "$LEGACY" "Phase D' — Humanize"
grep_has "$LEGACY" "paper-driller-qc.jsonl"
grep_has "$LEGACY" "audience-level: intro"
grep_has "$LEGACY" "AI 전용"
grep_absent "$LEGACY" "paper-holistic-analyzer"
grep_has "$LEGACY" "paper-deep-v2"

# --- 공유 legacy reference 참조 (agent 파일은 변경하지 않음) ---
grep_has "$AGENTS/paper-digest-composer.md" "insight-digest-spec"
grep_has "$AGENTS/paper-digest-composer.md" "readability-spec"
grep_has "$AGENTS/paper-digest-composer.md" "preread-v2-spec"
grep_has "$AGENTS/paper-preread-analyst.md" "preread-v2-spec"
grep_has "$AGENTS/paper-preread-analyst.md" "<<<READING_DECISION>>>"
grep_has "$AGENTS/paper-preread-analyst.md" "claim_origin"
grep_has "$AGENTS/paper-section-driller.md" "readability-spec"
grep_has "$AGENTS/paper-spine.md" "output_lang"
grep_has "$AGENTS/paper-section-driller.md" "output_lang"
grep_has "$AGENTS/paper-spine.md" "structure:"
grep_has "$AGENTS/paper-spine.md" "scholarly:"
grep_has "$AGENTS/paper-spine.md" "profile:"
grep_has "$AGENTS/paper-spine.md" "source_coverage:"
EVIDENCE="$AGENTS/paper-evidence.md"
grep_has "$EVIDENCE" 'mode`: `deep`'
grep_absent "$EVIDENCE" "# Mode: preread"
grep_has "$EVIDENCE" "출력 1 — claim ledger"
grep_has "$EVIDENCE" "source_location"
grep_has "$EVIDENCE" "최대 5개"
grep_has "$AGENTS/paper-preread-analyst.md" "<<<ONE_MINUTE>>>"
grep_has "$AGENTS/paper-preread-analyst.md" "<<<READING_MAP>>>"
grep_has "$AGENTS/paper-preread-analyst.md" "기본 1회, retry/검증 포함 최대 2회"
grep_has "$AGENTS/paper-preread-analyst.md" "## 독자 (고정)"
grep_has "$AGENTS/paper-preread-analyst.md" "비유 1개"
grep_has "$AGENTS/paper-preread-analyst.md" "audience_level"
grep_has "$AGENTS/paper-preread-analyst.md" "코드·데이터 공개 여부"
grep_has "$READABILITY_REF" "15어절"
grep_has "$READABILITY_REF" "독자 (고정)"
grep_has "$PREREAD_REF" "완전 서술 자리"
grep_has "$PREREAD_REF" "## Audience (고정)"
grep_has "$PREREAD_REF" "빠뜨리면 안 되는 두 줄"
COMPOSER="$AGENTS/paper-digest-composer.md"
grep_absent "$COMPOSER" "# Mode: preread"
grep_absent "$COMPOSER" "TERMS 최대 7개"
grep_absent "$COMPOSER" "3–6행"
grep_has "$COMPOSER" "## 어디까지 믿을까"
grep_has "$COMPOSER" "<<<READING_DECISION>>>"
grep_has "$COMPOSER" "claim_origin"

echo "----"
[ "$fail" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "SOME FAIL"; exit 1; }

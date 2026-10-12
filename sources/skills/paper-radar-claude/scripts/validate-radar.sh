#!/usr/bin/env bash
# paper-radar 정적 계약 검증. 모든 체크 통과 시 exit 0.
# 사용: bash ~/.claude/skills/paper-radar/scripts/validate-radar.sh
set -u
ROOT="${CLAUDE_HOME:-$HOME/.claude}"
SKILL_DIR="$ROOT/skills/paper-radar"
SKILL="$SKILL_DIR/SKILL.md"
fail=0
pass(){ echo "PASS  $1"; }
bad(){ echo "FAIL  $1"; fail=1; }
exists(){ [ -f "$1" ] && pass "exists: ${1#$ROOT/}" || bad "missing: ${1#$ROOT/}"; }
grep_has(){ grep -q -- "$2" "$1" 2>/dev/null && pass "contains '$2': $(basename "$1")" || bad "MISSING '$2': $(basename "$1")"; }

echo "== paper-radar =="

# --- 필수 파일 ---
exists "$SKILL"
exists "$SKILL_DIR/references/ranking-rubric.md"
exists "$SKILL_DIR/references/daily-radar-template.md"
exists "$SKILL_DIR/references/interest-profile-template.yaml"
exists "$SKILL_DIR/references/handoff-schema.yaml"
exists "$SKILL_DIR/scripts/validate-radar.sh"

# --- frontmatter: byte 0에서 시작 + YAML 파싱 + name == 디렉터리명 ---
if [ -f "$SKILL" ]; then
  if [ "$(head -c 3 "$SKILL")" = "---" ]; then pass "frontmatter starts at byte 0"; else bad "frontmatter must start at byte 0"; fi
  python3 - "$SKILL" <<'PY'
import sys, pathlib
try:
    import yaml
except ImportError:
    print("SKIP  pyyaml not installed — frontmatter parsed structurally only"); sys.exit(0)
p = pathlib.Path(sys.argv[1]); txt = p.read_text(encoding="utf-8")
if not txt.startswith("---\n"):
    print("FAIL  no leading frontmatter delimiter"); sys.exit(1)
end = txt.find("\n---", 3)
if end == -1:
    print("FAIL  unterminated frontmatter"); sys.exit(1)
try:
    fm = yaml.safe_load(txt[4:end])
except Exception as e:
    print(f"FAIL  YAML parse error: {e}"); sys.exit(1)
ok = True
if not isinstance(fm, dict):
    print("FAIL  frontmatter is not a mapping"); sys.exit(1)
if fm.get("name") != p.parent.name:
    print(f"FAIL  name '{fm.get('name')}' != dir '{p.parent.name}'"); ok = False
else:
    print(f"PASS  name matches dir: {fm['name']}")
for k in ("description", "user-invocable", "allowed-tools"):
    if k in fm: print(f"PASS  frontmatter key: {k}")
    else: print(f"FAIL  frontmatter key missing: {k}"); ok = False
if fm.get("user-invocable") is not True:
    print("FAIL  user-invocable must be true"); ok = False
if not isinstance(fm.get("allowed-tools"), list) or not fm["allowed-tools"]:
    print("FAIL  allowed-tools must be a non-empty list"); ok = False
else:
    print(f"PASS  allowed-tools: {len(fm['allowed-tools'])} entries")
sys.exit(0 if ok else 1)
PY
  [ $? -eq 0 ] || fail=1
fi

# --- 내부 상대 참조 대상 실재 확인 ---
python3 - "$SKILL_DIR" <<'PY'
import re, sys, pathlib
root = pathlib.Path(sys.argv[1])
pat = re.compile(r'(?:references|scripts)/[A-Za-z0-9_-]+(?:\.[A-Za-z0-9]+)?')
missing = []; checked = 0
for f in sorted(root.rglob("*")):
    if f.is_file() and f.suffix in (".md", ".yaml", ".yml", ".sh"):
        for m in set(pat.findall(f.read_text(encoding="utf-8", errors="replace"))):
            checked += 1
            if not (root / m).is_file():
                missing.append(f"{f.relative_to(root)} -> {m}")
for m in missing:
    print(f"FAIL  dangling relative ref: {m}")
print(f"{'FAIL' if missing else 'PASS'}  relative refs resolved ({checked - len(missing)}/{checked})")
sys.exit(1 if missing else 0)
PY
[ $? -eq 0 ] || fail=1

# --- 핵심 계약 문구 ---
grep_has "$SKILL" "paper-driller"
grep_has "$SKILL" "paper-understand"
grep_has "$SKILL" "canonical paper 노트를 만들지 않는다"
grep_has "$SKILL" "PAPER_RADAR_VAULT"
grep_has "$SKILL" "_wiki/radar/config.yaml"
grep_has "$SKILL" "_wiki/radar/state.json"
grep_has "$SKILL" "_wiki/radar/feedback.yaml"
grep_has "$SKILL" "_wiki/radar/daily/YYYY-MM-DD.md"
grep_has "$SKILL" "_wiki/radar/weekly/YYYY-Www.md"
grep_has "$SKILL" "radar_id"
grep_has "$SKILL" "frontier"
grep_has "$SKILL" "curriculum"
grep_has "$SKILL" "graph"
grep_has "$SKILL" "abstract-only는 abstract-only다"
grep_has "$SKILL" "exploratory"
grep_has "$SKILL" "unverified"
grep_has "$SKILL" "완료 기준"
grep_has "$SKILL" "J-Lens"
grep_has "$SKILL" "mapping_depth"
grep_has "$SKILL" "SCHEMA.md"

# --- rubric 8축 ---
RUB="$SKILL_DIR/references/ranking-rubric.md"
for axis in "interest fit" "pedagogical value" "novelty vs Wiki" "evidence quality" "bridge value" "availability" "freshness" "risk / overclaim"; do
  grep_has "$RUB" "$axis"
done
grep_has "$RUB" "freshness 지배 방지"

# --- 프로파일 6트랙 ---
PROF="$SKILL_DIR/references/interest-profile-template.yaml"
for t in transformer-mech alt-theory brain-analogy alt-arch mech-interp lab-watch; do
  grep_has "$PROF" "id: $t"
done
grep_has "$PROF" "unresolved_seeds"
grep_has "$PROF" "exploratory_slot_required: true"

# --- handoff 계약 ---
HO="$SKILL_DIR/references/handoff-schema.yaml"
for f in radar_id source_url vault_root candidate_rationale selected_action arxiv_id doi; do
  grep_has "$HO" "$f"
done
grep_has "$HO" "--mode preread"
grep_has "$HO" "/paper-understand"

echo "----"
[ "$fail" -eq 0 ] && { echo "paper-radar: ALL PASS"; exit 0; } || { echo "paper-radar: SOME FAIL"; exit 1; }

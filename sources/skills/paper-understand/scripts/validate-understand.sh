#!/usr/bin/env bash
# paper-understand 정적 계약 검증. 모든 체크 통과 시 exit 0.
# 사용: bash <스킬 폴더>/scripts/validate-understand.sh  (Claude Code ~/.claude/skills/paper-understand, Codex ~/.codex/skills/paper-understand)
set -u
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # this script lives in <skill>/scripts
ROOT="$(dirname "$(dirname "$SKILL_DIR")")"
SKILL="$SKILL_DIR/SKILL.md"
fail=0
pass(){ echo "PASS  $1"; }
bad(){ echo "FAIL  $1"; fail=1; }
exists(){ [ -f "$1" ] && pass "exists: ${1#$ROOT/}" || bad "missing: ${1#$ROOT/}"; }
grep_has(){ grep -q -- "$2" "$1" 2>/dev/null && pass "contains '$2': $(basename "$1")" || bad "MISSING '$2': $(basename "$1")"; }

echo "== paper-understand =="

# --- 필수 파일 ---
exists "$SKILL"
exists "$SKILL_DIR/references/teaching-protocol.md"
exists "$SKILL_DIR/references/session-state-schema.yaml"
exists "$SKILL_DIR/references/session-note-template.md"
exists "$SKILL_DIR/references/source-grounding-rules.md"
exists "$SKILL_DIR/scripts/validate-understand.sh"

# --- frontmatter: byte 0 시작 + YAML 파싱 + name == 디렉터리명 ---
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

# --- 상호작용 계약 ---
grep_has "$SKILL" "주요 질문을 정확히 1개만"
grep_has "$SKILL" "사용자의 답을 대신 지어내지 않는다"
grep_has "$SKILL" "claude -p"
grep_has "$SKILL" "가상의 사용자 답변"

# --- mastery 6상태 ---
for s in unseen recognized explained discriminated applied retained; do
  grep_has "$SKILL" "$s"
done
grep_has "$SKILL" "한 번 맞혔다고"

# --- 모드 ---
for m in quick standard deep; do grep_has "$SKILL" "\`$m\`"; done
grep_has "$SKILL" "기본값"

# --- phase 1..8 완료 기준 ---
for p in "Phase 1" "Phase 2" "Phase 3" "Phase 4" "Phase 5" "Phase 6" "Phase 7" "Phase 8"; do
  grep_has "$SKILL" "$p"
done
n_criteria=$(grep -c "완료 기준" "$SKILL")
[ "$n_criteria" -ge 8 ] && pass "완료 기준 blocks: $n_criteria (>=8)" || bad "완료 기준 blocks: $n_criteria (<8)"

# --- 저장 경로 ---
grep_has "$SKILL" "_wiki/study/learner-profile.md"
grep_has "$SKILL" "_wiki/study/papers/{paper-slug}/state.yaml"
grep_has "$SKILL" "_wiki/study/papers/{paper-slug}/sessions/YYYY-MM-DD.md"
grep_has "$SKILL" "전체 대화록을 덤프하지 않는다"
grep_has "$SKILL" "Reading-Status"

# --- 소스 근거 ---
grep_has "$SKILL" "source-coverage"
grep_has "$SKILL" "abstract-only"
grep_has "$SKILL" "위치 미확인"
grep_has "$SKILL" "튜터 해석"
grep_has "$SKILL" "논문 주장"
grep_has "$SKILL" "열린 질문"

# --- 세션 종료 3상태 ---
for st in paused completed-for-mode blocked-by-source; do grep_has "$SKILL" "$st"; done
grep_has "$SKILL" "마지막 phase에 도달한 것은 완료가 아니다"

# --- 이어하기 ---
grep_has "$SKILL" "last_question"
grep_has "$SKILL" "next_step"
grep_has "$SKILL" "초록부터 다시 시작하지 않는다"

# --- 라우팅 경계 ---
grep_has "$SKILL" "paper-radar"
grep_has "$SKILL" "paper-driller"
grep_has "$SKILL" "--mode preread"

# --- 참조 파일 계약 ---
TP="$SKILL_DIR/references/teaching-protocol.md"
grep_has "$TP" "한 턴 = 주요 질문 1개"
grep_has "$TP" "2회 실패"
grep_has "$TP" "teach-back"
for j in "정확" "불완전" "오개념" "근거 없음"; do grep_has "$TP" "$j"; done

SS="$SKILL_DIR/references/session-state-schema.yaml"
for f in paper session objectives mastery misconceptions open_questions review_prompts; do
  grep_has "$SS" "^$f:"
done
grep_has "$SS" "last_question"
grep_has "$SS" "source_coverage"

NOTE_T="$SKILL_DIR/references/session-note-template.md"
SG="$SKILL_DIR/references/source-grounding-rules.md"
grep_has "$SG" "위치 미확인"
grep_has "$SG" "blocked-by-source"
grep_has "$SG" "지어내지 않기"

# --- NotebookLM 통합: 필수 파일 ---
NB="$SKILL_DIR/references/notebooklm-integration.md"
exists "$NB"

# --- NotebookLM: 노트 + 원문 이중 소스 규칙 ---
grep_has "$SKILL" "노트 + 원문 이중 소스"
grep_has "$SKILL" "Canonical preread"
grep_has "$SKILL" "Original paper"
grep_has "$NB" "초록 페이지는 원문이 아니다"
grep_has "$NB" "near-match"

# --- NotebookLM: 모드 기본값과 오버라이드 ---
grep_has "$SKILL" "notebooklm_mode: auto"
grep_has "$SKILL" "--notebooklm on|off|auto"
grep_has "$NB" "notebooklm_mode: auto"

# --- NotebookLM: 인증 네트워크 테스트 ---
grep_has "$SKILL" "auth check --test --json"
grep_has "$SKILL" "token_fetch"
grep_has "$NB" "auth check --test --json"
grep_has "$NB" "token_fetch"
grep_has "$NB" "notebooklm login"

# --- NotebookLM: 권위 순서 ---
grep_has "$SKILL" "소스 권위 순서"
grep_has "$NB" "소스 권위 순서"
grep_has "$SG" "소스 권위 순서"
grep_has "$SG" "NotebookLM 합성"
grep_has "$SKILL" "NotebookLM 합성"
grep_has "$NB" "환각 없음"
grep_has "$SG" "환각 없음"

# --- NotebookLM: 비공식/문서화되지 않은 API 경고 ---
grep_has "$SKILL" "비공식"
grep_has "$SKILL" "undocumented"
grep_has "$NB" "비공식"
grep_has "$NB" "undocumented"
grep_has "$NB" "notebooklm-py-unofficial"
grep_has "$NB" "storage_state.json"

# --- NotebookLM: 로컬 폴백 (하드 의존성 아님) ---
grep_has "$SKILL" "로컬 폴백"
grep_has "$NB" "로컬 폴백"
grep_has "$NB" "rate limit"

# --- NotebookLM: dedup 식별자·다이제스트 ---
grep_has "$SKILL" "canonical_key"
grep_has "$SKILL" "preread_sha256"
grep_has "$NB" "canonical_key"
grep_has "$NB" "preread_sha256"
grep_has "$NB" "original_sha256_or_url"

# --- NotebookLM: 비공개 상태 업로드 금지 ---
grep_has "$SKILL" "업로드 금지"
grep_has "$NB" "업로드 금지"
grep_has "$NB" "learner-profile.md"
grep_has "$NB" "state.yaml"
grep_has "$NOTE_T" "업로드 대상이 아니다"

# --- NotebookLM: state 스키마 블록과 상태값 ---
grep_has "$SS" "^notebooklm:"
for k in mode backend client_version auth_verified_at notebook_id notebook_title \
         canonical_key preread_source_id preread_sha256 original_source_id \
         original_sha256_or_url source_sync_status last_synced_at last_query_at \
         conversation_id last_error; do
  grep_has "$SS" "  $k:"
done
for st in complete preread-only pending failed disabled; do
  grep_has "$SS" "$st"
done
grep_has "$SS" "notebooklm-py-unofficial"
grep_has "$SS" "쿠키·토큰"

# --- NotebookLM: pinned 0.8.0rc1 CLI 명령 계약이 문서에 있는가 ---
grep_has "$NB" "notebooklm create"
grep_has "$NB" "notebooklm source add"
grep_has "$NB" "notebooklm source wait"
grep_has "$NB" "notebooklm source list"
grep_has "$NB" "notebooklm source fulltext"
grep_has "$NB" "notebooklm ask"
grep_has "$NB" "--prompt-file"
grep_has "$NB" "0.8.0rc1"
grep_has "$NB" "7d0aa42c"
grep_has "$SKILL" "0.8.0rc1"
grep_has "$SKILL" "7d0aa42c"

# 설치되지 않은 MCP 경로를 문서화하지 않았는가
if grep -qiE 'notebooklm[[:space:]]+mcp' "$SKILL" "$NB" 2>/dev/null; then
  bad "documents a notebooklm MCP that is not installed"
else
  pass "no unsupported notebooklm MCP path documented"
fi

# --- 읽기 전용 CLI 계약 확인 (인증 불필요, 부재 시 SKIP) ---
NBCLI="$(PATH="$HOME/.local/bin:$PATH" command -v notebooklm 2>/dev/null)"
if [ -z "$NBCLI" ]; then
  echo "SKIP  notebooklm CLI not on PATH — runtime contract checks skipped (skill degrades to local fallback)"
else
  nbver="$(PATH="$HOME/.local/bin:$PATH" notebooklm --version 2>&1 | head -1)"
  case "$nbver" in
    *0.8.0rc1*7d0aa42c*) pass "CLI version matches pinned 0.8.0rc1 commit: $nbver" ;;
    *)       echo "WARN  CLI version drift (docs pin 0.8.0rc1/7d0aa42c): $nbver" ;;
  esac
  nbhelp(){ # nbhelp "<subcommand words>" "<expected token>"
    out="$(PATH="$HOME/.local/bin:$PATH" notebooklm $1 --help 2>&1)"
    case "$out" in
      *"$2"*) pass "CLI contract: 'notebooklm $1' supports $2" ;;
      *)      bad "CLI contract: 'notebooklm $1' missing $2" ;;
    esac
  }
  nbhelp "auth check" "--test"
  nbhelp "create" "--json"
  nbhelp "source add" "--type"
  nbhelp "source wait" "--timeout"
  nbhelp "source fulltext" "--json"
  nbhelp "ask" "--prompt-file"
  # 인증 없음은 정상 상태다. 검증을 실패시키지 않는다.
  auth_json="$(PATH="$HOME/.local/bin:$PATH" notebooklm auth check --json 2>&1)"
  case "$auth_json" in
    *'"status": "ok"'*) pass "auth present (not required for this validator)" ;;
    *)                  pass "auth absent/unverified — expected, validator does not require it" ;;
  esac
fi

echo "----"
[ "$fail" -eq 0 ] && { echo "paper-understand: ALL PASS"; exit 0; } || { echo "paper-understand: SOME FAIL"; exit 1; }

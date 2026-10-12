---
name: paper-driller
description: >-
  논문 1편을 원문 옆에 띄워 놓고 읽기 위한 근거 추적 노트를 만든다. 사용자가 고른 템플릿(기본 general-v1: paper-digest 개요 + 배경 + 지표 + 방법 + 결과 + take-home + 본문 도표 전부)로 쓴다. TRIGGERS: 논문 요약, paper drill, arxiv 정리, 논문 노트, 논문 읽기 전 요약, deep paper analysis
allowed-tools:
  - WebFetch
  - WebSearch
  - Read
  - Write
  - Edit
  - Bash
  - Agent
---

## Runtime binding (shared source)

`SKILL_ROOT` is the absolute directory containing this discovered `SKILL.md`. Resolve the installed item symlink before running commands. Supporting paths are relative to that directory; never infer the other harness HOME.

Role names in this document describe workflows. Claude uses its registered Markdown agents/Agent tool; Codex uses its registered native TOML roles and supported subagent interface. Do not execute Claude API snippets or pass `haiku`/`sonnet`/`opus` model aliases to Codex. Follow the active surface permission rules; if separate review cannot run, report that limitation, never pretend it ran. AskUserQuestion means the active harness user-input interface, not a required literal API name.

## 원문 수집 도구 (양 harness 공통)

먼저 활성 세션의 실제 도구 목록과 권한을 확인한다. Claude는 `WebFetch`/`WebSearch`와 로컬 PDF의 `Read(pages=…)`를 사용한다. Codex는 실제 제공되는 웹·PDF 도구를 사용하며, `hermes-tools`의 `web_search`/`web_extract`도 노출된 경우에만 사용한다. Claude 이름을 Codex 호출 이름으로 가정하지 않는다.

웹/PDF 수집이 기본 경로다. Claude의 `mcpsemanticscholar`·`paper-search-mcp-openai-v2`는 실제 도구가 제공되고 인증·권한이 확인된 경우에만 메타데이터·초록·검색을 보완한다. Codex에서 이 서버들을 필수로 요구하거나 자동 등록하지 않는다. 웹 도구가 없으면 사용자가 제공한 PDF·텍스트만 읽고 한계를 밝힌다. 검색 결과·초록·웹 요약은 전문이 아니다.


# Paper Driller v3

## 무엇을 만드나

논문 원문(PDF)을 옆에 띄워 놓고 함께 읽는 **동반 노트**를 만든다. 논문을 대신하는 글이 아니라, 원문의 어디에 무엇이 있는지 짚어 주는 글이다. 독자는 이 분야를 처음 보는 고등학생이라고 생각하고 쉽게 쓰되, 숫자·조건·가정은 원문 그대로 정확하게 남긴다.

노트의 절 구성은 **템플릿**이 정한다. 템플릿은 `references/templates/{id}.md` 파일 하나다. 첫 템플릿은 `general-v1`(일반 7부)이다. 자세한 절차는 `references/workflow.md`, 기계 스키마는 `references/paper-schema.json`이 단일 원천이다.

## 호출

```text
/paper-driller <arXiv-ID | DOI | URL | 제목> [--template <id>|auto] [--mode preread|deep] [--profile ...] [--humanize]
```

- `--template <id>`: 그 템플릿을 쓴다. 다시 묻지 않는다.
- `--template auto` (또는 `--auto`, "auto로 해줘"): **반드시 `general-v1`**. 전문 템플릿을 대신 골라 주는 옵션이 아니다.
- `--mode preread|deep` (기본값: preread): `deep`은 고른 템플릿을 다 채운 뒤 `## 상세 독해 노트`를 더 붙인다(비어 있으면 검증 실패). 템플릿 질문이나 도표 설명을 건너뛰는 뜻이 아니다. `--mode preread`만 있는 호출(radar `드릴` 포함)도 템플릿은 묻는다.
- `--humanize`: 저장 직전 서술 문단만 `humanize` 스킬로 다듬는다. 개요·표·수치·frontmatter는 넘기지 않는다.

## 순서

1. **중복 확인.** 원문 식별자는 frontmatter의 `URL` 하나다. `URL`에서 유도한 arXiv id(버전 제거)·DOI·정규화 URL이 같은 노트가 있으면 새로 만들지 않고 `update-existing`으로 간다. URL은 스킴·호스트 대소문자·`www.`·`#` 조각·끝 슬래시만 무시하고, 경로 대소문자와 query는 그대로 비교한다(`forum?id=A`와 `forum?id=B`는 다른 논문). 기존 템플릿을 유지하고 `AUTO:body` 안만 다시 쓴다. 사용자 필드·`USER:` 블록·H1 제목·마커 밖 내용은 글자 하나 바꾸지 않는다(YAML 들여쓰기·따옴표 포함). 사용자가 템플릿 전환을 명시적으로 승인한 경우에만 검증에 `--approved-switch`를 붙인다. 이 플래그는 이미 받은 동의의 기록이지 동의의 증거가 아니다.
2. **템플릿 선택.** 새 논문이면 `references/templates/`의 목록을 이름·용도와 함께 보여 주고 **사용자가 고를 때까지 기다린다.** 하나뿐이어도 묻는다. 논문 성격상 새 전문 구조가 낫다고 보면 절 제목 목록과 저장할 id를 제안하고 **"만들어서 저장해도 됩니까?"** 동의를 받은 뒤에만 파일을 만든다. 동의하지 않으면 파일을 만들지 않는다. 이미 고른 템플릿이 있으면 그것으로 진행하고, 아직 고른 것이 없으면 목록을 다시 보여 주고 선택을 기다린다. 명시적 `auto`는 전문 템플릿 제안으로 멈추지 않고 `general-v1`로 바로 간다. 비대화형이면 "템플릿 선택 필요"를 출력하고 파일을 만들지 않는다.
3. **원문 수집.** 위 도구 규칙에 따라 arXiv HTML/PDF 또는 출판사 원문을 웹으로 확보하고, URL을 모르면 제목으로 검색한다. 로컬 PDF는 실제 PDF 읽기 도구로 끝까지 읽는다. Claude의 등록된 논문 MCP는 조건부 보완일 뿐 필수가 아니다. 확보 범위를 `source-coverage`(`fulltext|section-extract|abstract-only|unknown`)에 정직하게 적는다.
4. **도표 manifest.** 노트를 쓰기 전에 원문에서 Figure/Table 목록을 임시 JSON으로 만든다. 항목마다 원문 라벨 그대로의 `id`, 본문 여부(`true|false|"unsure"`), 확인 상태(`viewed|caption-only|not-seen`)를 적는다. 부록·보충자료는 `false`. 노트에서 거꾸로 만들지 않는다.
5. **작성.** 선택한 템플릿의 절을 순서대로 채운다. `general-v1`의 `## 개요`는 `paper-digest` 스킬 규칙으로 실제 작성한 결과를 그대로 넣는다. 본문 Figure/Table은 하나도 빠짐없이 `### Figure N` / `### Table N` 아래 각각 설명한다. 길이 상한은 없다.
6. **검증.** Write 직후 아래 명령을 직접 실행한다. `SKIPPED:` 줄이 남아 있으면 완료가 아니다.
7. **Wiki Integration.** 중복 재확인, `linked-bases` 확인, 관련 노트 연결, `build_catalog.py`, `lint.py`, `_wiki/log.md` 기록.

## 공통 규칙 (템플릿이 끌 수 없음)

- 사실마다 원문 위치(Section/Table/Figure) 또는 `[위치 미확인]`.
- 출처 라벨 `author-stated | analyst-inference | unknown`을 섞지 않는다.
- 원문에 없는 수치·조건·주장·도표·arXiv 링크를 만들지 않는다. 기억 속 논문 내용으로 빈칸을 채우지 않는다. 원문 전체를 읽고도 없으면 "보고되지 않았다", 읽지 못한 범위에 있을 수 있으면 "확보한 범위에서 확인하지 못했다". 둘을 섞지 않는다.
- `abstract-only`·`section-extract` 노트는 짧게 쓴다. 범위 한계는 첫 절에 한 번만 밝히고, 채울 수 없는 절에는 "확보한 범위에 없음" 한 줄이면 된다. 초록 문장들을 이어 붙여 인과관계나 선행 연구 비교를 만들지 않는다.
- 지표가 없는 논문이면 템플릿의 지표 절(`general-v1`은 `## 지표`)에 "해당 없음"과 이유를 쓴다. 절 제목은 템플릿이 정한다.
- 도표를 직접 못 봤으면 캡션에서 확인되는 것만 쓰고 `caption-only`, 캡션도 못 봤으면 `not-seen`으로 표시한다. 항목별 `확인 상태`는 manifest의 `evidence`와 같아야 하며 빈 제목만 두면 설명한 것이 아니다. 그런 노트는 `quality-status: review`다.
- 도표 범위를 줄이는 것은 사용자가 명시적으로 요청했을 때만이며 `visual-scope: user-narrowed` + `visual-scope-note`에 그 요청을 적는다.
- 용어는 지우지 않는다. 첫 등장에 `용어(쉬운 설명)`. 15어절·비유 개수·수치 반복 금지 같은 v2 규칙은 새 노트에 적용하지 않는다.

## 저장

`vault_root`: 사용자 지정 → `PAPER_DRILLER_VAULT` → CWD에 `Public/`이 있으면 CWD → 없으면 사용자에게 확인. `destination`은 vault_root 상대 경로다. AI 논문 `Public/AI/Papers/`, 비-AI 논문 `Public/{domain}/`. Category 하위 폴더를 만들지 않는다. **PDF 위치에서 저장 경로를 추측하지 않는다.**

frontmatter는 **정확히 13개 키, 이 순서**다: `type: paper`, `Reading-Status`, `Read-Depth`, `Author`, `Journal/Conference`, `Published Year`, `Topic`, `Review-Date`, `Comment`, `URL`, `Category`, `linked-bases`, `Lab`. 빈 값은 `Key:`. 그 외 키(`arXiv-ID`, `DOI`, `Evidence-Quality`, `Reproducibility`, `isTargetPaper` 등)는 쓰지 않는다. 계약의 단일 기준은 vault `Public/_tools/paper_frontmatter.py`이고 local hook 차단은 별도 설치·검증된 환경에 한하며 양 harness에서 자동 보장하지 않는다. `Read-Depth`는 사람의 읽기 깊이이므로 새 노트는 비우고, `Reading-Status`는 비우거나 `☑️ Not Started`다. 새 노트 식별 키 `template-version: paper-note-v3`, `template-id`, `summary-mode`, `profile`, `source-coverage`, `quality-status`, `visual-check`, `visual-scope`는 YAML이 아니라 frontmatter 바로 뒤 `<!-- BEGIN DRILLER:meta` … `END DRILLER:meta -->` 블록에 `key: value` 한 줄씩 둔다. `reading-decision`은 실제로 판단했을 때만 적는다. 본문은 `<!-- BEGIN AUTO:body template-id={id} -->` … `<!-- END AUTO:body -->` 한 쌍 안에 두고, 그 뒤에 `<!-- BEGIN USER:notes -->` … `<!-- END USER:notes -->`를 둔다. 전체 예시는 `references/workflow.md` 7절.

## 검증 명령

공통 정적 계약은 `bash "${SKILL_ROOT}/scripts/validate-driller.sh"`로 검사한다. 이는 로컬 vault 엔진·unmanaged hooks·모델 실행을 검사하지 않는다. 아래 생성물 완료 검사와 frontmatter 도구는 별도 로컬 통합이다. 새 기기에서는 사용자가 승인한 vault 엔진과 PyYAML 인터프리터를 명시적으로 준비해야 한다. 기존 개인 경로의 hook 차단을 양 harness 공통 기능으로 보장하지 않는다. Codex에서도 생성물 검사기는 canonical `${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py`를 명시적으로 실행할 수 있으며 schema/template는 checkout 원본을 읽는다. 자동 hook 등록이나 로컬 엔진 import는 이 SSOT 설치 단계가 하지 않는다.

두 검사는 역할이 다르다. **(a) frontmatter 검사**(`paper_frontmatter.py check`, hook과 같은 판정)는 모든 `type: paper` 노트의 공통 계약이며 본문에 아무것도 요구하지 않는다. **(b) 생성물 완료 검사**(`paper-format-validator.py`)는 driller가 만든 노트의 절 구성·도표 manifest·갱신 보존을 보는 선택 검사이고, 수동 노트나 vault 전체의 준수 여부를 판정하는 도구가 아니다. 기본 `python3`에는 PyYAML이 없을 수 있으므로 아래처럼 전용 venv를 쓴다.

```bash
PY="${PAPER_FRONTMATTER_PYTHON:?PyYAML이 있는 승인된 local interpreter 절대경로 필요}"
# (a) frontmatter 13키 — 래퍼가 인터프리터를 고른다
bash "$VAULT/Public/_tools/paper_frontmatter.sh" check "$NOTE"
# (b) 생성물 완료 검사 — driller 노트 전용
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --path "$NOTE" --manifest "$MANIFEST"            # 신규 완료 조건
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --path "$NOTE" --manifest "$MANIFEST" --previous "$OLD"   # 갱신
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --path "$NOTE" --manifest "$MANIFEST" --previous "$OLD" --approved-switch   # 사용자가 승인한 템플릿 전환만
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --path "$NOTE" --meta "$META_JSON"              # DRILLER:meta 블록이 없는 옛 노트에 v2/v3 규칙 적용
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --check-template ${SKILL_ROOT}/references/templates/{id}.md   # 새 템플릿 등록 직후
bash ${SKILL_ROOT}/scripts/validate-driller.sh                                    # 정적 계약
```

`CHECKED:`는 실제 검사한 것, `SKIPPED:`는 안 한 것이다. exit 2면 stderr의 `FORMAT_VIOLATION`을 고치고 다시 실행한다(최대 3회). 잘못된 manifest는 건너뛰기가 아니라 실패다. 검증기는 노트와 manifest의 일치만 확인하고, manifest가 빠뜨린 도표나 실제로 봤는지 여부는 증명하지 못한다.

## Legacy

`template-version: paper-preread-v2`·`paper-deep-v2` 노트와 옛 agent 기반 deep 경로는 `references/legacy-workflow.md`, `references/preread-v2-spec.md`, `references/readability-spec.md`, `references/insight-digest-spec.md`를 따른다. 기존 노트의 본문은 일괄 변환하지 않는다(frontmatter만 13키로 마이그레이션되며 옛 YAML 키는 백업 manifest에 남는다). 옛 v2 검증(5,500자 상한, 6개 H2)은 `DRILLER:meta` 블록 또는 `--meta`로 v2임을 알 때 그대로 동작한다. `paper-digest`, `paper-radar`, `paper-understand`, 기존 agent 파일은 바꾸지 않았다.

## References

- `references/workflow.md` — 선택·갱신·수집·manifest·검증·Wiki 절차 전체
- `references/templates/general-v1.md` — 일반 7부 템플릿과 절별 작성 안내
- `references/paper-schema.json` — frontmatter·enum·manifest 스키마
- `references/legacy-workflow.md` — 옛 v2/deep 절차 보존본
- `scripts/validate-driller.sh` — 정적 계약 검증

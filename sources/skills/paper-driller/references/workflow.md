# Paper Driller v3 — 작업 절차 (workflow)

이 문서는 `SKILL.md`가 짧게 말한 규칙을 자세히 푼 것이다. 새 노트(`template-version: paper-note-v3`)는 이 문서를 따른다. 옛 preread v2·deep 절차는 `references/legacy-workflow.md`에 그대로 남아 있고, 새 노트에는 적용하지 않는다.

## 0. 용어

| 용어 | 뜻 |
|---|---|
| 템플릿 | 노트의 절(H2) 구성과 작성 안내를 담은 markdown 파일 하나. `references/templates/{id}.md`. 맨 앞 ```json 블록이 메타데이터다. 별도 registry는 없다. 디렉터리 안 파일 목록이 곧 목록이다. |
| `general-v1` | 첫 번째 일반 템플릿. 7부 구조. `auto`가 가리키는 유일한 템플릿. |
| manifest | 원문에서 직접 확인한 Figure/Table 목록을 적은 임시 JSON. 노트를 검증하는 기준. 노트에서 거꾸로 만들지 않는다. |
| AUTO:body | 스킬이 생성하고 다시 생성할 수 있는 본문 구간. 한 노트에 정확히 한 쌍. |
| USER:notes | 사용자가 쓰는 구간. 스킬이 절대 고치지 않는다. |

## 1. 호출과 템플릿 선택

```text
/paper-driller <arXiv-ID | DOI | URL | 제목> [--template <id>|auto] [--mode preread|deep] [--profile ...] [--humanize]
```

| 상황 | 동작 |
|---|---|
| 새 논문, 템플릿 미지정 | `references/templates/`의 파일 목록을 이름·용도와 함께 보여주고 선택을 기다린다. 템플릿이 하나뿐이어도 묻는다. |
| `--mode preread`만 지정 (radar `드릴` 경로 포함) | 플래그는 받아들이되 템플릿 질문은 그대로 한다. `--mode`는 템플릿 선택이 아니다. |
| 명시적 `auto` (`--template auto`, `--auto`, "auto로", "알아서 일반으로") | 반드시 `general-v1`. 전문 템플릿을 자동으로 고르지 않는다. |
| `--template <id>` | 파일이 있고 `--check-template`을 통과하면 재질문 없이 사용. 없거나 깨졌으면 사용자에게 알리고 선택을 기다린다. |
| 논문 성격상 새 전문 구조가 더 낫다고 판단 | 6절 절차로 제안한다. 동의 전에는 파일을 만들지 않는다. 거절하면 이미 고른 템플릿이 있을 때만 그것으로 진행하고, 없으면 목록을 다시 보여 주고 선택을 기다린다. 거절을 `general-v1` 선택으로 해석하지 않는다. 명시적 `auto`는 제안으로 멈추지 않고 `general-v1`이다. |
| 기존 노트 있음 (2절 dedup) | 기존 `template-id`를 유지한다. 다른 템플릿이나 `auto`가 함께 왔어도 구조 전환 요청인지 불분명하면 기존 구조 유지. 사용자가 전환을 명시했으면 그 말이 동의다. |
| 비대화형 실행(`claude -p`)에서 선택 없음 | "템플릿 선택 필요" 상태와 선택지를 출력하고 종료한다. 노트를 만들지 않는다. radar 완료 상태나 노트 경로도 기록하지 않는다. |

`--mode`는 `summary-mode` 값이 된다. 기본 `preread`. `deep`은 선택한 템플릿을 다 채운 뒤 `## 상세 독해 노트`를 덧붙이는 것이다. 검증기는 이 절이 `AUTO:body` 안에 있고, 비어 있지 않으며, 템플릿의 필수 절 뒤에 오는지 확인한다. 템플릿 선택이나 도표 전수 설명을 건너뛰는 옵션이 아니다. 옛 deep 경로(agent 여러 개)는 legacy 문서에만 있다.

## 2. 중복 확인이 먼저

템플릿을 묻기 **전에** 같은 논문 노트가 있는지 확인한다. frontmatter의 원문 식별자는 `URL` 하나다. `URL`에서 식별자를 유도해 비교한다: `arxiv.org/abs|pdf/{id}` → arXiv id(버전 접미사 제거, 소문자), `doi.org/{doi}` → DOI(소문자), 그 외 → 정규화 URL. 같은 arXiv id 또는 같은 DOI면 같은 논문이고, 그 밖에는 정규화 URL이 완전히 같을 때만 같은 논문이다. URL은 보수적으로 비교한다: 스킴, 호스트 대소문자, 앞의 `www.`, `#` 조각, 끝 슬래시 하나만 무시한다. 경로 대소문자와 query는 그대로 둔다. `openreview.net/forum?id=A`와 `forum?id=B`, `/Paper`와 `/paper`는 다른 논문이다. 검증기의 `derive_doc_ids`/`_norm_url`과 같은 규칙이다. `_wiki/catalog/*.md`를 먼저 훑고, 없으면 `Public/**/*.md` frontmatter를 본다. 옛 노트의 `arXiv-ID`·`DOI` 키는 마이그레이션으로 사라졌으므로 검색 기준으로 쓰지 않는다.

있으면 `update-existing`이다.

- 기존 `template-version`·`template-id`·`summary-mode`(`DRILLER:meta` 블록)를 유지한다. 옛 v2 노트는 v2로 남는다. 일괄 변환은 하지 않는다.
- 자동으로 바꿔도 되는 frontmatter 키는 `Review-Date` 하나다 (`paper-schema.json` `frontmatter.controlled_update_fields`). `DRILLER:meta`에서 자동으로 바꿔도 되는 키는 `source-coverage`, `quality-status`, `visual-check`, `visual-scope`, `visual-scope-note`, `reading-decision`, `decision-confidence`다 (`driller_meta.controlled_update_fields`).
- 다음은 자동으로 덮어쓰지 않는다: `URL`, `Author`, `Published Year`, `Journal/Conference`, `Topic`, `Comment`, `Category`, `linked-bases`, `Lab`, 그리고 사람 소유 필드 `Reading-Status`·`Read-Depth`. 값이 충돌하면 보고하고, 해결 전에는 검증 완료라고 말하지 않는다.
- 기존 노트의 YAML에 13키 밖의 키(`arXiv-ID`, `DOI`, `Evidence-Quality`, `tags`, 옛 `template-version` 등)가 남아 있으면 그 노트는 아직 마이그레이션되지 않은 것이다. 스킬이 조용히 지우지 않는다. 사용자에게 알리고 `bash Public/_tools/paper_frontmatter.sh fix --dry-run "$NOTE"`로 계획을 보인 뒤 `--apply --backup-dir`로 frontmatter만 옮긴다(본문 바이트 보존). 그 전에는 `--previous` 검증이 통과하지 않는다.
- `AUTO:body` 안만 다시 쓴다. 밖의 내용(H1 제목 포함)과 `USER:` 블록은 글자 하나 바꾸지 않는다. `USER:` 블록 안의 `TODO`는 사용자 메모이므로 검사하지 않는다.
- frontmatter는 키별 원문 그대로 비교한다. 들여쓰기·따옴표·목록 모양을 바꾸면 변경으로 본다. 검증을 통과시키려고 사용자 YAML을 다시 포맷하지 않는다.
- 템플릿 전환은 사용자가 대화에서 명시적으로 승인했을 때만 한다. 그때 검증에 `--approved-switch`를 붙인다. 이 플래그는 이미 받은 동의를 기록할 뿐 동의의 증거가 아니며, `template-version`·`template-id`·`summary-mode` 세 키만 바꿀 수 있게 한다. 승인 뒤에도 사용자 필드·`USER:` 블록·H1·마커 밖 내용은 그대로여야 한다.
- `AUTO:body` 마커가 없는 옛 노트는 자동 갱신 대상이 아니다. 바꿀 부분을 diff로 제시하고 승인을 받는다. 통째로 다시 쓰지 않는다.
- 검증: `--path NEW.md --previous OLD.md`가 위 규칙을 기계로 확인한다. 승인된 전환은 `--previous OLD.md --approved-switch`.

## 3. 원문 수집과 source-coverage

웹/PDF 수집이 기본 경로다. 먼저 활성 세션의 실제 도구 목록과 권한을 확인한다. Claude는 `WebFetch`로 arXiv HTML/PDF·출판사 원문을 가져오고, URL을 모르면 `WebSearch`로 제목을 검색한다. 캐시된 로컬 PDF 경로가 실제로 반환되면 `Read(pages=…)`로 읽는다. cross-host `redirect`가 나오면 안내 URL로 다시 호출한다. Codex는 실제 제공되는 웹·PDF 도구를 사용하며, `hermes-tools`의 `web_search`/`web_extract`도 노출된 경우에만 사용한다. Claude 이름을 Codex 호출 이름으로 가정하지 않는다.

Claude의 `mcpsemanticscholar`·`paper-search-mcp-openai-v2`는 실제 도구가 제공되고 인증·권한이 확인된 경우에만 메타데이터·초록·검색을 보완한다. Codex에서 이 서버들을 필수로 요구하거나 자동 등록하지 않는다. 웹 도구가 없으면 사용자가 제공한 PDF·텍스트만 읽고 한계를 밝힌다. 검색 결과·초록·웹 요약은 전문이 아니다.

새 노트는 **전문**을 목표로 한다. 도표를 전부 설명하려면 본문을 다 봐야 하기 때문이다. 긴 PDF는 page range로 나눠 끝까지 읽는다. 확보 범위를 `source-coverage`에 정직하게 적는다: `fulltext` | `section-extract` | `abstract-only` | `unknown`. `abstract-only`·`unknown`이면 방법·결과 세부를 추측하지 않고 `quality-status: review`로 둔다. `ready`는 금지다.

`output_lang`은 사용자 언어를 따른다. 고유명·수식·수치·원문 식별자는 원문 그대로 둔다.

## 4. 도표 manifest

노트를 쓰기 **전에** 원문에서 Figure/Table 목록을 만들어 임시 JSON 파일로 둔다(예: `${TMPDIR:-/tmp}/paper-driller-{doc}/manifest.json`처럼 작업별 경로). 노트 안에 저장하지 않는다. 검증기는 이 파일과 노트를 대조한다.

```json
{
  "manifest_version": 1,
  "doc_id": "arxiv:2601.15380",
  "doc_version": "v2",
  "source": "pdf:/path/to/cached.pdf",
  "scan": "complete",
  "scan_note": "",
  "items": [
    {"id": "Figure 1", "caption": "...", "locator": "p.2", "main_body": true, "evidence": "viewed"},
    {"id": "Table 3", "caption": "...", "locator": "p.7", "main_body": "unsure", "evidence": "caption-only", "note": "Appendix 경계가 불명확"},
    {"id": "Figure 9", "caption": "...", "locator": "p.15", "main_body": false, "evidence": "not-seen", "note": "Appendix B"}
  ]
}
```

규칙:

- `doc_id`는 `arxiv:` | `doi:` | `url:` 접두사가 있는 문자열이다. 값은 형식이 맞아야 한다(arXiv id, `10.xxxx/…` DOI, `http(s)://` URL). 노트 frontmatter의 같은 종류 값과 같은 규칙으로 정규화해 대조한다. 다르면 도표 검증 실패. 버전이 양쪽에 모두 적혀 있고 다르면 실패(`doc_version` 또는 `arxiv:...v2`). `doc_id`에 버전이 들어 있으면 `doc_version`은 그 값과 같아야 한다. `manifest_version`은 정수 `1`이다(`1.0` 아님).
- `source`는 어디서 목록을 얻었는지 적는 기록이다. 명령이 아니며 실행하지 않는다.
- `scan`: 원문 전체를 끝까지 훑었으면 `complete`, 아니면 `partial` + `scan_note`.
- `id`는 원문 라벨 그대로. `Figure 3`, `Fig. 3`, `그림 3`을 합치지 않는다. 특이한 번호를 추측한 번호로 바꾸지 않는다. 같은 id 중복 금지.
- `main_body`: `true`(본문) | `false`(부록·보충자료) | `"unsure"`. 문자열 `"false"`는 잘못된 값이다. 번호나 위치만으로 부록 여부를 정하지 않는다. 캡션·섹션 제목·쪽 배치를 본다.
- `evidence`: `viewed`(직접 봄) | `caption-only`(캡션만) | `not-seen`. 노트의 항목별 `확인 상태` 줄은 이 값과 같아야 한다. 검증기는 두 값의 일치만 확인하고, 실제로 봤는지는 증명하지 못한다.
- `^(Figure|Table)\s*\d+` 같은 단순 검색 결과를 완전한 목록으로 취급하지 않는다. HTML figure 요소, PDF 캡션을 우선한다.
- 사용자가 범위를 줄였으면 `scope` 블록을 추가한다: `{"requested_by_user": "사용자의 실제 요청 문장", "include": ["Figure 1", "Table 2"]}`. 그리고 노트에 `visual-scope: user-narrowed`와 `visual-scope-note`(같은 요청 문장)를 적는다. 문자열 하나만으로 동의를 주장하지 않는다. 템플릿 선택만으로 범위가 줄지 않는다.

노트가 다뤄야 하는 대상(target)은 `main_body`가 `true` 또는 `"unsure"`인 항목이다. `scope`가 있으면 `include` 목록이다.

`visual-check` 값은 한 규칙으로 정한다(검증기의 `expected_visual_check`).

| 값 | 조건 |
|---|---|
| `viewed` | 모든 대상이 `viewed` |
| `caption-only` | 모든 대상이 `caption-only` |
| `mixed` | `viewed`와 `caption-only`가 섞임 |
| `unverified` | 대상 중 `not-seen`이 있음, 또는 `scan: partial`인데 대상이 0개 |
| `none` | `scan: complete`이고 `scope` 없이 대상이 0개일 때만 |

`quality-status: ready`는 `scan: complete`, 모든 대상 `main_body: true`, `visual-check`가 `viewed` 또는 `none`, `source-coverage`가 `fulltext`/`section-extract`일 때만 허용한다. 캡션만 본 경우, 미확정 항목, 부분 스캔은 모두 `review`다.

## 5. 작성 규칙 (모든 템플릿 공통)

템플릿이 제목을 바꿀 수는 있어도 다음은 끌 수 없다.

- 사실마다 원문 위치 또는 `[위치 미확인]`.
- 출처 라벨 `author-stated` | `analyst-inference` | `unknown` 구분.
- 원문에 없는 수치·조건·주장·도표를 만들지 않는다.
- `source-coverage`와 도표 확인 상태의 한계를 노트에 밝힌다. 전문이 아니면 첫 절에 한 번만 밝히고, 채울 수 없는 절에는 "확보한 범위에 없음" 한 줄만 쓴다. 절마다 긴 한계 문단을 되풀이하지 않는다.
- "보고되지 않았다"(원문 전체를 읽고도 없음)와 "확보한 범위에서 확인하지 못했다"(읽지 못한 범위에 있을 수 있음)를 구분한다. 기억 속 논문 내용으로 빈칸을 채우지 않는다. 초록 문장들을 이어 붙여 인과관계나 선행 연구 비교를 만들지 않는다.
- 본문 Figure/Table 전수 개별 설명(사용자가 명시적으로 줄이지 않는 한).
- 사용자 내용 보존.

문체: 이 분야를 처음 보는 고등학생이 읽는다고 생각한다. 용어는 지우지 말고 첫 등장에 괄호 설명을 붙인다. 비유는 이해를 돕는 용도로만 쓰고, 비유 뒤에는 정확한 용어로 돌아온다. 15어절 제한, 비유 개수 제한, 수치 반복 금지, 전체 길이 상한은 새 노트에 적용하지 않는다. 그 규칙들(`readability-spec.md`, `preread-v2-spec.md`)은 v2 노트 전용이다.

`general-v1`의 `## 개요`는 `paper-digest/SKILL.md`의 규칙으로 실제 작성한 결과를 그대로 넣는다. 다른 템플릿은 절 제목이 달라도 되며, 그 템플릿이 개요 자리로 정한 절에 같은 규칙을 적용한다. `--humanize`를 켰어도 개요·표·frontmatter·BibTeX·도표 절의 수치는 다듬기에 넘기지 않는다. 다듬은 뒤 숫자·괄호 안 용어·`[위치 미확인]`·`[[링크]]`가 바뀌었으면 그 블록은 원본으로 되돌린다.

## 6. 새 전문 템플릿 제안·등록

논문이 일반 7부와 잘 안 맞을 때(예: 순수 이론, 시스템 논문, 서베이) 이렇게 한다.

1. 사용자에게 제안한다: 왜 필요한지, 절 제목 목록, 저장할 id(`^[a-z0-9][a-z0-9-]{1,63}$`, 예 `theory-v1`), 도표 절 이름. 공통 규칙(5절)은 그대로 적용된다고 말한다.
2. **"만들고 저장해도 됩니까?"** 명시적 동의를 받는다. 동의 없으면 저장하지 않는다. 이미 고른 템플릿이 있으면 그것으로 진행하고, 없으면 목록을 다시 보여 주고 선택을 기다린다. 거절은 `general-v1` 선택이 아니다.
3. 동의하면 `references/templates/{id}.md` 하나를 쓴다. 맨 앞 ```json 메타데이터(`id`, `title`, `description`, `required_h2`, `optional_h2`, `visual_section`), 그 뒤 작성 안내. 기존 파일을 덮어쓰지 않는다. 구조를 바꾸려면 새 id다.
4. 저장 직후 검사한다. 실패하면 파일을 고치거나 지우고 다시 검사한다.

```bash
PY="${PAPER_FRONTMATTER_PYTHON:?PyYAML이 있는 승인된 local interpreter 절대경로 필요}"
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --check-template ${SKILL_ROOT}/references/templates/{id}.md
```

검사 항목: id 형식, 파일명 = id, 템플릿 디렉터리 바로 안(경로 이동·심볼릭 링크 거부), 메타데이터 자료형, 빈·중복 제목, `visual_section`이 `required_h2`에 있음, 안내 본문 존재. 템플릿 파일의 내용은 절대 실행하지 않는다.

## 7. 저장 위치와 파일 구조

`vault_root`: 사용자 지정 → `PAPER_DRILLER_VAULT` → CWD에 `Public/`이 있으면 CWD → 없으면 사용자에게 확인. `destination`은 vault_root 상대 경로다. AI 논문 `Public/AI/Papers/`, 비-AI 논문 `Public/{domain}/`. Category 하위 폴더를 새로 만들지 않는다. **PDF가 있는 위치에서 저장 경로를 추측하지 않는다.** 학술 논문은 `type: paper`를 첫 키로 둔다. `scholarly=no` 일반 글은 `type: paper`를 쓰지 않는다.

frontmatter는 **정확히 13개 키, 이 순서**다 (vault `Public/_tools/paper_frontmatter.py`가 단일 기준, hook이 강제한다). 빈 값은 `Key:`로 둔다. `arXiv-ID`·`DOI`·`Evidence-Quality`·`Reproducibility`·`isTargetPaper`·`Benchmark-Type`과 템플릿 키는 YAML에 쓰지 않는다. 템플릿·수집·도표 메타데이터는 frontmatter 바로 뒤의 `DRILLER:meta` HTML 주석 블록에 `key: value` 한 줄씩 적는다 (Obsidian 읽기 화면에는 보이지 않는다).

```markdown
---
type: paper
Reading-Status: "☑️ Not Started"
Read-Depth:
Author: "First Author et al."
Journal/Conference: "Venue"
Published Year: 2026
Topic: "keywords"
Review-Date: "YYYY-MM-DD"
Comment: "문제 한 구절 + 결과 한 구절"
URL: "https://arxiv.org/abs/XXXX.XXXXX"
Category: "Reasoning"
linked-bases: "[[Papers.base]]"
Lab:
---
<!-- BEGIN DRILLER:meta
template-version: paper-note-v3
template-id: general-v1
summary-mode: preread
profile: empirical
source-coverage: fulltext
quality-status: ready
visual-check: viewed
visual-scope: main-body
END DRILLER:meta -->
# {한국어 제목}

<!-- BEGIN AUTO:body template-id=general-v1 -->
## 개요
...
## 본문 도표
### Figure 1
...
<!-- END AUTO:body -->

<!-- BEGIN USER:notes -->
<!-- END USER:notes -->
```

- 13개 키는 어디에 저장하든 모두 있어야 한다. `Category`·`linked-bases`·`Lab`은 비-AI 논문이면 비워 둔다. 값을 추측해 채우지 않는다.
- `Read-Depth`는 **사람의** 읽기 깊이다. 스킬이 원문을 읽었다고 채우지 않는다. 새 노트는 항상 비운다. `Reading-Status`는 비우거나 `☑️ Not Started`다. 갱신 시 두 값은 그대로 둔다.
- `DRILLER:meta` 블록은 정확히 하나, frontmatter 뒤·H1 앞·`AUTO:body` 밖에 둔다. 코드 펜스 안에 적힌 블록은 글자일 뿐이다. 허용 키는 `paper-schema.json`의 `driller_meta` 목록뿐이다. 블록이 없는 옛 노트를 v2/v3 규칙으로 검사하려면 `--meta META.json`을 준다.
- `reading-decision`·`decision-confidence`는 선택이다. 판단을 실제로 했을 때만 `DRILLER:meta`에 적는다. 호환을 위해 만들어 넣지 않는다.
- `visual-scope: user-narrowed`이면 `visual-scope-note`가 필수다.
- H1 제목은 `AUTO:body` 밖에 둔다. `## Wiki 연결`, `## BibTeX`는 AUTO 안 선택 절이다.
- 마커는 정확히 한 쌍. 시작 마커의 `template-id`는 필수이며 frontmatter와 같아야 한다. 코드 블록 안에 적힌 마커는 표시용 글자일 뿐 마커가 아니다(AUTO 전체를 코드 블록으로 감싸면 마커 0개로 실패). 검증기는 AUTO 안에서만 절·도표를 세고, 코드 블록과 `USER:` 블록 안 제목은 세지 않는다. `template-version`을 지운 v3 형태 노트는 legacy로 취급되지 않고 실패한다.

## 8. 검증

검사는 두 층이다.

- **(a) frontmatter 13키 검사** — `Public/_tools/paper_frontmatter.py check` (래퍼 `paper_frontmatter.sh`). 모든 `type: paper` 노트의 공통 계약이며 명시적으로 설치한 local hook과 같은 엔진 계약을 사용한다. hook 차단 동작은 별도 검증하며 양 harness에서 자동 보장하지 않는다. 본문(H1, 길이, 절)은 보지 않는다. 수동 노트·옛 노트는 이것만 통과하면 된다.
- **(b) 생성물 완료 검사** — `"${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py"`. driller가 만든 노트의 절 구성·도표 manifest·갱신 보존을 보는 **선택** 검사다. hook이 아니므로 Write 직후 직접 실행한다. 새 노트의 **완료 조건은 manifest까지 넣은 이 검사 통과**다. `DRILLER:meta`도 `--meta`도 없는 노트는 legacy 경로(H1·최소 본문)로 보는데, 이는 driller 산출물 점검용이지 vault 전체의 준수 판정이 아니다. 옛 v2 노트에 v2 규칙을 적용하려면 `--meta META.json`을 붙인다.

기본 `python3`에는 PyYAML이 없을 수 있다. 전용 venv 인터프리터를 한 번 정의해 쓴다.

```bash
PY="${PAPER_FRONTMATTER_PYTHON:?PyYAML이 있는 승인된 local interpreter 절대경로 필요}"
# (a) frontmatter만 (엔진, hook과 같은 판정) — 래퍼가 PyYAML 있는 인터프리터를 고른다
bash "$VAULT/Public/_tools/paper_frontmatter.sh" check "$NOTE"
# (b) 완료 검사 (신규)
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --path "$NOTE" --manifest "$MANIFEST"
# (b) 갱신 검사
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --path "$NOTE" --manifest "$MANIFEST" --previous "$OLD_COPY"
# (b) 사용자가 승인한 템플릿 전환 (플래그는 동의의 기록이지 증거가 아니다)
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --path "$NOTE" --manifest "$MANIFEST" --previous "$OLD_COPY" --approved-switch
# (b) 형식만 (manifest 없음) — 도표 완전성은 검사하지 않는다
"$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py" --path "$NOTE"
# legacy stdin 방식도 그대로 동작한다
printf '{"tool_name":"Write","tool_input":{"file_path":"%s"}}' "$NOTE" | "$PY" "${SKILL_ROOT}/../../hooks/claude/paper-format-validator.py"
```

출력 읽는 법:

- `CHECKED: frontmatter, structure, template:general-v1, visuals` — 실제로 검사한 항목.
- `SKIPPED: visuals (no manifest …)` — 검사하지 않은 항목. 이 줄이 있으면 완료가 아니다.
- `RESULT: PASS|FAIL`, exit 0|2. FAIL이면 stderr의 `FORMAT_VIOLATION` 목록을 고치고 다시 실행한다(최대 3회, 그래도 실패하면 사용자에게 보고).
- CLI `--path`는 파일 없음, 디렉터리, 비-Markdown, 디코딩 실패, frontmatter 없음, `type: paper` 아님, 13키 계약 위반(금지 키·누락 키·순서·중복 키·깨진 YAML), 알 수 없는 `template-version`, schema·엔진 로드 실패를 모두 FAIL로 낸다. `SKIP_PAPER_VALIDATOR`는 CLI에 적용되지 않는다. 범위는 오직 `type: paper`다. 파일명(`_overview` 등)이나 폴더로 제외하지 않는다.
- 명시적으로 준 manifest가 잘못됐으면 SKIPPED가 아니라 FAIL이다. v2·legacy 노트에 manifest를 주면 형식과 논문 일치만 검사하고 도표 검사는 `SKIPPED:`로 표시한다.
- `--path`에 잘못된 입력(자료형이 틀린 manifest, 모순된 버전, 잘못된 DOI/URL, 깨진 템플릿 메타데이터)을 주면 traceback 없이 exit 2와 해당 필드 오류를 낸다.

검증기는 노트와 manifest의 **일치**를 확인한다. manifest 자체가 빠뜨린 도표나 원문 해석 오류는 잡지 못한다. 그 책임은 작성자에게 있다.

정적 계약 검사: `bash ${SKILL_ROOT}/scripts/validate-driller.sh`.

## 9. Wiki Integration

legacy와 같다.

1. 중복 재확인 (`URL`에서 유도한 arXiv id/DOI/정규화 URL)
2. `linked-bases` 파일 존재 확인
3. 관련 기존 노트 1–3개 연결
4. `python3 Public/_tools/build_catalog.py`
5. 대상 catalog에 새 행 확인
6. `python3 Public/_tools/lint.py`
7. 새 오류가 없으면 `_wiki/log.md`에 기록

## 10. 다른 스킬과의 관계

- `paper-radar` `드릴`은 `/paper-driller … --mode preread`를 부른다. 이 호출은 그대로 받되 템플릿 선택 단계로 이어진다. 노트가 실제로 만들어지기 전에는 radar에 노트 경로를 기록하지 않는다.
- `paper-understand`는 수정하지 않았다. 새 노트에서의 대응은 다음과 같다.

| understand가 찾는 것 | v3 노트에서 |
|---|---|
| `source-coverage` | 같은 키 |
| `reading-decision` | 있으면 같은 키, 없으면 없는 것(만들지 않음) |
| claim ledger | `general-v1`: `## 주요 결과` 표의 행(주장·근거 위치·수치·조건·출처 라벨). 다른 템플릿: 그 템플릿이 결과·근거를 담는 절 |
| reading map | `general-v1`: `## 주요 결과`의 근거 위치 열 + `## 본문 도표`의 각 항목. 다른 템플릿: 근거 위치 열 + 그 템플릿의 `visual_section` 항목 |

- `paper-digest`는 개요 절에서 그 규칙대로 실행할 뿐, 파일을 바꾸지 않는다.

## 11. 선택 흐름 시나리오 (문서 검토용)

자동 실행기가 없어 아래는 테스트가 아니라 검토용 표다.

| 입력 | 기대 동작 |
|---|---|
| `/paper-driller 2601.15380` | dedup → 없음 → 템플릿 목록 제시, 대기 |
| `/paper-driller 2601.15380 --mode preread` (radar) | 위와 같음. `summary-mode: preread` 예약 |
| `/paper-driller 2601.15380 --template auto` | `general-v1`로 바로 진행 |
| `/paper-driller 2601.15380 --template theory-v1` (파일 있음·검사 통과) | 재질문 없이 진행 |
| 같은 명령, 파일 없음 | 알리고 목록 제시, 대기 |
| 새 논문, 모델이 전문 구조 제안 | 제안·동의 요청. 동의 전 저장 없음 |
| 위 제안 거절, 아직 고른 템플릿 없음 | 목록 다시 제시, 대기. 노트·템플릿 파일 없음 |
| 새 논문 + `auto`, 모델이 전문 구조가 낫다고 봄 | 제안하지 않거나 한 줄로만 언급하고 `general-v1`로 진행 |
| 기존 v2 노트 + `--template auto` | 기존 v2 유지. 전환 의도 확인 질문 |
| 기존 v3 노트 + "general-v1으로 바꿔줘" | 전환 진행. `AUTO:body`만 교체, USER 보존. 검증은 `--previous OLD --approved-switch` |
| `claude -p "/paper-driller 2601.15380"` | 선택 필요 상태 출력 후 종료. 파일 없음 |

---
name: paper-driller
description: 논문이나 긴 글을 spine 분석 후 심층 노트 또는 공유용 한 문단 요약으로 정리한다.
allowed-tools:
  - mcp__arxiv__download_paper
  - mcp__arxiv__read_paper
  - mcp__mcpsemanticscholar__get-paper-abstract
  - mcp__mcpsemanticscholar__search-paper-title
  - mcp__mcpsemanticscholar__paper-search-advanced
  - mcp__paper-search-mcp-openai-v2__search_arxiv
  - mcp__paper-search-mcp-openai-v2__search_semantic
  - WebFetch
  - WebSearch
  - Read
  - Write
  - Edit
  - Bash
  - Agent
---

# Paper Driller

## Codex Subagent Compatibility

Legacy Claude invocation snippets in this skill should be interpreted as Codex subagent workflow guidance, not literal Claude Code API calls.

- Spawn subagents only when the user explicitly asks for subagents or parallel agent work, or when the active Codex surface exposes an equivalent explicit subagent workflow.
- Prefer a matching custom agent in `~/.codex/agents/*.toml`; otherwise use Codex built-ins (`explorer` for read-heavy scans, `worker` for implementation, `default` for general roles) with the role prompt as task guidance.
- Do not pass Claude model aliases such as `haiku`, `sonnet`, or `opus` to Codex. Custom agents inherit the parent model unless their TOML file intentionally sets a Codex-supported field such as `model_reasoning_effort`.
- Keep parallel write scopes disjoint; if that is not possible, do the work in the main context and use subagents only for review or read-heavy analysis.


> **Use this for**: 1개 문서(arxiv 논문·일반 URL·파일·붙여넣은 텍스트)를 spine 선행 분석 + 섹션별 병렬 분석으로 깊이 정리.

어떤 글이든 **spine(전체 흐름 맵) → 섹션별 subagent 분석 → readable 합성**으로 정리한다. 학술 문서면 메타/BibTeX를 포함한 노트를, 일반 글이면 비전문가용 readable 요약을 생성한다.

## 외부 접근 (skill-local)

**MCP/외부 fetch 권한은 오직 paper-driller skill에만 있다.** 모든 subagent는 MCP·WebFetch·WebSearch를 사용하지 않으며, paper-driller가 추출해 전달하는 텍스트(또는 이미 로컬에 받아둔 파일 경로)만 입력으로 받는다.

우선순위 (fallback chain):
1. `mcp__arxiv__download_paper` + `mcp__arxiv__read_paper` — arXiv 논문 전문
2. `mcp__mcpsemanticscholar__get-paper-abstract` — SemanticScholar 메타·abstract
3. `mcp__paper-search-mcp-openai-v2__search_*` — 대체 검색
4. `WebFetch(https://arxiv.org/abs/{id})` — 최후 fallback
5. `WebSearch` — 제목 기반 마지막 시도

## Available Agents (6) + 모델/effort

| Agent | Phase | Role | Codex agent config |
|---|---|---|---|
| `paper-spine` | B (선행 1회) | 전체 읽기 → spine(논지·흐름맵·경계·thesis초안). 짧으면 섹션까지 1패스 | custom agent, high reasoning |
| `paper-section-driller` | C 병렬 | 섹션(또는 chunk)별 요약, spine 주입, structure(imrad/free) 분기 | custom agent, high reasoning |
| `paper-meta` | C 병렬(논문만) | 메타데이터 + BibTeX + Category | custom agent, inherited reasoning |
| `paper-evidence` | C 병렬(논문만) | 실험 표 + Mermaid(mmdc) + 재현성 | custom agent, high reasoning |
| `paper-comparison` | C 병렬(논문만) | 관련 연구 비교 매트릭스 | custom agent, high reasoning |
| `paper-digest-composer` | D | readable 서문(insight-digest-spec) + Zettelkasten + 용어 + 태그 | custom agent, high reasoning |

**Codex 운영 주의:** Claude 모델/effort 별칭은 사용하지 않는다. `paper-*` custom agent TOML은 필요한 경우 `model_reasoning_effort = "high"`만 보존하고 모델은 부모 세션에서 상속한다.

**설계 선택지 — Agent Teams vs subagent**: Agent Teams (experimental, v2.1.32+)는 peer-to-peer·공유 task list가 필요할 때 유리하나, 본 설계의 section agent는 서로 독립이고 합성은 composer가 전담하므로 일반 subagent 병렬 호출이 더 경제적이다.

**구조 이력**: (2026-04-17) 5개 `paper-section-*`를 `paper-section-driller`로 통합.
(2026-06-03) Global Spine 도입 — holistic-analyzer를 `paper-spine`으로 흡수해
"선행 1회 전체읽기"로 승격하고, 그 spine을 모든 섹션 호출에 주입해 전체 흐름을 보존한다.
입력 범위를 논문→임의 텍스트로 확장(structure×scholarly 분기). 섹션 fan-out 수는 글의 실제 섹션 수에
따른다(정형 논문이면 5).

---

## Mode detection

- `--bite` 플래그가 명시적으로 전달되면 Bite 모드.
- 사용자 요청 문장에 bite 트리거("논문 요약", "한입 요약", "paper bite", "디스코드에 공유", "share this paper", "summarize for sharing")가 있으면 자동 Bite 모드.
- 그 외 모두 Deep 모드(기본).

Bite 모드는 Phase A/B/C 까지만 수행 후 인사이트 단락을 출력하고 종료한다. Phase D/E/F 및 QC 매트릭스의 엄격한 루프, 파일 Write, hook 검증은 수행되지 않는다.

## Profile detection — 2축 (structure × scholarly)

paper-spine의 SPINE 출력 `structure`와 `scholarly` 두 축을 **독립적으로** 따른다.

- `structure`: **imrad** = abstract/method/results 헤딩·실험 구조가 뚜렷 → section_type(abstract/intro/method/results/discussion) 블록 + **evidence agent**(실험표·재현성) 사용.
  **free** = 그 외(철학·이론·수학 에세이, 블로그, 문서) → 실제 섹션 id로 자유 `<<<SECTION:{id}>>>` 요약, evidence 생략.
- `scholarly`: **yes** = 인용가능 학술원(저자·venue·연도) → **meta agent**(메타+BibTeX), scholarly frontmatter, comparison(관련문서 있을 때), `{vault_root}/Public/AI/Papers/[Category]/` 저장, Phase F hook 검증.
  **no** = 블로그·뉴스·일반 글 → 경량 frontmatter, `{vault_root}/survey-notes/`(또는 사용자 지정) 저장, hook 생략.

조합 예: Turing 1950 = `structure=free, scholarly=yes` → 자유 섹션요약 + BibTeX/메타 + scholarly frontmatter (BibTeX를 잃지 않는다). 블로그 글 = `free, no`. 표준 ML 논문 = `imrad, yes`.

사용자가 `--structure imrad|free` / `--scholarly yes|no`로 수동 override 가능. 감지 근거는 노트에 `<!-- structure: {값} / scholarly: {값} (근거) -->` 주석으로 남긴다.

---

## Workflow

```
[입력: arxiv ID/URL · 일반 URL · 파일 · 붙여넣은 텍스트 + 선택적 --bite/--structure/--scholarly]
      ↓
[Phase A] 수집·정규화 → full_text (+ 논문이면 관련 문서 pre-fetch)
[Phase B] paper-spine 선행 1회 → SPINE(논지·흐름맵·경계·structure·scholarly) + 길이 tier 판정
[Phase C] 섹션 병렬 호출 (spine 주입; Tier S는 spine이 섹션까지, Tier L은 chunk 단위)
          └ scholarly==yes면 meta/comparison, structure==imrad면 evidence 추가
[Phase C.5] QC 매트릭스 루프 (해당 agent만 targeted retry, 최대 3회)
      ↓
  mode == bite?
   ├─ yes → [Phase D'] insight-digest-spec 기반 서문 → chat 출력 → DONE
   └─ no  → [Phase D] readable-composer → [Phase E] 조립 → [Phase F] (논문) hook 검증 → [Phase G] 모델/effort 검증 → DONE
      ↓
[품질 체크리스트 최종 확인]
```

다중 문서 처리: 여러 문서 입력 시 각각에 대해 위 workflow 반복. 사용자에게 처리 목록 확인 후 진행.

---

## Phase A: 수집·정규화

입력 형태별로 텍스트를 확보한다:
- **arxiv ID/URL**: `mcp__arxiv__read_paper` → 실패 시 MCP/WebFetch fallback chain.
- **일반 URL(HTML)**: `WebFetch`로 본문 추출.
- **PDF URL / 저작권 학술 논문**: `WebFetch`는 소형 모델이 **전문을 요약하거나 저작권을 이유로 전문 재현을 거부**할 수 있다. 이때 WebFetch는 PDF 바이너리를 **로컬 tool-results 경로에 캐시**하므로, 그 **캐시된 PDF 경로를 orchestrator가 `Read`(pages=…)로 직접 읽어** `full_text`를 확보한다(네트워크 재fetch 아님). WebFetch 응답에 `redirect`가 감지되면 안내된 URL로 **재호출**한다(cross-host redirect는 자동 추적되지 않음).
- **로컬 파일 경로**: `Read`.
- **붙여넣은 텍스트**: 그대로 사용.
확보한 텍스트를 `full_text`로 정규화한다. 10쪽 초과 PDF는 `Read`의 `pages`로 분할해 전부 읽는다. 이후:

1. **(학술 문서 후보일 때만) 관련 문서 pre-fetch**: comparison agent용 3-5편. (Phase A는 spine 이전이므로 arxiv ID·저자/venue 단서로 추정하고, 확정은 Phase B의 `scholarly` 판정을 따른다.)
2. **관련 논문 pre-fetch (comparison agent용)**: SemanticScholar `paper-search-advanced` 또는 related-papers API로 3-5편 후보 메타 수집.
   - 각 원소: `{ title, year, venue, abstract, code_url?, relation_type }` (`direct` / `base` / `sota` / `alternative`).
   - 선정: 본 논문 제목·키워드로 유사도 상위, 같은 문제 다른 접근 우선.
3. **코드 링크 감지**: 본문에서 `https://github.com/...` 패턴 추출 → evidence agent 입력.

---

## Phase B: Spine 패스 (선행 1회)

`paper-spine`을 **1회 호출**해 `full_text`로부터 SPINE을 만든다. SPINE은 장르·structure·scholarly·
thesis·audience_frame·throughline·flow_map·section_boundaries·terms_to_explain을 담는다. 이 SPINE이
이후 모든 섹션 호출에 **공유 맥락으로 주입**되어 전체 흐름을 보존한다.

길이 판정으로 tier 결정(다음 Phase C):
- **Tier S (짧음)**: `paper-spine`을 `mode=spine_plus_sections`로 호출해 섹션 출력까지
  한 번에 받는다. fan-out 없음. (이전 holistic fallback의 정상화)
- **Tier M (구조적·중간)**: spine 후 section_boundaries대로 section-driller 병렬.
- **Tier L (섹션이 임계 초과)**: 해당 섹션을 chunk로 나눠 `is_chunk=true`로 각 chunk를
  section-driller에 보내고(모든 chunk 1회 이상 방문), chunk 요약을 섹션 단위로 병합.
  Tier L 진입 시 chunk 수를 사용자에게 사전 고지한다(조용한 누락 금지).

빠른 경로(옵션): 명확한 IMRaD 정규식 헤딩이 이미 보이면 spine의 section_boundaries를
그 정규식 결과로 채워 spine 호출을 가볍게 할 수 있다(품질 저하 없으면).

**출력 언어(`output_lang`)**: 사용자 입력 언어를 따른다(기본: 입력이 한국어면 `ko`, 영어면 `en`). orchestrator는 `output_lang`을 paper-spine·paper-section-driller·paper-digest-composer **모든 호출 payload에 포함**한다. 원문 인용·고유명·수치는 언어와 무관하게 원형 보존한다.

---

## Phase C: 병렬 호출 프로토콜

**단일 assistant 메시지에 Agent 툴을 동시 호출.** 모든 섹션 호출에 `spine`을 주입한다.

각 section-driller 호출 payload:
```
doc_id, title, authors?(있으면), output_lang, structure, scholarly, spine(SPINE 블록 전체),
section_id, section_text, section_type?(structure==imrad), is_chunk?, chunk_index?, chunk_total?,
retry_feedback?(선택)
```

호출 구성:
- **Tier S**: 섹션 출력은 이미 spine이 생성 → section-driller fan-out 없음.
- **Tier M/L**: spine.flow_map의 각 section_id마다 section-driller 1회(Tier L은 chunk당 1회).
- **scholarly == yes**일 때 추가:
  - `paper-meta` — `raw_metadata` (메타+BibTeX)
  - `paper-comparison` — `target_paper, candidates(pre-fetch)` (관련문서 있을 때)
- **structure == imrad**일 때 추가:
  - `paper-evidence` — `results_text, method_text, abstract_text, discussion_text, code_links`
- 두 축이 모두 아래값이면(free, no) section-driller만 호출한다.

structure==imrad에서 section-driller의 `section_type`은 spine.flow_map의 IMRaD 매핑을 따르며,
누락되면 에이전트가 오류로 종료한다.

---

## Phase C.5: Section QC Matrix Loop

각 subagent 산출물을 매트릭스로 검증. 실패 항목이 있으면 **해당 agent(및 section agent의 경우 해당 `section_type`)만** `retry_feedback`과 함께 재호출.

| Agent / section_type | 필수 요구사항 |
|---|---|
| paper-section-driller (abstract) | (a) 3-5문장, (b) 선언적 contribution 2-3 bullet, (c) 원문과 일치 |
| paper-section-driller (introduction) | (a) 연구 동기, (b) 기존 한계 2+, (c) RQ/핵심 통찰, (d) `왜 이 연구를 하는가?` 블록 |
| paper-section-driller (method) | (a) 핵심 구성요소, (b) 입출력, (c) 차별점 |
| paper-section-driller (results) | (a) 숫자+출처, (b) 베이스라인 비교, (c) `발견` 블록 |
| paper-section-driller (discussion) | (a) 한계 2+, (b) 향후 방향 1+, (c) 논쟁점/검증 가정/후속, (d) `이론적 의의` |
| paper-meta | (a) 10 메타 필드 전부, (b) BibTeX compile-safe, (c) Category enum 중 하나 |
| paper-evidence | (a) 실험 표 or "불충분" 명시, (b) mmdc 통과 Mermaid, (c) 재현성 종합등급 |
| paper-comparison | (a) 3편+, (b) 7 축 전부, (c) 코드공개 표기 |
| paper-section-driller (free `<<<SECTION:{id}>>>`) | (a) 3-8문장, (b) 첫 문장이 전체 흐름 속 역할 명시, (c) 용어 괄호설명, (d) 원문과 일치 |

> **축 조건**: section_type 행과 `paper-evidence`는 `structure==imrad`일 때만, `paper-meta`·`paper-comparison`은 `scholarly==yes`일 때만 적용한다. `structure==free`면 위 free 행으로 검증하고, 호출되지 않은 agent 행은 건너뛴다(생성되지 않은 산출물에 retry 금지).

**루프 프로토콜**:
1. 각 산출물에 대해 위 매트릭스 자동 체크 (paper-driller 내부 로직).
2. 실패 시 해당 agent를 `retry_feedback=[누락 항목 리스트]`로 **단독 재호출**.
3. 섹션별 **최대 3회** retry. 초과 시 실패 항목을 `qc_warnings`로 composer에 전달 + 최종 파일에 `<!-- QC: {failed_items} -->` 코멘트 삽입.
4. 모든 섹션 통과 → Phase D.

Legacy Claude SubagentStop hook(`paper-driller-subagent-log.sh`)은 Codex에서 자동 실행되지 않는다. 필요하면 Codex 실행 중 직접 `~/.codex/logs/paper-driller-qc.jsonl`에 같은 형식으로 기록해 재시도 패턴을 관찰한다.

---

## Phase D' (Bite mode 전용): Insight-First Single Paragraph

Bite 모드일 때 Phase C.5 통과 후 다음 블록을 조합해 한 문단 요약 생성:

**structure == imrad** (paper 마커 사용):
- `<<<SECTION:abstract>>>` + `<<<CONTRIB:abstract>>>`
- `<<<RATIONALE:why>>>` (Introduction의 motivation)
- `<<<RATIONALE:findings>>>` (Results의 발견)
- `<<<RATIONALE:significance>>>` (Discussion의 이론적 의의)
- `<<<META>>>` 에서 title, arxiv_id, url 필드 추출 (출처 링크용)

**structure == free** (paper 마커·META 없음 — spine.flow_map의 각 `<<<SECTION:{id}>>>` 블록 사용):
- spine.thesis / throughline / audience_frame + 가용한 `<<<SECTION:{id}>>>` 블록들로 서문 구성
- 출처 링크: `scholarly==yes`로 `<<<META>>>` 블록이 있으면 거기서 title/url/DOI를 사용; 없으면 입력 URL, 그것도 없으면 생략

### 출력 구조·작성 규칙

Bite 모드 서문은 **`references/insight-digest-spec.md`를 그대로 따른다** (Context→Insight
→Solution→Evidence + Implication + 출처 링크, 작성 규칙·피해야 할 것·다중 문서 처리 포함).
이 명세는 readable-composer와 공유된다 — 한 곳에서만 진화시킨다.

**Bite 모드는 파일 Write를 하지 않고 chat에 직접 출력한다.** 사용자가 명시적으로 "파일로 저장" 또는 `--bite --write`를 지정하면 `{title}_bite.md`로 저장.

---

## Phase D: Digest Composer

`paper-digest-composer` 에 `doc_id` + `title` + `title_kr` + `output_lang` + `structure` + `scholarly` + `spine` + QC 통과 섹션
블록(structure==imrad이면 evidence, scholarly==yes이면 comparison/meta 포함) + `qc_warnings` 전달. composer는 spine.thesis를 seed로 받아
`references/insight-digest-spec.md`에 따라 readable 서문을 확정하고, 다음을 생성:
- `<<<DIGEST>>>` CISELQ 한 문단
- `<<<ZETTEL>>>` 원자적 인사이트 2-4개
- `<<<GLOSSARY>>>` 핵심 용어 5+
- `<<<TAGS>>>` 태그 3+
- `<<<RELATED_LINKS>>>` Obsidian 링크

**composer는 섹션 요약을 재작성하지 않는다. 파일 Write도 하지 않는다.**

참조: `references/zettelkasten-guide.md`.

---

## Phase E: 템플릿 조립 + Write

paper-driller가 기계적으로 블록을 템플릿 슬롯에 주입하여 `.md` 파일 생성.

**파일명**: 논문 제목 기반 (금지 문자 대체: `:` → ` -`, `/` → `-`, `?*"<>|` 제거). 예: `Alignment Faking in Large Language Models.md`.

**저장 위치(`vault_root` 해석)**: 다음 순서로 `vault_root`를 정한다 — (1) 사용자가 경로를 지정했으면 그것, (2) 환경변수 `PAPER_DRILLER_VAULT`가 있으면 그것, (3) 현재 작업 디렉터리에 `Public/AI/Papers/` 또는 `survey-notes/`가 이미 있으면 CWD, (4) 모두 없으면 **사용자에게 1회 질문**(찾지 못하면 `./paper-notes/`로 임시 저장하고 노트 상단에 경고 주석). 최종 경로: scholarly==yes → `{vault_root}/Public/AI/Papers/[Category]/`, scholarly==no → `{vault_root}/survey-notes/`. 카테고리 폴더 없으면 생성.

**⚠️ 모든 출력 파일은 YAML frontmatter(`---`)로 시작해야 한다.**

### 통합 출력 템플릿

```markdown
---
Reading-Status: "✅ Done"
Author: "[First Author et al.]"
Journal/Conference: "[Venue]"
Published Year: YYYY
Topic: "[Keywords]"
Review-Date: "YYYY-MM-DD"
Comment: "[한줄 요약]"
URL: "[Paper URL]"
arXiv-ID: "[arXiv ID or N/A]"
Category: "[enum]"
Evidence-Quality: "[A/B/C/D]"
Reproducibility: "[A/B/C/D]"
linked-bases: "[[Papers.base]]"
---

# {title_kr}

> **Digest**: {<<<DIGEST>>> 삽입}

---

## 섹션별 요약

### Abstract
{<<<SECTION:abstract>>>}

**저자 contribution**
{<<<CONTRIB:abstract>>>}

### 왜 이 연구를 하는가?
{<<<RATIONALE:why>>>}

### Introduction
{<<<SECTION:introduction>>>}

### Methods
{<<<SECTION:method>>>}

### 발견 (Findings)
{<<<RATIONALE:findings>>>}

### Results
{<<<SECTION:results>>>}

### Discussion
{<<<SECTION:discussion>>>}

{<<<RATIONALE:significance>>>}  <!-- #### 이론적 의의 -->

**Discussion Points**
{<<<DISCUSSION_POINTS>>>}

---

## 실험 결과 상세
{<<<EVIDENCE:table>>>}

## 프레임워크 다이어그램
{<<<EVIDENCE:diagram>>>}

## 재현성 및 신뢰도 평가
{<<<EVIDENCE:reproducibility>>>}

## 관련 연구 비교 매트릭스
{<<<COMPARISON>>>}

---

## 원자적 인사이트 (Zettelkasten)
{<<<ZETTEL>>>}

## 핵심 용어 정리
{<<<GLOSSARY>>>}

## 관련 연구
{<<<RELATED_LINKS>>>}

## 태그
{<<<TAGS>>>}

---

## BibTeX
```bibtex
{<<<BIBTEX>>>}
```
```

### free 프로파일 출력 템플릿 (structure == free)

free 구조에서는 **본문**이 IMRaD 슬롯 대신 spine.flow_map의 실제 섹션을 쓴다. 단, **frontmatter는 저장 경로의 `paper-format-validator` 계약을 따라야 한다**: SCOPE_GLOBS(`Public/AI/Papers/**`·`arxiv-notes/**`·`survey-notes/**`)에 저장되는 모든 노트는 **canonical 15키 frontmatter**를 요구하고 `title`/`author`/`year`/`tags`는 **금지 alias**다(validator는 본문 구조에는 관대 → free 본문은 그대로 허용). 따라서 free 노트도 frontmatter는 통합 템플릿과 동일한 canonical 키를 쓰고 **본문만 free 구조**로 채운다.

- **scholarly==yes** (→ `{vault_root}/Public/AI/Papers/[Category]/`): 아래 canonical frontmatter(통합 출력 템플릿과 동일한 Reading-Status … linked-bases 15키)를 그대로 사용. `Evidence-Quality`·`Reproducibility`는 A/B/C/D 강제이므로 실험 없는 개념/이론·철학 글이면 보수적으로 C/D 부여. `Category`는 enum(Architecture/Training/Benchmark·Evaluation/Application/Reasoning/Survey/Dataset/Optimization/Theory/AGI) 중 하나. `structure: free`·`scholarly: yes`는 추가 키로 보존 가능(금지 alias 아님). `## BibTeX`(`<<<BIBTEX>>>`)를 본문 끝에 덧붙인다.
- **scholarly==no**: SCOPE_GLOBS **밖**(예: 사용자 지정 일반 노트 경로)에 저장하면 경량 frontmatter(아래 주석 처리된 lightweight 예시)를 써도 된다. 단 `survey-notes/`도 SCOPE_GLOBS에 포함되므로 거기에 저장하면 canonical frontmatter가 강제됨에 유의.

frontmatter는 `### 통합 출력 템플릿`의 canonical 블록을 그대로 쓰고(매핑은 아래 **frontmatter 값은 …** 규칙 공유), **본문만** 아래 free 구조로 교체한다:

```markdown
# {title_kr}

> 📌 **한입 요약**
> {<<<DIGEST>>>}

---

## 흐름 따라 읽기

> 논지 흐름(throughline): {spine.throughline}

### {section_id 1 제목}
{<<<SECTION:{id1}>>>}

### {section_id 2 제목}
{<<<SECTION:{id2}>>>}
... (spine.flow_map의 모든 섹션)

---

## 원자적 인사이트 (Zettelkasten)
{<<<ZETTEL>>>}

## 핵심 용어 정리
{<<<GLOSSARY>>>}

## 태그
{<<<TAGS>>>}
```
scholarly==yes면 위 본문 마지막에 `## BibTeX` 코드블록(`<<<BIBTEX>>>`)도 덧붙인다(통합 템플릿과 동일). (lightweight frontmatter — `title`/`title_kr`/`source`/`year`/`tags` — 는 **SCOPE_GLOBS 밖**의 scholarly==no 노트에만 허용; SCOPE_GLOBS 안에서는 절대 금지 — validator가 `title`/`author`/`year`/`tags`를 차단한다.)

**frontmatter 값은 `<<<META>>>` 블록에서 매핑**:
- `Author` ← meta.authors의 first + "et al."
- `Journal/Conference` ← meta.venue
- `Published Year` ← meta.year
- `URL` ← meta.url
- `arXiv-ID` ← meta.arxiv_id
- `DOI` ← meta.doi
- `Category` ← meta.category
- `Evidence-Quality` ← meta.evidence_quality
- `Reproducibility` ← evidence 종합등급
- `Review-Date` ← 오늘 날짜
- `linked-bases` ← 카테고리별 base 파일

---

## Phase F: Hook 검증 + Retry

Write 직후 PostToolUse hook `paper-format-validator.sh`가 자동 실행. stderr에 `FORMAT_VIOLATION in paper summary file:` 포함 시 위반 상태.

**Retry 프로토콜 (최대 3회)**:
1. stderr의 `FRONTMATTER: ...` / `SECTIONS: ...` / `CONTENT: ...` 항목을 파싱.
2. 각 항목 타깃형 Edit:
   - `FRONTMATTER: required key missing: X` → canonical 순서로 추가.
   - `FRONTMATTER: deprecated/alias key` → canonical 매핑 또는 삭제.
   - `FRONTMATTER: Category=... — must be one of ...` → enum 중 가장 가까운 값.
   - `SECTIONS: ... skeleton` → 해당 섹션 블록 복구 (composer 또는 해당 section agent 재호출).
   - `CONTENT: no \`\`\`mermaid block` → evidence agent 재호출.
   - `CONTENT: placeholder pattern` → 실제 내용으로 대체 (composer 재호출).
3. Edit 후 hook 자동 재실행. exit 0이면 성공.
4. 3회 초과 → 사용자에게 stderr + 수동 수정 요청.

**⚠️ hook은 `Public/AI/Papers/**`, `arxiv-notes/**`, `survey-notes/**` 경로에서만 동작**.
비학술(scholarly==no) 노트를 hook 경로 밖에 저장하면 검증을 건너뛴다(의도된 동작 — 논문 전용 검증).

Legacy Claude SubagentStop hook `paper-driller-subagent-log.sh`은 Codex에서 자동 실행되지 않는다. 필요하면 각 agent-style 작업 종료를 `~/.codex/logs/paper-driller-qc.jsonl`에 직접 기록한다.

---

## Phase G: Codex agent 설정 검증 (최초 1회 / 변경 후)

정적 검증: `~/.codex/agents/paper-*.toml` 파일이 존재하고 Claude 모델 alias 없이 필요한 `model_reasoning_effort`만 포함하는지 확인한다.

런타임 검증(샘플 1편): 병렬 실행을 명시적으로 요청한 경우 각 역할이 기대한 출력 블록을 반환하는지 확인한다. Codex subagent 활동 로그나 `/agent` 화면은 역할 종료와 요약 확인용으로만 사용한다.

---


## 품질 체크리스트 (최종)

> 아래는 **imrad + scholarly 완전형** 기준이다. `structure==free`면 IMRaD 하위(Abstract/Introduction/Methods/Results/Discussion)·rationale·실험표·Mermaid·재현성·비교매트릭스 항목을 건너뛰고 `흐름 따라 읽기`의 모든 섹션·Digest·인사이트·용어·태그만 확인한다. `scholarly==no`면 BibTeX·비교매트릭스·`Public/AI/Papers/` 경로 항목을 생략하고 `survey-notes/` 저장으로 확인한다.

- [ ] frontmatter가 canonical 순서로 완전
- [ ] Digest가 CISELQ 6요소 전부, 전문용어 괄호 설명, 숫자+출처
- [ ] `섹션별 요약` 블록에 Abstract/Introduction/Methods/Results/Discussion 5개 하위 모두
- [ ] rationale 블록 3개(`왜 이 연구를 하는가?` / `발견` / `이론적 의의`)가 대응 섹션에 인접
- [ ] Discussion Points 3개 카테고리 전부
- [ ] 실험 표 또는 "데이터 불충분" 명시
- [ ] Mermaid 블록 mmdc 통과
- [ ] 재현성 종합등급 A/B/C/D 부여
- [ ] 주장별 신뢰도 2+
- [ ] 비교 매트릭스 3편+
- [ ] 원자적 인사이트 2+, 자기설명적
- [ ] 핵심 용어 5+ (논문 기본 용어 포함)
- [ ] 태그 3+
- [ ] 파일 `Public/AI/Papers/{Category}/` 에 저장

**미충족 시**: 해당 agent/composer를 targeted 재호출 또는 Edit으로 수정 후 재검증.

---

## 카테고리 분류 기준

| 카테고리 | 키워드 |
|---|---|
| Memory | memory, test-time learning, context, retrieval, RAG |
| Skill_LM | reward, RL, RLHF, self-improvement, exploration, skill |
| Meta-cognition | consciousness, self-awareness, metacognition, introspection |
| (새) | 위에 해당 안 되면 주제로 새 폴더 생성 |

---

## References

- `references/section-summary-best-practices/{abstract,introduction,method,results,discussion,meta,evidence,comparison}.md` — 섹션별 요약 best practices (agent 프롬프트 내부 참조)
- `references/reproducibility-rubric.md` — 재현성 평가 기준
- `references/comparison-matrix-guide.md` — 비교 매트릭스 가이드
- `references/zettelkasten-guide.md` — 원자적 인사이트 가이드
- `references/insight-digest-spec.md` — readable 서문 단일 명세(Bite 모드 + composer 공유)
- `scripts/validate-driller.sh` — frontmatter·참조 정적 검증 하버스

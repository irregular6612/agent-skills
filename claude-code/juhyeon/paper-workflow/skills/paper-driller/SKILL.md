---
name: paper-driller
description: >-
  논문을 읽기 전 사용하는 근거 추적 가능한 프리리드 요약을 기본 생성한다. 명시적으로 요청받은 경우에만 섹션별 deep note를 만든다. TRIGGERS: 논문 요약, paper drill, arxiv 정리, 논문 노트, 논문 읽기 전 요약, deep paper analysis
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

# Paper Driller v2

## 목적

기본 산출물은 논문을 대신하는 장문 해설이 아니다. 독자가 원문을 읽기 전에 문제·핵심 아이디어·주요 근거·한계·읽을 위치를 빠르게 파악하는 **프리리드 요약**이다.

- `--mode preread|deep`
- **기본값: preread**
- `deep`은 사용자가 심층 독해 노트나 섹션별 분석을 명시적으로 요청한 경우에만 사용한다.

기계 판독 스키마의 단일 진실 원천은 `references/paper-schema.json`이다. Category·profile·source coverage·preread 필수 섹션 enum을 다른 문서에 별도로 복제하지 않는다. 출력 의도와 편집 원칙은 `references/preread-v2-spec.md`, 정확성 보존형 쉬운 설명 규칙은 `references/readability-spec.md`, deep 모드의 장문 digest 규칙은 `references/insight-digest-spec.md`를 따른다.

## 핵심 편집 원칙

1. **원문을 대신하지 않는다.** 정밀한 수식·증명·실험 설정은 reading map으로 원문에 연결한다.
2. **원문 순서보다 독자 질문 순서로 재구성한다.** 문제 → 아이디어 → 수행 내용 → 근거 → 한계 → 읽기 지도.
3. **중복을 제거한다.** Digest·먼저 이해하기·Abstract를 별도 반복하지 않는다.
4. **근거를 추적한다.** 핵심 주장에는 Table/Figure/Section 또는 coverage 한계를 붙인다.
5. **기본은 짧게, 상세는 요청 시에만.** Zettelkasten·거대 비교표·섹션별 요약은 deep 전용이다.

## 프로파일

`structure`와 `scholarly`에 더해 `profile`을 판정한다.

| profile | 판정 | 핵심 검증 대상 |
|---|---|---|
| `empirical` | 실험·관찰 중심 | 데이터, 조건, baseline, metric, 부정 결과 |
| `theoretical` | 정리·증명·구성 중심 | 가정, 증명 전략, 정리의 적용 범위 |
| `survey` | 문헌 분류·종합 중심 | 조사 범위, taxonomy, 포함·제외 기준 |
| `position` | 주장·논증 중심 | 핵심 주장, 근거 종류, 반론 |
| `dataset-benchmark` | 데이터셋·평가체계 중심 | 생성, split, metric, baseline, 누출·편향 |
| `general-article` | 비학술 일반 글 | 논증 흐름, 출처, 핵심 사례 |

기존 2축도 유지한다.

- `structure`: `imrad` | `free`
- `scholarly`: `yes` | `no`

사용자는 `--mode`, `--profile`, `--structure`, `--scholarly`를 override할 수 있다.

## Agent 구성

| Agent | preread | deep | 책임 |
|---|---:|---:|---|
| `paper-preread-analyst` | **필수·1회** | 생략 | 읽기 판정, 핵심 아이디어, 수행 내용, claim ledger, 한계, reading map을 한 번에 생성 |
| `paper-spine` | 생략 | 필수 | 상세 독해용 전체 논지·flow map |
| `paper-meta` | 생략 | 선택 | deep에서 metadata 보정이 필요한 경우만 사용 |
| `paper-evidence` | 생략 | 필수 | deep claim/evidence·재현성 감사 |
| `paper-digest-composer` | 생략 | 필수 | deep 산출물 합성 |
| `paper-section-driller` | 생략 | 필요 | deep 섹션별 상세 독해 |
| `paper-comparison` | 생략 | 선택 | deep 관련 연구 비교 매트릭스 |

**기본 subagent 호출 예산: 1회**다. 핵심 수치 충돌, low-confidence 핵심 claim, 사용자 `--verify|--repro` 요청에만 같은 analyst를 제한된 payload로 한 번 더 호출한다. preread는 최대 2회이며 section fan-out·별도 meta/evidence/composer 호출을 금지한다. metadata와 BibTeX는 수집 결과를 orchestrator가 결정론적으로 매핑한다.

## Workflow

### preread — 기본

```text
입력
  ↓
A. metadata + 판단에 필요한 핵심 구간 수집, source coverage 판정
  ↓
B. paper-preread-analyst 1회
  ↓
C. 결정론적 frontmatter/BibTeX 매핑 + 템플릿 조립
  ↓
D. paper-format-validator
  ↓
E. Wiki Integration
```

### deep — 명시 요청 전용

```text
전체 수집 → paper-spine → section/evidence/meta/comparison → composer
→ 템플릿 조립 → validator → Wiki Integration
```

# Phase A — 수집·정규화

## Fetch fallback

1. arXiv: `mcp__arxiv__download_paper` + `mcp__arxiv__read_paper`
2. Semantic Scholar metadata/abstract
3. paper-search MCP
4. `WebFetch` arXiv HTML
5. 제목 기반 `WebSearch`

PDF URL에서 WebFetch가 전문 대신 **캐시된 PDF** 경로를 반환하면 orchestrator가 해당 로컬 경로를 `Read(pages=…)`로 읽는다. cross-host `redirect`가 나오면 안내 URL로 다시 호출한다.

preread는 페이지 수와 무관하게 먼저 다음 구간만 수집한다.

1. metadata + abstract
2. Introduction의 contribution 단락
3. method overview 또는 핵심 Figure caption
4. 대표 결과 Table/Figure와 주변 문단
5. limitations/discussion/conclusion
6. 목차·heading·page locator

판정·claim·reading map을 만들기에 부족할 때만 추가 구간을 읽는다. deep에서만 10쪽 초과 PDF를 page range로 나눠 전체를 방문한다.

## Source coverage

확보 범위를 다음 중 하나로 기록한다.

- `fulltext`
- `section-extract`
- `abstract-only`
- `unknown`

`abstract-only` 또는 `unknown`이면:

- 방법·결과 세부를 추측하지 않는다.
- `quality-status: review`를 emit한다.
- ONE_MINUTE와 KEY_EVIDENCE에서 coverage 한계를 알린다.

`output_lang`은 사용자 입력 언어를 따르며 모든 agent payload에 포함한다. 고유명·수식·수치·원문 식별자는 보존한다.

# Phase B — Preread analyst

`mode=preread`이면 `paper-preread-analyst`를 정확히 1회 호출한다. 다음을 한 호출에서 생성한다.

```text
READING_DECISION, ONE_MINUTE, CORE_IDEA, WHAT_THEY_DID,
KEY_EVIDENCE, LIMITS, READING_MAP, TERMS?, CONTEXT_LINKS?
```

claim ledger:

```text
claim | source_location | observation | condition_or_caveat | claim_origin
```

`claim_origin`은 다음 enum만 사용한다.

```text
author-stated | analyst-inference | unknown
```

- 원문 명시 내용과 분석자의 해석을 섞지 않는다.
- 최대 5개 claim만 남긴다.
- locator가 없으면 `[위치 미확인]`으로 쓴다.
- `abstract-only|unknown`에서는 방법·수치·위치를 추측하지 않는다.
- 같은 claim의 완전한 서술은 한 곳에 한 번만 둔다.
- READING_MAP은 2–4행, TERMS는 최대 3개다.

`paper-preread-analyst`가 반환한 marker를 orchestrator가 순서대로 조립한다. 별도 composer가 문장을 다시 생성하지 않는다.

# Phase C — Deep 분기

`mode=deep`에서만 legacy 상세 agent 경로를 사용한다.

1. `paper-spine`: profile·thesis·flow map·argument map
2. 긴 원문은 `paper-section-driller`로 실제 chunk를 방문
3. `paper-evidence`: 상세 claim/evidence·재현성 감사
4. `paper-meta`: metadata 보정이 필요한 경우만
5. `paper-comparison`: 비교가 실제로 필요한 경우만
6. `paper-digest-composer`: 중복 제거 후 deep note 합성

Deep에서도 모든 원문 heading을 기계적으로 재서술하지 않는다. Zettelkasten·Mermaid·비교표는 독해 후 재사용 가치가 있을 때만 생성한다.

# Phase D — 출력

## canonical frontmatter

모든 학술 논문은 `type: paper`를 첫 키로 emit한다. 기존 Wiki 계약은 유지하고 v2 식별 필드를 추가한다.

```yaml
---
type: paper
template-version: paper-preread-v2
summary-mode: preread
profile: empirical
source-coverage: fulltext
quality-status: ready
reading-decision: read
decision-confidence: high
Reading-Status: "☑️ Not Started"
Author: "First Author et al."
Journal/Conference: "Venue"
Published Year: 2026
Topic: "keywords"
Review-Date: "YYYY-MM-DD"
Comment: "문제·아이디어·결과·한계를 포함한 한 문장"
URL: "https://..."
arXiv-ID: "N/A"
DOI: "N/A"
Evidence-Quality: "A"
Reproducibility: "B"
Category: "Reasoning"
isTargetPaper: false
linked-bases: "[[Papers.base]]"
---
```

공통 13키는 기존 validator 계약을 따른다. **AI 전용** 키 `Category`, `isTargetPaper`, `linked-bases`는 `Public/AI/` 아래에서만 필수다. 비-AI 논문에는 AI 전용 키를 생략한다.

## preread 본문 템플릿

````markdown
# {title_kr}

{<<<READING_DECISION>>>}

{<<<ONE_MINUTE>>>}

{<<<CORE_IDEA>>>}

{<<<WHAT_THEY_DID>>>}

{<<<KEY_EVIDENCE>>>}

{<<<LIMITS>>>}

{<<<READING_MAP>>>}

{<<<TERMS>>>}

{<<<CONTEXT_LINKS>>>}

## BibTeX
```bibtex
{<<<BIBTEX>>>}
```
````

## deep 본문 템플릿

preread 블록을 맨 앞에 유지한 뒤 `## 상세 독해 노트` 아래에 실제로 필요한 섹션만 추가한다. 원문 모든 heading을 기계적으로 복제하지 않는다. Zettelkasten과 상세 비교표는 재사용 가치가 있을 때만 추가한다.

## free 프로파일 출력 템플릿

`structure=free, scholarly=yes`도 canonical paper frontmatter를 유지한다. 본문은 preread 템플릿을 그대로 쓰며 IMRaD heading을 강제하지 않는다. `scholarly=no` 일반 글은 `type: paper`를 사용하지 않고 사용자가 지정한 일반 노트 경로에 저장한다.

## 경로

`vault_root` 결정 순서:

1. 사용자 지정
2. `PAPER_DRILLER_VAULT`
3. CWD에 `Public/`이 있으면 CWD
4. 모두 없으면 사용자에게 경로 확인

`destination`은 vault_root 상대 경로다.

- AI 논문: `Public/AI/Papers/`
- 비-AI 논문: `Public/{domain}/`
- Category 하위 폴더를 새로 만들지 않는다.

동일 DOI/arXiv-ID/정규화 URL이 있으면 새 파일을 만들지 않고 `update-existing`으로 전환한다. 재실행 시 사용자 필드와 개인 메모를 보존한다.

# Phase E — Format 검증

Write 직후 `paper-format-validator.sh`를 통과해야 한다. 위반 시 최대 3회 타깃 수정한다.

- frontmatter 누락/alias/category
- H1 또는 실질 본문 누락
- placeholder
- source coverage와 quality-status 불일치

정적 검증:

```bash
bash skills/paper-driller/scripts/validate-driller.sh
```

# Phase F — Wiki Integration

파일 작성만으로 완료하지 않는다.

1. 중복 DOI/arXiv-ID 재확인
2. `linked-bases` 파일 존재 확인
3. 관련 기존 노트 1–3개 연결
4. `python3 Public/_tools/build_catalog.py` 실행
5. 대상 catalog에 새 행이 생겼는지 확인
6. `python3 Public/_tools/lint.py` 실행
7. 새 오류가 없으면 `_wiki/log.md`에 기록

기존 사용자 내용은 보존한다. 자동 재생성이 필요한 경우 다음 블록 경계를 권장한다.

```text
<!-- BEGIN AUTO:preread -->
...
<!-- END AUTO:preread -->

<!-- BEGIN USER:notes -->
...
<!-- END USER:notes -->
```

# 품질 게이트

## preread

- [ ] `read|skim|skip` 판정과 confidence가 있음
- [ ] problem, idea, evidence, limitation, reading map이 모두 있음
- [ ] 핵심 수치마다 출처 위치 또는 `[위치 미확인]`
- [ ] 모든 claim이 `author-stated|analyst-inference|unknown`으로 구분됨
- [ ] source-coverage가 실제 확보 범위와 일치
- [ ] 본문 non-whitespace 길이가 schema 상한 이내
- [ ] Digest/Abstract/쉬운 설명이 별도 반복되지 않음
- [ ] Findings/Results/실험표가 중복되지 않음
- [ ] Discussion/이론적 의의/Discussion Points가 중복되지 않음
- [ ] 원문을 읽을 목적과 위치가 구체적
- [ ] 기본 subagent 1회, 조건부 재검증 포함 최대 2회
- [ ] catalog와 lint 검증 완료

## deep

- [ ] 사용자가 deep을 명시적으로 요청함
- [ ] 상세 섹션이 단순 재서술이 아니라 독해·재사용 가치를 가짐
- [ ] profile에 맞지 않는 실험·재현성 항목을 강제하지 않음

## References

- `references/preread-v2-spec.md` — 기본 출력·길이·중복 규칙
- `references/readability-spec.md` — 정확성 보존형 쉬운 설명
- `references/insight-digest-spec.md` — deep digest
- `references/zettelkasten-guide.md` — deep 원자적 인사이트
- `references/reproducibility-rubric.md` — deep 재현성 평가
- `references/comparison-matrix-guide.md` — deep 비교표
- `scripts/validate-driller.sh` — 정적 계약 검증

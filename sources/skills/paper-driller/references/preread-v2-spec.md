# Paper Driller v2 — Pre-read Summary Specification

## Purpose

기본 산출물은 논문을 대체하는 장문 해설이 아니다. 독자가 원문을 읽기 전에 다음을 빠르게 결정하도록 돕는 **5–8분 분량의 프리리드 요약**이다.

1. 이 논문이 어떤 문제를 푸는가?
2. 핵심 아이디어는 무엇인가?
3. 무엇을 실제로 했고 어떤 근거를 제시했는가?
4. 어디까지 믿을 수 있으며 무엇은 아직 모르는가?
5. 원문을 읽는다면 어디를 먼저 봐야 하는가?

원문의 섹션을 순서대로 재서술하지 않는다. 원문을 읽지 않아도 된다는 인상을 만들지 않으며, 정밀한 수식·증명·실험 설정은 reading map을 통해 원문으로 안내한다.

## Audience (고정)

독자는 하나다. **이 분야를 처음 보는 똑똑한 사람**(고등학생, 타분야 대학생). 난이도 옵션은 없다.
문장 길이·괄호 설명·비유·문체 규칙은 `readability-spec.md`가 단일 원천이다. 이 문서는 블록 구조와 중복 규칙만 정한다.
전문가용 밀도는 KEY_EVIDENCE·READING_MAP 표가 담당한다. 서술 블록은 쉽게, 표 블록은 정확하게.

## Modes

- `preread` — 기본. 5–8분 분량의 의사결정·방향잡기용 요약.
- `deep` — 명시적으로 요청받았을 때만. 섹션별 분석, 상세 비교, Zettelkasten, 다이어그램까지 포함할 수 있다.

## Default Output Contract

```text
READING_DECISION
ONE_MINUTE
CORE_IDEA
WHAT_THEY_DID
KEY_EVIDENCE
LIMITS
READING_MAP
TERMS
CONTEXT_LINKS
```

### 0. READING_DECISION

`read | skim | skip` 중 하나와 `high | medium | low` confidence를 제시한다. 이유는 **독자 적합성만** 1–2문장으로 적는다("X를 연구하면 read, Y가 목적이면 skim"). 문제·수치·한계를 여기서 다시 쓰지 않는다. source coverage 부족은 논문 품질이 아니라 판정 confidence를 낮추는 요인으로 처리한다.

### 1. ONE_MINUTE

4–6개 bullet만 사용한다.

- `문제` — 연구가 다루는 gap 또는 질문
- `핵심 아이디어` — 방법 이름이 아니라 작동 원리
- `주요 결과` — 가장 중요한 증거 1–2개
- `핵심 한계` — 결론의 적용 범위를 제한하는 조건
- `읽을 가치` — 어떤 독자에게 왜 유용한가

Digest, plain explanation, abstract summary를 별도로 반복하지 않는다.

bullet마다 한 문장. **locator(Table/Figure/App.)와 숫자를 쓰지 않는다.** 결론만 쓰고 근거는 KEY_EVIDENCE에 둔다. `핵심 아이디어` bullet은 방법 이름과 원리 한 구절이지 메커니즘 전체가 아니다.

### 2. CORE_IDEA

2–4개 짧은 문단. 다음 순서를 따른다.

```text
"이 논문은 X를 Y로 푼다" 한 문장 → 비유 정확히 1개 → 작동 원리(병목 → 통찰 → 구현) → 누구에게 왜 쓸모인지
```

3–4문단. 비유는 정확히 하나이고 뒤에 정확한 용어로 되돌아온다. 기술 용어는 보존하고 첫 등장에 괄호 설명을 붙인다. anchor·데이터셋·baseline의 구체명은 여기서 나열하지 않고 일반명사("사람이 매긴 정답지")로 쓴다. 구체명은 WHAT_THEY_DID에서 한 번.

### 3. WHAT_THEY_DID

프로파일에 맞춰 3–6개 bullet 또는 하나의 작은 다이어그램으로 표현한다.

- empirical: 데이터, 비교 조건, 방법, 평가 지표
- theoretical: 가정, 구성 또는 증명 전략, 정리의 범위
- survey: 조사 범위, taxonomy 축, 포함·제외 기준
- position: 핵심 논증, 근거 종류, 주요 반론
- dataset-benchmark: 데이터 생성, split, metric, baseline

섹션별 요약은 만들지 않는다. bullet 앞에 "왜 이걸 했나" 한 구절을 붙인다. 데이터셋·anchor·baseline 구체명의 완전 서술 자리는 이 블록이다.

### 4. KEY_EVIDENCE

최대 5개의 claim ledger 행을 사용한다.

| 주장 | 근거 위치 | 관찰/수치 | 조건·주의 | claim_origin |
|---|---|---|---|---|

- `claim_origin`은 `author-stated | analyst-inference | unknown` 중 하나다.
- 원문 명시 내용과 분석자의 해석을 섞지 않는다.
- 모든 정량 주장에 Table/Figure/Section 위치 또는 `[위치 미확인]`을 붙인다.
- 같은 수치를 ONE_MINUTE, CORE_IDEA, KEY_EVIDENCE에서 장문으로 반복하지 않는다.
- ONE_MINUTE에는 결론만, ledger에는 추적 가능한 상세만 둔다.
- 근거가 abstract-only이면 이를 명시한다.

### 5. LIMITS

세 범주와 출처 경계를 구분한다.

- `저자가 인정한 한계` — `author-stated`
- `분석자의 해석·우려` — `analyst-inference`
- `읽지 못했거나 확인할 수 없는 범위` — `unknown`

Discussion, theoretical significance, discussion points, reproducibility를 별도 장문 섹션으로 반복하지 않는다. 재현성 정보는 결론에 영향을 줄 때 여기에 합친다.

**빠뜨리면 안 되는 두 줄.** empirical·dataset-benchmark profile에서는 (1) 실험 반복 횟수(seed 수, 조건당 run 수)와 (2) 코드·데이터 공개 여부를 LIMITS 어딘가에 반드시 한 줄씩 쓴다. 원문에 없으면 "보고되지 않았다"로 쓴다. 중복 제거 규칙은 "한 번만"이지 "0번"이 아니다. 2026-09-05 dry-run에서 이 두 줄이 통째로 빠진 사례가 있었다.

### 6. READING_MAP

원문을 실제로 읽게 만드는 가장 중요한 블록이다.

| 읽는 목적 | 먼저 볼 곳 | 확인할 질문 |
|---|---|---|

2–4행. Section/Table/Figure 번호를 가능한 범위에서 정확히 적는다. 원문 위치를 확인할 수 없으면 `[위치 미확인]`으로 표기한다.

### 7. TERMS

최대 3개. 3단 정의: 일상어 한 줄 → 정확한 정의 → 이 논문에서 왜 중요한가. **본문에 이미 괄호 설명이 있는 용어는 넣지 않는다.** 용어 정의 자리는 본문 괄호 또는 TERMS 중 하나다. `먼저 알아둘 말`과 `핵심 용어 정리`를 이 목록 하나로 합친다.

### 8. CONTEXT_LINKS

최대 5개. 거대한 관련 연구 비교표를 기본 생성하지 않는다.

- 기반 연구
- 직접 선행 또는 후속
- 경쟁 접근

각 링크에 연결 이유를 한 문장으로 쓴다. 상세 7축 비교 매트릭스는 `deep` 모드에서만 생성한다.

## Length Budget

frontmatter와 BibTeX를 제외한 기본 본문 목표는 대략 2,500–5,000자이며, non-whitespace **5,500자**를 hard limit으로 사용한다. 초과할 때는 다음 순서로 줄인다.

1. 중복 설명 삭제
2. 배경·관련연구 축약
3. 보조 수치 삭제
4. 선택적 용어 삭제
5. 상세 절차를 reading map으로 이동

핵심 한계, 수치의 조건, source coverage는 삭제하지 않는다.

## Duplication Rules

다음 쌍은 기본 모드에서 동시에 만들지 않는다.

| 기존 블록 | v2 처리 |
|---|---|
| Digest + 먼저 이해하기 + Abstract | ONE_MINUTE + CORE_IDEA로 병합 |
| 왜 이 연구를 하는가 + Introduction | CORE_IDEA 첫 부분으로 병합 |
| 발견 + Results + 실험 결과 상세 | KEY_EVIDENCE ledger로 병합 |
| Discussion + 이론적 의의 + Discussion Points | LIMITS로 병합 |
| 먼저 알아둘 말 + 핵심 용어 정리 | TERMS로 병합 |
| 비교 매트릭스 + 관련 연구 | CONTEXT_LINKS로 병합 |
| 원자적 인사이트 | 기본 생략; deep 또는 사후 독해 단계에서 생성 |
| Mermaid | 작동 원리 이해에 실제 도움이 될 때만 1개 |

v2 블록끼리도 역할을 나눈다. 정보 종류마다 **완전 서술 자리는 하나**이고 다른 블록에서는 이름이나 한 구절로만 가리킨다.

| 정보 종류 | 완전 서술 자리 | 다른 블록에서는 |
|---|---|---|
| 작동 원리 | CORE_IDEA | 방법 이름 + 한 구절 |
| 수치·실험 조건 | KEY_EVIDENCE | 결론만, 숫자 금지 |
| 한계 상세·표본 크기 | LIMITS | 한 구절. 수치는 `C1`처럼 행 번호로 참조 |
| 데이터셋·anchor·baseline 이름 | WHAT_THEY_DID | 일반명사 |
| 용어 정의 | 본문 괄호 **또는** TERMS, 둘 중 하나 | - |
| 판정 이유 | READING_DECISION | - |

frontmatter `Comment`는 80자·2문장 이내다. 문제 한 구절 + 결과 한 구절. ONE_MINUTE를 복제하지 않는다.

## Source Coverage

다음 값을 frontmatter에 남긴다.

- `fulltext` — 전문 전체를 읽음
- `section-extract` — 주요 섹션만 확보
- `abstract-only` — 초록과 메타만 확보
- `unknown` — 확보 범위를 검증하지 못함

`abstract-only`에서는 방법·결과의 세부를 추측하지 않는다. `quality-status: review`로 기록하고 KEY_EVIDENCE에 근거 부족을 명시한다.

## Default Execution Budget

preread는 `paper-preread-analyst` 단일 호출로 분석과 편집을 끝낸다. metadata/BibTeX는 수집된 필드를 결정론적으로 매핑한다. 별도 spine·meta·evidence·composer·section fan-out은 deep 전용이다.

- 기본 subagent: 1회
- 핵심 수치 충돌, low-confidence 핵심 claim, `--verify|--repro`: 같은 analyst 1회 추가 가능
- retry 포함 최대: 2회
- `--humanize`: validator 통과 후 `humanize` 스킬(KO Fast, `humanize-ko-monolith` 1회)을 서술 블록에만 적용한다. 이 호출은 위 2회 예산에 세지 않는다. 표 블록·frontmatter·BibTeX는 넘기지 않는다.

## Completion Criteria

- READING_DECISION에 read|skim|skip 판정과 confidence가 있다.
- ONE_MINUTE만 읽어도 문제·아이디어·결과·한계를 구분할 수 있다.
- 핵심 주장마다 원문의 위치 또는 coverage 한계가 있다.
- 모든 claim의 원문/분석자/미확인 경계가 표시된다.
- 같은 주장이나 수치의 완전한 서술은 한 번만 있다.
- 원문을 읽을 위치와 확인 질문이 READING_MAP에 있다.
- 본문이 5,500 non-whitespace chars 이하이다.
- 서술 블록의 문장이 15어절 이하이고, 첫 등장 용어에 괄호 설명이 있다(`readability-spec.md`).
- CORE_IDEA가 "무엇 → 비유 1개 → 원리 → 쓸모" 순서다.
- 같은 수치가 두 블록에 나오지 않는다. ONE_MINUTE에 locator가 없다.
- 프리리드 요약이 논문의 대체물이라고 주장하지 않는다.

# Paper Driller v2 — Pre-read Summary Specification

## Purpose

기본 산출물은 논문을 대체하는 장문 해설이 아니다. 독자가 원문을 읽기 전에 다음을 빠르게 결정하도록 돕는 **5–8분 분량의 프리리드 요약**이다.

1. 이 논문이 어떤 문제를 푸는가?
2. 핵심 아이디어는 무엇인가?
3. 무엇을 실제로 했고 어떤 근거를 제시했는가?
4. 어디까지 믿을 수 있으며 무엇은 아직 모르는가?
5. 원문을 읽는다면 어디를 먼저 봐야 하는가?

원문의 섹션을 순서대로 재서술하지 않는다. 원문을 읽지 않아도 된다는 인상을 만들지 않으며, 정밀한 수식·증명·실험 설정은 reading map을 통해 원문으로 안내한다.

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

`read | skim | skip` 중 하나와 `high | medium | low` confidence를 제시한다. 판정 이유와 추천 독자를 1–2문장으로 적는다. source coverage 부족은 논문 품질이 아니라 판정 confidence를 낮추는 요인으로 처리한다.

### 1. ONE_MINUTE

4–6개 bullet만 사용한다.

- `문제` — 연구가 다루는 gap 또는 질문
- `핵심 아이디어` — 방법 이름이 아니라 작동 원리
- `주요 결과` — 가장 중요한 증거 1–2개
- `핵심 한계` — 결론의 적용 범위를 제한하는 조건
- `읽을 가치` — 어떤 독자에게 왜 유용한가

Digest, plain explanation, abstract summary를 별도로 반복하지 않는다.

### 2. CORE_IDEA

2–4개 짧은 문단. 다음 순서를 따른다.

```text
기존 접근의 병목 → 저자의 통찰 → 통찰이 방법으로 구현되는 방식
```

비유는 필요할 때 하나만 사용한다. 기술 용어는 보존하고 첫 등장에 짧게 설명한다.

### 3. WHAT_THEY_DID

프로파일에 맞춰 3–6개 bullet 또는 하나의 작은 다이어그램으로 표현한다.

- empirical: 데이터, 비교 조건, 방법, 평가 지표
- theoretical: 가정, 구성 또는 증명 전략, 정리의 범위
- survey: 조사 범위, taxonomy 축, 포함·제외 기준
- position: 핵심 논증, 근거 종류, 주요 반론
- dataset-benchmark: 데이터 생성, split, metric, baseline

섹션별 요약은 만들지 않는다.

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

### 6. READING_MAP

원문을 실제로 읽게 만드는 가장 중요한 블록이다.

| 읽는 목적 | 먼저 볼 곳 | 확인할 질문 |
|---|---|---|

2–4행. Section/Table/Figure 번호를 가능한 범위에서 정확히 적는다. 원문 위치를 확인할 수 없으면 `[위치 미확인]`으로 표기한다.

### 7. TERMS

최대 3개. 해당 요약을 이해하는 데 필요한 용어만 둔다. `먼저 알아둘 말`과 `핵심 용어 정리`를 이 목록 하나로 합친다.

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

## Completion Criteria

- READING_DECISION에 read|skim|skip 판정과 confidence가 있다.
- ONE_MINUTE만 읽어도 문제·아이디어·결과·한계를 구분할 수 있다.
- 핵심 주장마다 원문의 위치 또는 coverage 한계가 있다.
- 모든 claim의 원문/분석자/미확인 경계가 표시된다.
- 같은 주장이나 수치의 완전한 서술은 한 번만 있다.
- 원문을 읽을 위치와 확인 질문이 READING_MAP에 있다.
- 본문이 5,500 non-whitespace chars 이하이다.
- 프리리드 요약이 논문의 대체물이라고 주장하지 않는다.

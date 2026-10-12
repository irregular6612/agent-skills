# Critic Review Protocol

이 문서는 Phase 3a Critic의 **단일 평가 기준**이다. `SKILL.md`와
`agents/academic-reviewer.md`에는 평가표를 복사하지 않는다. Critic은 평가 전에 이
파일 전체를 읽고, 문서 유형에 맞는 추가 가이드도 읽는다.

## 목차

- 적용 규칙
- 25 Principles
- Issue Classification
- Document-Type Additions
- Insight Narrative Score
- Critic Prompt Template
- Required Output
- Output Rules

## 적용 규칙

- 요청 언어의 자연스러운 학술 문체를 평가한다. 한국어는 번역체를, 영어는 부자연스러운
  직역과 비관용적 표현을, 그 밖의 언어는 해당 언어의 학술 관습을 점검한다.
- Abstract, Introduction, Results, Discussion 같은 **서술 본문**은 문단으로 작성한다.
  다만 학회가 요구하는 contribution 요약, Methods의 포함·제외 기준과 재료 목록,
  제안서의 일정·milestone, 표·알고리즘·부록처럼 구조화가 더 정확한 부분은 목록을
  허용한다.
- CI·표준오차 같은 불확실성은 표본이나 반복 실행에서 추정한 결과처럼 변동성이 중요한
  값에 요구한다. 표본 수, 하이퍼파라미터, 정확한 개수, 정의상 고정된 값에는 요구하지
  않는다. 어떤 불확실성 지표를 쓸지는 연구 설계와 분야 관례에 맞춘다.
- 초안에 남아 있는 미검증 주장과 미검증 인용은 Warning이 아니라 C1이다. 출처가
  검증되었지만 서지정보가 불완전한 경우만 W1로 분류한다.

## 25 Principles

### Factual Accuracy — highest priority

| ID | Principle | Violation |
| --- | --- | --- |
| FA1 | Fact-based claims | Claim is neither verified nor admissible user-attested information in the Fact Base |
| FA2 | No invented numbers | Metric or statistic has no admissible Fact Base source |
| FA3 | Verified citations | Cited work or attributed finding was not checked against a reliable source |

### Structure

| ID | Principle | Violation |
| --- | --- | --- |
| ST1 | Topic-first | Paragraph starts with background instead of its main claim |
| ST2 | Purpose-driven opening | Section does not state why it exists |
| ST3 | Implication-focused closing | Section ends without significance |
| ST4 | Figure/table reference | Visual is used without an in-text reference |

### Understandability

| ID | Principle | Violation |
| --- | --- | --- |
| UN1 | Definition-first | A technical term is used before an explicit definition |
| UN2 | Compare-contrast | A new approach is not compared with relevant alternatives |
| UN3 | Smart-but-unfamiliar | An informed non-specialist cannot understand why a choice was made |
| UN4 | Coherent flow | Logical connection between paragraphs is missing |

### Format

| ID | Principle | Violation |
| --- | --- | --- |
| FM1 | Conciseness | Unnecessary modifiers such as 매우, very, or extremely |
| FM2 | Specific numbers | A vague quantifier is used where a specific value is available |
| FM3 | Prose where prose is expected | A narrative section uses bullets without a genre or venue reason |
| FM4 | Abstract-level | File paths or function names are exposed in prose |
| FM5 | Statistical uncertainty | An estimated result omits appropriate uncertainty when variability matters |

### Naturalness

| ID | Principle | Violation |
| --- | --- | --- |
| NL1 | Language-natural phrasing | The requested language contains translationese or non-idiomatic academic phrasing |
| NL2 | No overstatement | Rhetoric is stronger than the evidence |
| NL3 | One main idea per sentence | A sentence compresses too many independent ideas |
| NL4 | No word repetition | The same word repeats in adjacent sentences |
| NL5 | Non-mechanical transitions | The same connector pattern is repeated mechanically |

### Insight

| ID | Principle | Violation |
| --- | --- | --- |
| IS1 | Motivation-before-method | A method appears without explaining why it is needed |
| IS2 | Cause-and-effect chain | Steps are listed without causal reasoning |
| IS3 | Concrete instantiation | An abstract concept lacks a useful example or concrete case |
| IS4 | Document-level insight arc | The section lacks a Context→Insight→Solution→Evidence arc where appropriate |

## Issue Classification

### Critical — blocks completion

| ID | Issue | Principle | Score 0 | Score 1 | Score 2 |
| --- | --- | --- | --- | --- | --- |
| C1 | Unsupported claim, invented number, or unverified citation | FA1/FA2/FA3 | 발견 | 없음 | n/a |
| C2 | Fact contradiction | FA1 | 발견 | 없음 | n/a |
| C3 | Topic-first violation | ST1 | 배경/일반론으로 시작 | 배경 후 주장 | 첫 문장이 핵심 주장 |
| C4 | Undefined technical term | UN1 | 용어 등장 후 정의 없음 | 같은 문단 후반 정의 | 첫 등장 시 즉시 정의 |
| C5 | Choice rationale is not understandable | UN3 | 선택 동기 부재 | 동기 암시 | 한계와 선택 이유 명시 |
| C6 | Logical disconnect between paragraphs | UN4 | 인과 부재 | 일부 연결 | 명시적 전제→결론 체인 |
| C7 | Bullets misused in narrative prose | FM3 | 서술 본문을 이유 없이 목록화 | 문단 설명이 일부 있음 | 문단 사용 또는 장르상 정당한 목록 |
| C8 | Unnatural phrasing in the requested language | NL1 | 명백한 직역·비관용 표현 | 일부 부자연스러움 | 해당 언어에 자연스러움 |
| C9 | Methods/contribution introduces a technique without WHY | IS1 | 기법만 제시 | 약한 동기 | 명확한 인과 |

점수가 1 이하인 항목만 Critical로 보고한다. C1과 C2는 0/1 binary이다.

### Warning — should fix

| ID | Issue | Principle |
| --- | --- | --- |
| W1 | Verified citation has incomplete traceability or bibliographic metadata | FA3 |
| W2 | Missing compare-contrast | UN2 |
| W3 | No implication at section end | ST3 |
| W4 | Vague modifiers | FM1 |
| W5 | Purpose unclear at section start | ST2 |
| W6 | Avoidably vague quantitative expression | FM2 |
| W7 | Reader-irrelevant code elements exposed | FM4 |
| W8 | Figure/table without reference | ST4 |
| W9 | Overblown rhetoric | NL2 |
| W10 | Overloaded sentence | NL3 |
| W11 | Word repetition in adjacent sentences | NL4 |
| W12 | Mechanical connector pattern | NL5 |
| W13 | Method/technique introduced without WHY outside Methods | IS1 |
| W14 | Steps presented without causal logic | IS2 |
| W15 | Abstract concept without a useful concrete case | IS3 |
| W16 | Section Insight Narrative Score below 5/8 | IS1–IS4 |
| W17 | Estimated result lacks appropriate uncertainty when variability matters | FM5 |

### Suggestion — optional

| ID | Issue |
| --- | --- |
| S1 | Improve a transition |
| S2 | Add a useful example or analogy |
| S3 | Simplify a sentence |

## Document-Type Additions

- 연구 제안서이면 `proposal-writing-guide.md`의 PR1–PR5를 추가 평가한다.
- SoP·학업계획서이면 `sop-writing-guide.md`의 SoP1–SoP5를 추가 평가한다.
- SoP1·SoP3 위반은 Critical로 격상한다.
- 논문 섹션과 기술 문서는 추가 원칙 없이 위 25원칙을 적용한다.

## Insight Narrative Score

주요 섹션마다 IS1–IS4를 0(없음), 1(약함), 2(강함)으로 평가한다.

| Section | IS1 WHY | IS2 Chain | IS3 Example | IS4 Arc | Total /8 | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| [섹션명] |  |  |  |  |  |  |

- 7–8: Insight-driven
- 5–6: Adequate
- 0–4: W16 발행
- Methods의 IS1 위반은 W13 대신 C9로 분류한다.

## Critic Prompt Template

Orchestrator는 다음 템플릿의 대괄호 부분을 채워 Critic에게 전달한다. 이 문서의 표를
프롬프트에 다시 복사하지 않는다.

```text
먼저 다음 평가 기준 파일을 끝까지 읽고 그대로 적용하세요:
[CRITIC_PROTOCOL_ABSOLUTE_PATH]

문서 유형: [DOCUMENT_TYPE]
요청 언어: [LANGUAGE]
문서 유형별 추가 가이드: [GUIDE_ABSOLUTE_PATH 또는 없음]

[Fact Base]
[VERIFIED, USER-ATTESTED, UNVERIFIED 표 전체]

[문서 내용]
[DRAFT]

평가 기준 파일의 Issue ID, 채점 기준, 출력 형식을 따르세요. 문서를 수정하지 말고
평가 결과만 반환하세요.
```

## Required Output

```markdown
### 🔴 Critical
- [C3] Introduction 1문단: "최근 연구에서는..." (score 0/2) → 핵심 주장으로 시작

### 🟡 Warning
- [W4] Methods 2문단: "매우 효과적인" → 검증된 구체 표현으로 대체

### 🔵 Suggestion
- [S1] Para 2→3: 전환 개선 권장

### Insight Narrative Score
| Section | IS1 | IS2 | IS3 | IS4 | Total | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Introduction | 1 | 2 | 1 | 1 | 5/8 | 🟡 |

### Hallucination Catch
- [C1] Para 2: "15% improvement" — Fact Base에 없음

### Summary
Critical: 2 | Warning: 4 | Suggestion: 1 | Insight Avg: 5.5/8
```

## Output Rules

1. JSON을 출력하지 않는다.
2. pass/fail이나 전체 합격 여부를 판단하지 않는다. 종료 판단은 Phase 4 책임이다.
3. 모든 Critical에 `(score N/2)`를 쓴다. C1/C2는 `(score N/1)`을 쓴다.
4. 정확한 위치와 짧은 원문 인용을 포함한다.
5. 수정 제안은 “X로 대체”, “Y 추가”처럼 구체적으로 작성한다.
6. 문서를 직접 수정하지 않는다.

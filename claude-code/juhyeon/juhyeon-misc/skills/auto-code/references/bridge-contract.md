# 브릿지 계약 (spec-bridge 전용)

auto-code Stage 1-b가 쓴 설계문서를 superpowers `writing-plans`가 소비 가능한
spec으로 변환할 때 지켜야 할 계약이다. spec-bridge 에이전트는 이 파일을 먼저 읽는다.

## 산출 스키마

브릿지는 아래 섹션을 이 순서로 가진 마크다운 파일 하나를 만든다.
경로: `<repo>/docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`

```
# <제목> Design Spec

**Date:** YYYY-MM-DD
**Status:** APPROVED
**Source:** <설계문서 절대경로>

## Problem Statement
## Motivation
## Approaches Considered
## Architecture
## Components
## Data Flow
## Error Handling
## Testing Strategy
## Global Constraints
## Success Criteria
## Open Questions
```

이 중 `## Architecture`, `## Data Flow`, `## Error Handling`,
`## Testing Strategy`, `## Global Constraints` 다섯 개는 게이트 2가 본문
존재까지 검사한다. 헤더만 두고 비우면 실패한다.

## 매핑표

왼쪽은 설계문서(`docs/superpowers/designs/<date>-<slug>-grill.md`)의 섹션,
오른쪽은 산출 spec에서의 행선지다. 설계문서 스키마는 auto-code SKILL.md
Stage 1-b가 단일 원천이다.

| 설계문서 섹션 | 행선지 | 처리 |
|---|---|---|
| Problem Statement | Problem Statement | 그대로 이관 |
| Constraints | Global Constraints | **정확값으로 변환** — 아래 규칙 참조 |
| Approaches Considered | Approaches Considered | 그대로 이관 (탈락 사유 포함) |
| Recommended Approach | Architecture | **시드로만 사용** — 컴포넌트 분해는 신규 작성 |
| Success Criteria | Success Criteria | 그대로 이관 |
| Open Questions | Open Questions | 그대로 이관 |
| Domain Notes | (경로를 따라가 읽는다) | 아래 참조 |

### Domain Notes 처리

이 섹션은 내용이 아니라 **경로 목록**이다. `CONTEXT.md`와
`docs/adr/NNNN-*.md`가 거기 나열된다. 브릿지는 각 경로를 Read해서 다음과 같이
쓴다.

| 읽은 것 | 쓰는 곳 | 처리 |
|---|---|---|
| `CONTEXT.md`의 `## Language` 용어 | spec 전체 | **정본 용어로 강제.** `_Avoid_`에 있는 말을 spec에 쓰지 않는다 |
| ADR 본문(결정과 이유) | Architecture / Global Constraints | 결정은 Architecture 전제로, 되돌릴 수 없는 제약은 Global Constraints 한 줄로 |
| ADR의 Considered Options | Approaches Considered | 설계문서에 없는 대안만 추가 |
| ADR의 Consequences | Error Handling / Testing Strategy | 비자명한 하류 영향은 처리·검증 대상으로 |

`Domain Notes`가 `ADR 없음`이면 그대로 넘어간다. 설계문서에 적힌 경로가 실제로
없으면 지어내지 말고 OPEN_QUESTIONS로 올린다.

설계문서에 원본이 없어 **브릿지가 새로 작성해야 하는** 섹션:
`## Motivation`, `## Components`, `## Data Flow`, `## Error Handling`,
`## Testing Strategy`. 그리고 `## Architecture`는 Recommended Approach를
시드로 삼되 컴포넌트 경계와 책임을 새로 세운다.

`## Motivation`은 설계문서에 대응 섹션이 없다. Problem Statement와 ADR의
"왜 이 결정을 했는가"에서 끌어오되, 근거가 없으면 비워 두지 말고 Problem
Statement를 압축해 한 문단으로 적는다 — 게이트 2가 본문을 요구하는 다섯 개
섹션에는 포함되지 않으므로 짧아도 된다.

## 출처 표기 규칙

새로 쓰는 모든 항목은 근거를 대괄호로 표기한다. 표기 없는 항목은 계약 위반이다.

```
- Node >= 20.11              [출처: package.json:14]
- 외부 의존성 추가 금지        [출처: 설계문서 §Constraints]
- 로그는 구조화 JSON          [추론]
```

- `[출처: <파일>:<줄>]` — 저장소 파일에서 확인한 사실
- `[출처: 설계문서 §<섹션>]` — Stage 1-b 설계문서에서 가져온 사실
- `[출처: ADR-<번호>]` / `[출처: CONTEXT.md §Language]` — domain-modeling 산출물에서 가져온 사실
- `[추론]` — 근거 없이 브릿지가 판단한 것

`[추론]` 태그가 붙은 항목은 **전부 OPEN_QUESTIONS로 승격**해 반환한다.
오케스트레이터가 사용자에게 확인받아 태그를 없앤다. 게이트 2는
`## Open Questions` 이전 구간에 `[추론]`이 남아 있으면 실패시킨다.

## Global Constraints 변환 규칙

설계문서의 `## Constraints`는 문답에서 나온 제약을 한 줄씩 적은 것이다. writing-plans는
"exact values, one line each"를 요구하고, SDD는 이 블록을 모든 task 리뷰어에게
verbatim으로 복사한다. 따라서 다음과 같이 변환한다.

- 산문 한 문장 → 검증 가능한 한 줄로 쪼갠다
- 버전·수치·경로·이름은 저장소에서 확인해 **정확값**을 쓴다
- 확인이 불가능하면 값을 지어내지 말고 `[추론]`으로 표기한다

변환 예:

```
전: "최신 Node를 쓰고 의존성은 최소로 유지한다"
후: - Node >= 20.11   [출처: package.json:14]
    - 신규 런타임 의존성 추가 금지   [출처: 설계문서 §Constraints]
```

## 반환 형식

브릿지는 spec 파일을 Write한 뒤, 최종 응답으로 아래만 텍스트로 반환한다.
spec 본문 전체를 반환하지 않는다 (오케스트레이터 컨텍스트 절약).

```
SPEC_PATH: <절대경로>
FILLED: Architecture, Components, Data Flow, Error Handling, Testing Strategy, Global Constraints
OPEN_QUESTIONS:
1. <질문> — 근거 부족 항목: <어떤 줄인지>
2. ...
```

Write가 하네스에 차단되면 `SPEC_PATH: BLOCKED`를 반환하고 spec 본문 전체를
텍스트로 이어 붙인다. 오케스트레이터가 대신 파일을 쓴다.

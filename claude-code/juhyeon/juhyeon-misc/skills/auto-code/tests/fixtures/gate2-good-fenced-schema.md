# 펜스 스키마 리스팅을 포함한 Design Spec

브릿지는 bridge-contract.md의 산출 스키마를 그대로 따라 쓰라고 지시받는다.
그 스키마는 아래처럼 섹션 헤더를 펜스 코드블록 안에 나열한다. 이 리스팅이
실제 섹션보다 앞에 오면, 펜스를 모르는 has_body()는 리스팅 쪽 헤더에서
found를 잡고 바로 다음 줄에서 exit 해 "본문 비어있음" 오탐을 낸다.

이 픽스처의 PASS는 스캐너가 **실제로 돌아서** 통과시킨 결과여야 한다.
그래서 아래 본문에는 스캐너가 반드시 읽고 반드시 허용해야 하는 줄들을
일부러 심어 뒀다: 펜스 안의 `[추론]` 예시, 인라인 코드 스팬 안의 `[추론]`
언급, 그리고 Open Questions로 정상 이월된 `[추론]` 항목이다.
조기 exit으로 아무것도 안 읽고 통과하면 이 셋 중 무엇도 검사되지 않는다.

```
# <제목> Design Spec

## Problem Statement
## Architecture
## Components
## Data Flow
## Error Handling
## Testing Strategy
## Global Constraints
## Open Questions
```

## Problem Statement
로그 수집기의 백프레셔 정책이 문서화돼 있지 않다.

## Architecture
수집기 프로세스 하나가 stdout을 읽어 고정 크기 링버퍼에 적재하고,
CLI가 그 버퍼를 읽기 전용으로 조회한다. 두 컴포넌트는 파일 소켓으로만 만난다.

## Data Flow
프로세스 stdout -> collector -> 링버퍼 -> CLI 조회.

## Error Handling
버퍼가 가득 차면 가장 오래된 항목부터 버리고 드롭 카운터를 올린다.

## Testing Strategy
링버퍼 오버플로 단위 테스트, 소켓 재연결 통합 테스트, CLI 스모크 테스트.

## Global Constraints
- Node >= 20.11   [출처: package.json:14]
- 외부 의존성 추가 금지   [출처: 설계문서 §Constraints]
- 근거를 못 찾은 항목은 `[추론]`로 표기한다   [출처: bridge-contract.md §출처 표기 규칙]

출처 표기 예시는 아래와 같다. 펜스 안이므로 위반이 아니다.

````markdown
- 링버퍼 기본 용량은 4096개   [추론]

```js
// 중첩 펜스도 바깥 펜스가 닫힐 때까지 전부 코드블록이다
const CAP = 4096
```
````

## Open Questions
- 보존 기간 기본값을 얼마로 할지   [추론]

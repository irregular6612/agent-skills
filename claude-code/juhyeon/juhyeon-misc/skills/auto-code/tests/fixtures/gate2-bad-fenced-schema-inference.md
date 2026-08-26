# 펜스 스키마 뒤에 미해소 추론이 남은 Design Spec

계약이 요구하는 문서 모양 그 자체가 스캐너를 우회시키는지 검증하는 픽스처다.
아래 펜스 코드블록은 bridge-contract.md의 산출 스키마를 그대로 옮긴 것이라
`## Open Questions` 줄을 포함한다. 펜스를 모르는 스캐너는 그 줄에서 exit 해
아래 Global Constraints의 미해소 `[추론]`을 한 줄도 읽지 못한다.

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
수집기의 보존 정책이 정해지지 않았다.

## Architecture
수집기 프로세스가 링버퍼에 적재하고 CLI가 읽기 전용으로 조회한다.

## Data Flow
프로세스 stdout -> collector -> 링버퍼 -> CLI 조회.

## Error Handling
버퍼가 가득 차면 가장 오래된 항목부터 버리고 드롭 카운터를 올린다.

## Testing Strategy
링버퍼 오버플로 단위 테스트, 소켓 재연결 통합 테스트.

## Global Constraints
- Node >= 20.11   [출처: package.json:14]
- 링버퍼 기본 용량은 4096개   [추론]

## Open Questions
- 보존 기간 기본값을 얼마로 할지   [추론]

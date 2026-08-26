# 샘플 기능 Design Spec

## Architecture
단일 수집기 프로세스가 stdout을 읽어 링버퍼에 넣는다.

## Data Flow
프로세스 stdout -> collector -> 링버퍼 -> CLI 조회.

## Error Handling
버퍼가 가득 차면 가장 오래된 항목부터 버리고 경고를 남긴다.

## Testing Strategy
링버퍼 오버플로 단위 테스트와 CLI 스모크 테스트.

## Global Constraints
- Node >= 20.11   [출처: package.json:14]
- 외부 의존성 추가 금지   [출처: 설계문서 §Constraints]
- 미확정 항목은 `[추론]` 태그를 달아 Open Questions로 승격한다   [출처: 설계문서 §Constraints]

## Open Questions
- 보존 기간 기본값을 얼마로 할지   [추론]

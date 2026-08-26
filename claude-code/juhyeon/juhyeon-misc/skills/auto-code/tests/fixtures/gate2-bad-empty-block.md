# 샘플 기능 Design Spec

## Architecture
단일 수집기 프로세스가 stdout을 읽어 링버퍼에 넣는다.

## Data Flow

## Error Handling
버퍼가 가득 차면 가장 오래된 항목부터 버린다.

## Testing Strategy
링버퍼 오버플로 단위 테스트.

## Global Constraints
- Node >= 20.11   [출처: package.json:14]

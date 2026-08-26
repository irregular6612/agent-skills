# Design: 샘플 기능

Status: DRAFT

## Problem Statement
로그 파일이 흩어져 있어 원인 추적에 시간이 걸린다.

## Constraints
외부 의존성 추가 금지.

## Recommended Approach
단일 수집기로 표준 출력만 모은다.

## Success Criteria
한 명령으로 최근 1시간 로그를 본다.

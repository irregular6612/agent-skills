# {{TOPIC}} — 구현 hand-off

**작성:** {{DATE}} / auto-code 파이프라인
**상태:** plan 완료, 구현 미착수

## 다음 세션에서 이 블록을 붙여넣으세요

```
아래 계획을 superpowers:subagent-driven-development로 실행해줘.

plan: {{PLAN_PATH}}
spec: {{SPEC_PATH}}

모델 배분:
- 구현 서브에이전트: sonnet (plan에 코드가 다 있어 전사 작업에 가깝다)
- 최종 whole-branch 리뷰: opus (SDD Model Selection이 요구하는 최고 체급)
- fix 라운드 4-5: 막힌 구현자보다 한 체급 위

시작 전에 git worktree로 격리하고, master/main에서 바로 구현하지 마.
```

## 배경 문서

| 문서 | 경로 |
|---|---|
| 설계문서 | {{DESIGN_DOC}} |
| spec (브릿지 산출) | {{SPEC_PATH}} |
| plan | {{PLAN_PATH}} |
| 도메인 문서 (CONTEXT.md / ADR) | 설계문서의 `## Domain Notes` 참조 |

## 확정된 Global Constraints

{{GLOBAL_CONSTRAINTS}}

이 목록은 SDD가 **모든 task 리뷰어에게 verbatim으로 전달**한다.
값을 바꾸면 리뷰 기준이 바뀐다는 뜻이므로, 수정 시 plan 원본도 같이 고칠 것.

## 미해결 리스크

{{OPEN_RISKS}}

## 검증 상태

- GATE 1 (설계문서 계약) 통과
- GATE 2 (브릿지 spec 5개 블록 + 출처 표기) 통과
- GATE 3 (plan의 SDD 파싱 가능성) 통과

게이트를 다시 돌리려면:

```bash
bash ~/.claude/skills/auto-code/scripts/gate.sh 3 {{PLAN_PATH}}
```

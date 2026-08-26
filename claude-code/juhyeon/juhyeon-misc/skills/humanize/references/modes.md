# Modes — Fast / Strict / Redo 결정 로직

Humanize 스킬의 모드 결정·자동 승급·redo 분기 매트릭스를 한 곳에 모음. SKILL.md Phase 0과 strict 모드 종합 판정 단계에서 로드.

## 모드 결정 흐름

```
입력 받음
  ↓
언어 감지 (첫 500자, 70% 기준)
  ↓
명시 플래그 체크 (--strict / --fast / --ko / --en)
  ↓
입력 길이 체크 (8,000자 초과 → strict 자동 승급)
  ↓
Redo 신호 체크 (후속 명령 / `/humanize-redo`)
  ↓
모드 확정
```

## 모드 결정표

| 신호 | 결정 | 이유 |
|---|---|---|
| `--strict` 명시 | strict | 사용자 의도 |
| `--fast` 명시 | fast | 사용자 의도 (8,000자 초과 시 경고만, 진행은 함) |
| 8,000자 초과 | strict (자동 승급, 1줄 고지) | monolith 단일 호출은 장문에 부적합 |
| "특정 카테고리만 다시" / "이 문단만" / "2차 윤문" / `/humanize-redo` | strict redo | monolith는 부분 재실행 불가 |
| 위 아무것도 해당 안 됨 | fast | 디폴트 |

## 자동 승급 조건

다음 신호 중 하나라도 감지되면 fast → strict 자동 승급:
- 입력 길이 ≥ 8,001자
- 후속 명령 "특정 카테고리만 다시"·"이 문단만"·"강도 조정"
- `/humanize-redo` 호출

승급 시 한 줄 고지: `자동 승급: fast → strict (사유: <8,000자 초과 | redo 신호>)`

## Strict 종합 판정 매트릭스

`humanize-fidelity-auditor` + `humanize-naturalness-reviewer` 결과를 바탕으로 다음 분기:

| fidelity | naturalness | 종합 판정 | 후속 동작 |
|---|---|---|---|
| full_pass | accept | 최종 승인 | Phase D 출력 |
| full_pass | accept_with_note | 최종 승인 (메모 첨부) | Phase D 출력 + summary.md에 메모 |
| full_pass | rewrite_round_2 | 2차 윤문 | rewriter 재호출 (target finding 한정) |
| full_pass | rollback_and_rewrite | 롤백 후 재윤문 | rewriter에 edit 롤백 지시 후 재호출 |
| conditional_pass (rework action ≥1: `rollback_required` 또는 `rewrite_with_hedge_preserved`) | (any) | 부분 롤백 + 재시도 | rewriter 재호출 (rework 대상 edit만) → 재감사 |
| conditional_pass (warnings only) | accept / accept_with_note | accept_with_note | 경고를 summary.md 기록, 재시도 없음 |
| conditional_pass (warnings only) | rewrite_round_2 / rollback_and_rewrite | naturalness 경로 따름 | naturalness 판정대로 rewriter 재호출 |
| fail | (any) | 전면 재작업 | rewriter 전면 재호출 |

최대 3 round 후 미해결이면 `hold_and_report` — 결과 그대로 출력 + summary.md에 "사람 검토 요망" 명시.

이 매트릭스(modes.md)가 conditional_pass를 포함한 모든 후속 동작의 단일 정보 출처(SSOT)다 — 리뷰어 에이전트는 verdict와 per-edit action만 보고하며 파이프라인의 후속 흐름을 직접 결정하지 않는다.

## Redo 신호 파싱표

사용자 후속 발화를 다음 표로 해석해 rewriter 입력을 조정:

| 사용자 신호 | 처리 |
|---|---|
| "특정 카테고리만 다시" / "X 카테고리만" / "번역투만" 등 | 해당 카테고리 finding만 rewriter 재실행 |
| "이 문단만" / "두 번째 문단만" / "이 부분만" | 해당 범위 finding만 처리 |
| "강도 낮춰" / "보수적으로" / "조심스럽게" | min_severity = S1만 |
| "강도 높여" / "더 적극적으로" / "공격적으로" | min_severity = S1+S2+S3 모두 |
| "이 변경 되돌려" / "롤백" / "원래대로" | fidelity-auditor 롤백 명령으로 처리 |
| "2차 윤문" / 단순 redo 요청 | 잔존 finding 전체 대상으로 round 2 진행 |

## EN Strict 진입 조건

EN inline 디폴트에서 strict로 진입하는 신호:
- `--strict` 명시
- 8,000자 초과
- Redo 신호 (`/humanize-redo`)

EN strict 진입 시 inline 1차 윤문본을 `03_rewrite.md`로 저장하고 fidelity-auditor + naturalness-reviewer를 `language=en`으로 호출.

## 모드별 산출물 요약 (자세히는 `workspace.md`)

| 모드 | 산출물 |
|---|---|
| KO Fast | `00_meta.json` + `01_input.txt` + `final.md` + `summary.md` |
| KO Strict | 6단계 + `00_meta.json` |
| EN Inline | (응답에 직접 출력, `_workspace` 디렉토리 미생성) |
| EN Strict | `00_meta.json` + `01_input.txt` + `03_rewrite.md` + `04_fidelity_audit.json` + `05_naturalness_review.json` + `final.md` + `summary.md` |

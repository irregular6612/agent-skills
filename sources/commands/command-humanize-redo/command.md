---
description: 최근 윤문 결과를 2차로 다듬기 — 특정 카테고리·문단·강도 조정 가능
argument-hint: [조정 지시 — 예 "번역투만 다시" "이 문단만" "강도 낮춰"]
---

# /humanize-redo — 2차 윤문 / 부분 재실행

가장 최근 cwd `_workspace/{run_id}/`를 찾아 `humanize` 스킬을 Strict redo 모드로 재호출한다.

## 사용자 지시
$ARGUMENTS

## 동작

1. cwd `_workspace/`에서 최신 `run_id` 디렉토리 식별 (없으면 "이전 실행이 없습니다. `/humanize`로 시작하세요" 안내).
2. 직전 run의 언어·옵션 복원:
   - `00_meta.json` 존재 → 그대로 사용
   - 없음 (옛 v1.5 또는 이전 run) → `01_input.txt` 첫 500자로 언어 재추정, `_workspace/` 내 파일 존재로 모드 추정, 신규 `00_meta.json` 작성
3. `humanize` 스킬 Phase 0를 Strict redo 모드로 진입:
   - 사용자 지시를 `references/modes.md §Redo 신호 파싱표`로 해석
   - 카테고리/문단/강도/롤백 신호에 따라 rewriter 입력 조정
4. 산출물은 `03_rewrite_v2.md` (또는 v3)로 버전 분리 저장.
5. `04_fidelity_audit.json` + `05_naturalness_review.json` 재실행 → 새 등급·하이라이트 보고.

## 루프 한도

최대 round 3. 그 이상은 `hold_and_report`로 사람 검토 권고.

## 참고

- 풀 파이프라인 신규 실행은 [`/humanize`](./humanize.md) 사용.
- Redo 신호 파싱표: `references/modes.md §Redo 신호 파싱표`
- `00_meta.json` 후방 호환: `references/workspace.md §후방 호환`

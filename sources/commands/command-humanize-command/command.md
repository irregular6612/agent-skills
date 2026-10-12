---
description: AI가 쓴 한글·영문 텍스트를 자연스럽게 윤문 (humanize 스킬 호출)
argument-hint: [윤문할 텍스트 또는 파일 경로 + 옵션]
---

# /humanize-command — 한글·영문 AI 윤문

`humanize` 스킬을 발동해 인자로 전달된 텍스트(또는 파일)에 윤문 파이프라인을 실행한다.

## 입력
$ARGUMENTS

## 동작

1. 인자가 비었으면 "윤문할 텍스트를 붙여넣어 주세요" 안내 후 종료.
2. 인자가 파일 경로(.txt/.md)면 Read로 본문 로드.
3. 인자가 텍스트면 그대로 사용.
4. `humanize` 스킬 SKILL.md Phase 0부터 실행:
   - 첫 응답 한 줄: `humanize {ko|en} {fast|strict|inline} / run_id: ...`
   - 언어 자동 감지 (`--ko`·`--en`로 강제 가능)
   - 모드 자동 결정 (`--strict`로 Strict 강제)
   - Strict면 cwd `_workspace/{YYYY-MM-DD-NNN}/` 생성, EN inline은 미생성
5. 결과 반환:
   - 한 줄 상태 (변경률·등급·자체검증)
   - 윤문본 본문 (마크다운 블록)
   - 카테고리별 탐지 before/after 표 (KO=ko-taxonomy ID, EN=en-patterns 카테고리)
   - 등급 B 이하면 "`/humanize-redo`로 2차 윤문 가능" 안내

## 옵션 (인자 끝에 자연어로)

- `장르: 칼럼|리포트|블로그|공적` — KO만 (생략 시 첫 300자 추정)
- `voice: clear-thinker|casual-storyteller|sharp-opinionated|warm-professional|mirror` — EN만
- `강도: 보수|기본|적극` (디폴트: 기본)
- `최소심각도: S1|S2|S3` (디폴트: S2)
- `--strict` — Strict 모드 강제
- `--fast` — Fast 모드 강제 (8,000자 초과 시 경고)
- `--ko` / `--en` — 언어 자동 감지 무시

`voice: mirror` 선택 시 SKILL.md가 "윤문할 voice 샘플을 붙여넣어 주세요" 1회 질문. 샘플 직접 첨부하려면 `voice: mirror` 옵션과 함께 인자 끝에 ` --- 샘플 ---` 구분자 후 샘플 텍스트 붙여넣기.

## 참고

- 스킬 본체: `~/.claude/skills/humanize/SKILL.md`
- 모드 결정 로직: `references/modes.md`
- KO 분류 체계: `references/ko-taxonomy.md`
- EN 안티패턴: `references/en-patterns.md`
- EN voice: `references/en-voices.md`

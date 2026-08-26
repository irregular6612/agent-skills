# Workspace — `_workspace/{run_id}/` 산출물 계약

Strict 모드 및 EN Strict가 사용하는 작업공간 명세. 모든 strict 에이전트(monolith·detector·rewriter·fidelity-auditor·naturalness-reviewer)가 이 계약을 따른다.

## 디렉토리 구조

```
<cwd>/_workspace/{YYYY-MM-DD-NNN}/
├── 00_meta.json
├── 01_input.txt
├── 02_detection.json                (KO Strict only)
├── 03_rewrite.md
├── 03_rewrite_diff.json             (KO Strict only — rewriter가 작성)
├── 03_rewrite_v2.md / v3.md         (redo round 2/3)
├── 04_fidelity_audit.json
├── 05_naturalness_review.json
├── final.md
└── summary.md
```

## 파일 명세

### `00_meta.json` (Strict: orchestrator 작성 / Fast: monolith 작성)

```json
{
  "run_id": "2026-05-25-001",
  "language": "ko",
  "mode_initial": "fast",
  "mode_current": "strict",
  "genre": "칼럼",
  "intensity": "기본",
  "min_severity": "S2",
  "voice": null,
  "round": 2,
  "created_at": "2026-05-25T14:32:11+09:00"
}
```

필드:
- `language`: `ko` | `en`
- `mode_initial`: 첫 진입 모드 (`fast` | `strict` | `inline`)
- `mode_current`: 현재 모드 (자동 승급 후 갱신)
- `genre`: KO만 (`칼럼` | `리포트` | `블로그` | `공적`), EN은 `null`
- `intensity`: `보수` | `기본` | `적극`
- `min_severity`: `S1` | `S2` | `S3`
- `voice`: EN만 (`clear-thinker` | `casual-storyteller` | `sharp-opinionated` | `warm-professional` | `mirror`), KO는 `null`
- `round`: 1부터 시작, redo마다 +1
- `created_at`: ISO 8601 (timezone 포함)

### `01_input.txt` (모든 strict 모드 — orchestrator 작성)

원문 그대로. 줄바꿈·공백 보존.

### `02_detection.json` (KO Strict — `humanize-ko-detector` 작성)

`humanize-ko-detector.md` 본문 §출력 스키마 참조. `findings` 배열 + `meta` 객체.

### `03_rewrite.md` (Strict — rewriter / SKILL.md orchestrator 작성)

1차 윤문본. KO Strict는 `humanize-ko-rewriter`가 작성. EN Strict는 SKILL.md가 inline 3-pass로 작성.

### `03_rewrite_diff.json` (KO Strict — rewriter 작성)

`humanize-ko-rewriter.md` 본문 §출력 스키마 참조. `edits` 배열 + 변경률 메타.

### `03_rewrite_v2.md`, `v3.md` (Redo round 2/3 — rewriter / orchestrator 작성)

2차·3차 윤문본. round 분리 저장.

### `04_fidelity_audit.json` (Strict — `humanize-fidelity-auditor` 작성)

의미 동등성 감사 결과. language 무관 동일 스키마.

### `05_naturalness_review.json` (Strict — `humanize-naturalness-reviewer` 작성)

잔존 패턴·과윤문 리뷰. language별 finding 카테고리 다름 (KO=ko-taxonomy ID, EN=en-patterns 카테고리).

### `final.md` (Strict: orchestrator 작성 / Fast: monolith 작성)

최종 윤문본. Strict면 최신 `03_rewrite_vN.md`와 동일. Fast면 monolith가 직접 작성.

### `summary.md` (모든 모드 — orchestrator가 Write)

메트릭 + 등급 + 하이라이트 + 잔존 finding. 자세한 포맷은 `humanize-ko-monolith.md` §출력 포맷 참조. **Fast 모드에서도 orchestrator가 기록한다** — monolith(서브에이전트)는 `summary.md`를 직접 Write할 수 없어(아래 §서브에이전트 Write 제약) 본문을 텍스트로 반환하고 orchestrator가 디스크에 옮긴다.

## 백업 정책

모든 산출물은 덮어쓰기 전 `*_prev.{확장자}`로 백업. 예:
- `final.md` → `final_prev.md` (덮어쓰기 전)
- `02_detection.json` → `02_detection_prev.json`

이전 prev가 이미 있으면 `*_prev2.{확장자}`로 누적 (최대 3개까지, 그 이상은 가장 오래된 것 삭제).

## 언어별 산출물 차이

| 모드 | 작성하는 파일 |
|---|---|
| KO Fast | `00_meta.json` + `01_input.txt` + `final.md` + `summary.md` (4개) |
| KO Strict | 위 4개 + `02_detection.json` + `03_rewrite.md` + `03_rewrite_diff.json` + `04_fidelity_audit.json` + `05_naturalness_review.json` (9개) |
| EN Inline | (없음 — `_workspace` 디렉토리 미생성, 응답에 직접 출력) |
| EN Strict | `00_meta.json` + `01_input.txt` + `03_rewrite.md` + `04_fidelity_audit.json` + `05_naturalness_review.json` + `final.md` + `summary.md` (7개. 02·03_diff 없음) |

> **KO Fast 파일 소유권**: 오케스트레이터(SKILL.md)는 `01_input.txt`와 `summary.md`를 작성하고 run 메타데이터(`run_id`·`intensity`·`min_severity`·`created_at`)를 monolith에 전달한다. `00_meta.json`·`final.md`는 `humanize-ko-monolith`(서브에이전트)가 디스크에 직접 Write한다. `summary.md`는 monolith가 본문을 텍스트로 반환하면 orchestrator가 기록한다 (아래 §서브에이전트 Write 제약).

## 서브에이전트 Write 제약 (harness 가드 — 실재함)

Codex runtime는 **서브에이전트가 `Write` 도구로 report성 파일명을 기록하는 것을 차단**한다. 차단 메시지:

> `Subagents should return findings as text, not write report files. Include this content in your final response instead.`

검증(2026-06-01): `summary.md` → **차단**, `final.md`·`00_meta.json`·`01_input.txt`·`02_detection.json` 등 → 허용. 즉 `summary` 같은 report성 이름만 가드에 걸린다. **orchestrator(메인 루프)** 와 **Bash**는 가드 비대상.

함의:
- 서브에이전트(monolith·detector·rewriter·auditor·reviewer)는 `summary.md`를 직접 Write하지 않는다 — 본문을 텍스트로 반환하고 **orchestrator가 기록**한다.
- Strict 모드의 `final.md`·`summary.md`는 원래 orchestrator가 기록하므로 문제 없음. Fast 모드의 `summary.md`만 이 경로로 바뀐다 (monolith 텍스트 반환 → orchestrator Write).
- Bash heredoc 우회는 쓰지 않는다 — orchestrator 기록이 정본 경로다.

## 후방 호환 — `00_meta.json` 없을 때

옛 `_workspace/`(v1.5 또는 그 이전)에 `00_meta.json`이 없는 경우 `/humanize-redo`는 다음 폴백:
1. `01_input.txt` 첫 500자로 언어 재추정 (KO/EN 70% 기준)
2. `_workspace/` 내 파일 존재 여부로 모드 추정 (`02_detection.json` 있으면 KO Strict로 가정)
3. 추정 결과를 `00_meta.json`으로 신규 작성 후 redo 진행

## NNN 시퀀스

`{YYYY-MM-DD-NNN}` 의 NNN은 해당 날짜의 `_workspace/` 디렉토리 카운트 + 1 (zero-padded 3자리). 언어·모드와 무관. 동일 날짜 KO 003과 EN 004는 그냥 시퀀스.

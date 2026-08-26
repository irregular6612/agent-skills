---
name: humanize
description: KO/EN 텍스트의 AI 문체, 번역투, 과장 표현을 줄여 사실과 의미는 유지한 채 자연스럽게 윤문한다.
---

# Humanize — AI 윤문 통합 스킬 (KO + EN)

## Phase 0: 한 줄 상태 출력 + 언어/모드/run_id 결정

작업 시작 시 첫 출력:
```
humanize {lang} {mode} / run_id: {YYYY-MM-DD-NNN}
```

### 언어 감지 (첫 500자)

- 한글(가나다 유니코드) ≥ 70% → `ko`
- 영문(ASCII 알파벳) ≥ 70% → `en`
- 둘 다 70% 미만(혼재) → 사용자에 1회 질문: "이 글 한글 위주? 영문 위주?"

`--ko` / `--en` 명시되면 자동 감지 무시.

### 모드 결정

`references/modes.md`의 모드 결정표를 따른다.

| 신호 | 결정 |
|---|---|
| `--strict` 또는 "정밀 모드" | strict |
| 입력 8,000자 초과 | strict (자동 승급 + 1줄 고지) |
| "특정 카테고리만" / "이 문단만" / "2차 윤문" / `/humanize-redo` | strict redo |
| 그 외 | fast (KO 디폴트) / inline (EN 디폴트) |

### run_id

cwd 기준 `_workspace/{YYYY-MM-DD-NNN}/` 신규 생성 (NNN은 그날의 시퀀스).

Redo 신호면 cwd `_workspace/`에서 최신 run_id 재사용. `00_meta.json` 없는 옛 run의 경우 `01_input.txt` 첫 500자로 언어 재추정 후 신규 `00_meta.json` 작성 (자세히는 `references/workspace.md §후방 호환`).

EN inline 모드는 `_workspace/` 생성 안 함 (가벼움 유지).

### Phase 0 직후 — 옛 author-context.yaml 안내

cwd에 `author-context.yaml`이 존재하면 1줄 안내:
"author-context.yaml 발견됐으나 v1.5+에서는 지원하지 않습니다. EN voice mirror 모드(`/humanize --voice mirror`)로 대체 가능합니다."

진행은 그대로 (옵션 무시).

## 공통 철칙 (모든 언어·모든 모드)

1. **의미 불변**: 사실·주장·수치·날짜·고유명사·인용은 한 글자도 안 건드림.
2. **장르 유지**: 칼럼이 에세이로, 리포트가 블로그로 표류 금지.
3. **register 보존**: 격식체 → 격식체. AI 티는 문법·수사이지 격식 자체가 아님.
4. **근거 기반**: 탐지된 패턴 span만 수정. 무근거 임의 개선 금지.
5. **변경률 가드**: 30% 초과 경고 / 50% 초과 강제 중단·롤백.
6. **자동 추론 금지**: AGENTS.md 등 외부 파일을 자동 파싱해 옵션 추론 안 함.

## 한글 (`lang=ko`) 분기

### Fast 모드 (디폴트)

1. `01_input.txt` 작성 (오케스트레이터)
2. `humanize-ko-monolith` 에이전트 1회 호출:
   - 입력: `input_path` (`01_input.txt` 절대경로) + `quick_rules_path` (`~/.codex/skills/humanize/references/ko-quick-rules.md` 절대경로) + `genre_hint` + `run_id` + `intensity` + `min_severity` + `created_at`
   - monolith가 디스크에 직접 Write: `00_meta.json` + `final.md`
   - monolith가 **텍스트로 반환**: `summary.md` 전문
3. **오케스트레이터가 `summary.md` 작성**: monolith가 반환한 summary 전문을 `_workspace/{run_id}/summary.md`로 기록. (서브에이전트는 harness 가드로 report성 파일(`summary.md`)을 Write할 수 없으므로 orchestrator가 기록한다 — 자세히는 `references/workspace.md §서브에이전트 Write 제약`.)
4. 결과 4종 반환:
   - 한 줄 상태 (변경률·등급·자체검증)
   - 윤문본 본문 (마크다운 블록)
   - summary.md 핵심 표
   - 등급 B 이하면 "정밀 검증은 `--strict`로 5인 파이프라인" 안내

상세 룰북: `references/ko-quick-rules.md`

### Strict 모드 (`--strict` 또는 자동 승급)

`references/modes.md §Strict 종합 판정 매트릭스`에 따라 분기.

1. `00_meta.json` 작성 (`mode_current: strict`)
2. `01_input.txt` 작성
3. `humanize-ko-detector` 호출 → `02_detection.json`
4. `humanize-ko-rewriter` 호출 → `03_rewrite.md` + `03_rewrite_diff.json` (최대 3회 루프)
5. 병렬 호출:
   - `humanize-fidelity-auditor` (`language: "ko"`) → `04_fidelity_audit.json`
   - `humanize-naturalness-reviewer` (`language: "ko"`) → `05_naturalness_review.json`
6. 종합 판정 매트릭스 적용 → 승인 / 2차 윤문 / 롤백 분기
7. 최대 3 round 후 미해결이면 `hold_and_report`
8. `final.md` + `summary.md` 작성 + 결과 반환

상세: `references/ko-taxonomy.md` (SSOT 10대×40+ 패턴), `references/ko-playbook.md` (윤문 처방)

## 영문 (`lang=en`) 분기

### Inline 3-pass 모드 (디폴트)

1. `references/en-patterns.md` 로드 (Tier 1/2/3 banned vocab + 구조 패턴 + 17항 QC 체크리스트)
2. `references/en-voices.md` 로드 + voice 결정:
   - 사용자가 `--voice <name>` 명시 → 사용
   - 사용자가 샘플 첨부 → `mirror` 모드 (샘플 분석 후 voice profile 빌드)
   - 사용자가 mirror 선택했는데 샘플 없음 → "윤문할 voice 샘플을 붙여넣어 주세요" 1회 질문
   - 명시 없음 → 4 preset 안내 후 사용자 선택
   - 사용자가 "그냥 자연스럽게" → `clear-thinker` 디폴트
3. Pass 1: vocabulary 제거 (Tier 1/2/3)
4. Pass 2: 구조 깨기 (parallel negation, tricolon, em-dash, mirror structure 등)
5. Pass 3: human texture 추가 (선택된 voice 적용)
6. 17항 QC 체크리스트 자체 점검
7. 윤문본 반환 (단일 응답, `_workspace` 미생성)

상세: `references/en-patterns.md`, `references/en-voices.md`

### Strict 모드 (`--strict`, 영문에서도 가능)

1. `00_meta.json` + `01_input.txt` 작성
2. Inline 3-pass로 1차 윤문본 생성 → `03_rewrite.md` 저장
3. 병렬 호출:
   - `humanize-fidelity-auditor` (`language: "en"`) → `04_fidelity_audit.json`
   - `humanize-naturalness-reviewer` (`language: "en"`) → `05_naturalness_review.json`
4. 종합 판정 매트릭스 (KO와 동일) 적용 → 잔존 시 Pass 2~3 부분 재실행
5. `final.md` + `summary.md` 작성 + 결과 반환

EN Strict는 옵션. 디폴트는 inline.

## 웹 확장 (`--web` 모드)

윤문 자체가 아니라 **윤문 파이프라인을 웹 서비스로 패키징**하는 작업. 텍스트 입력→윤문 출력을 원하면 이 모드가 아니라 위 KO/EN 분기를 쓴다.

발동 신호: "humanize 웹서비스 만들어줘"·"윤문 웹앱 설계"·"Next.js/Vercel 확장"·`--web`.

1. `humanize-web-architect` 에이전트 1회 호출
2. 입력: 사용자 요구사항 + `references/web-service-spec.md` 절대경로
3. 산출물: 아키텍처 문서·API 스펙(`/api/detect`, `/api/rewrite`)·4화면 UX 와이어프레임·통합 가이드(AI Gateway·Resend·Clerk 선택)

상세: `references/web-service-spec.md`

## Redo / 부분 재실행

`/humanize-redo` 또는 후속 신호("특정 카테고리만 다시"·"이 문단만"·"강도 낮춰"·"강도 높여")가 오면:

1. cwd `_workspace/`에서 최신 run_id 식별 (없으면 "이전 실행이 없습니다. `/humanize`로 시작하세요" 안내)
2. `00_meta.json`에서 언어·이전 모드·옵션 복원 (없으면 `01_input.txt` 첫 500자로 재추정)
3. Strict 모드로 자동 승급 (Fast monolith는 부분 재실행 불가)
4. 사용자 지시 파싱 (`references/modes.md §Redo 신호 파싱표`)
5. rewriter 재호출 → `03_rewrite_v2.md` (또는 v3)
6. 검증 단계 재실행
7. 최대 3 round 후 `hold_and_report`

## 옵션 (자연어 인자)

- `장르: 칼럼|리포트|블로그|공적` (KO만, 생략 시 첫 300자로 추정)
- `voice: clear-thinker|casual-storyteller|sharp-opinionated|warm-professional|mirror` (EN만)
- `강도: 보수|기본|적극` (디폴트: 기본)
- `최소심각도: S1|S2|S3` (디폴트: S2)
- `--strict` 또는 `--fast` (모드 강제)
- `--ko` 또는 `--en` (언어 자동 감지 무시)

언어와 안 맞는 옵션이 들어오면(예: EN 입력에 `장르` 옵션) 1줄 경고 후 무시.

## 산출물 계약

`references/workspace.md`에 정의된 명세를 따른다:
- KO Fast: `00_meta.json` + `01_input.txt` + `final.md` + `summary.md` (4개)
- KO Strict: 위 4개 + `02_detection.json` + `03_rewrite.md` + `03_rewrite_diff.json` + `04_fidelity_audit.json` + `05_naturalness_review.json` (9개)
- EN Inline: (`_workspace` 미생성, 응답에 직접 출력)
- EN Strict: `00_meta.json` + `01_input.txt` + `03_rewrite.md` + `04_fidelity_audit.json` + `05_naturalness_review.json` + `final.md` + `summary.md` (7개)

모든 덮어쓰기 전 `*_prev.{ext}` 백업.

## 에이전트 호출 규칙

**모델:** 모든 에이전트 `model: opus` 통일.

**필요 에이전트 7종:**
- `humanize-ko-monolith` (Fast 전용)
- `humanize-ko-detector`, `humanize-ko-rewriter` (KO Strict)
- `humanize-fidelity-auditor`, `humanize-naturalness-reviewer` (KO/EN Strict 공용, `language` 파라미터)
- `humanize-taxonomist` (SSOT 확장, 런타임 호출 X — 별도 명령으로만)
- `humanize-web-architect` (`--web` 모드 전용, 윤문 핫패스 아님)

자동 탐색 위치: `~/.codex/skills/claude-subagent-library/references/agents/humanize-*.md`.

## 테스트 시나리오

### KO Fast 정상 흐름
- 입력: ChatGPT 한글 칼럼 초안 (2,000~5,000자, 번역투·결말 공식·hype 어휘 풍부)
- 기대: monolith 1콜, 변경률 15~25%, 등급 A/B, wall-clock 2~3분

### KO Strict 자동 승급
- 입력 8,000자+ → fast→strict 1줄 고지 후 5인 파이프라인
- 기대: 변경률 18~22%, fidelity full_pass, naturalness accept

### EN inline 정상 흐름
- 입력: 영문 LinkedIn 초안 (~500단어)
- voice 결정 → 3-pass → 17항 QC 통과 → 단일 응답 반환

### Redo
- 직전 KO Strict run + "번역투만 다시 해줘" → A 카테고리 finding만 rewriter 재실행, `03_rewrite_v2.md` 생성

## 주의 사항

- **의미 불변이 최상위 불문율.** 모든 모드·언어에서 위반 즉시 롤백.
- **수치·고유명사·직접 인용은 탐지/윤문 대상 아님.** Do-NOT list 엄수.
- **장르 이탈 금지.** KO 격식체 → 격식체, EN voice 선택 → voice 유지.
- **변경률 30% 초과 → 경고, 50% 초과 → 강제 중단.**
- **자동 로드 금지.** AGENTS.md 등 다른 파일을 자동 파싱해 옵션 추론 안 함.

## 참고 자료 (load on demand)

- 모드 결정·redo 규칙·종합 판정 매트릭스: `references/modes.md`
- `_workspace/` 산출물 계약: `references/workspace.md`
- 한글 Fast 룰북: `references/ko-quick-rules.md`
- 한글 Strict SSOT (10대×40+ 패턴): `references/ko-taxonomy.md`
- 한글 Strict 처방: `references/ko-playbook.md`
- 영문 안티패턴 (vocab + 구조 + 17항 QC + LinkedIn 특칙): `references/en-patterns.md`
- 영문 voice (4 preset + mirror): `references/en-voices.md`
- 웹 확장 스펙 (`--web`): `references/web-service-spec.md`

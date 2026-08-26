# Iterative Academic Writer — Changelog

## v5.x (2026-07-22, Critic 단일 기준과 충돌 규칙 정리)

### Changed
- Critic 평가표·프롬프트·출력 규칙을 `critic-review-protocol.md` 한 곳으로 통합했다.
- 서술 본문과 장르상 필요한 목록을 구분하고, 불확실성 보고 대상을 변동성 있는 추정치로 한정했다.
- `User-Attested` 근거 수준을 추가하고 `Unverifiable`이 남으면 완료하지 않도록 했다.
- NL1/C8을 요청 언어별 자연스러움 평가로 일반화했다.

### Supersedes
- 아래 v3.x의 “SKILL.md ↔ agent.md 평가표 복사·동기화” 방식은 더 이상 적용하지 않는다.
  `evals/check_sync.sh`는 이제 protocol 단일 기준과 consumer 연결을 검사한다.

## v4.x (2026-06-01, 회귀 자동화 — v3 C1 옵션 실행)

### Added
- V4-A: `evals/lint_review_output.sh` — academic-reviewer 출력 회귀 린터. v3 실패 모드 3건 자동 검출(JSON 블록 / pass·fail verdict / catalog 범위 밖 C·W·S ID). captured 출력 파일 대상. 종료코드 0/1/2.
- V4-B: `evals/check_sync.sh` — SKILL.md↔agent.md sync drift 가드. v3.x "Sync 의무" 3항목(채점표·W catalog·prohibition) 양쪽 존재 검증. pre-commit hook 후보.
- evals.json에 `review_check`(doc_type / dispatch_ids_expected / forbidden_patterns / lint) + top-level `tooling` 메타 추가.

### Note (자동화 경계)
evals는 생성 프롬프트라 end-to-end는 LLM 필요(불가피한 manual). 자동화 가능한 두 경계만 스크립트화: 정적 sync 가드 + captured 출력 린팅. 다음 후보 — pre-commit hook에 check_sync.sh 연결.

## v3.x (2026-06-01, prohibition rules sync 확장)

### Fixed (P1/P2 — v2 실측 검증에서 발견)
- V3-A: SKILL.md Phase 3a prompt에 W1-W17 catalog inline 추가 — agent가 임의 W ID 부여하던 문제 해결
- V3-B: SKILL.md Phase 3a prompt에 prohibition rules 6건 inline 추가 — pass/fail verdict 누출 + JSON 블록 누출 차단
- V3-C: changelog sync 의무 정의 확장 (채점 기준 표 + W catalog + prohibition rules)

### Sync 의무 (확장 — v2.y "Sync 의무" supersedes)
다음 3개 항목은 SKILL.md Phase 3a prompt ↔ `agents/academic-reviewer.md` 양쪽 동시 갱신:
1. **C1-C9 채점 기준 표** (Score 0/1/2 column) — SKILL.md Step 2 inline + agent Step 2 표
2. **W1-W17 catalog** — SKILL.md 본문 line 157-173 + Phase 3a prompt inline + agent description
3. **Prohibition rules 6건** — SKILL.md Phase 3a prompt "[출력 규칙]" 블록 + agent "## 평가 원칙" 섹션

한쪽 변경 시 다른 쪽 동시 갱신 필수. CI 검사 또는 수동 grep 권장.

## v2.y (2026-05-25, post-validation fix)

### Fixed (P0 integration breaks discovered post-commit 174e00b)
- G1: `agents/academic-reviewer.md` 전면 재작성 — 25-principle 정합, JSON 출력 폐기, 마크다운 Issue ID 형식(SKILL.md Phase 4 호환), 채점 기준 self-contained
- G2: `references/proposal-writing-guide.md` 24원칙 → 25원칙 (line 3, 18)
- G3: SoP1-SoP5 / PR1-PR5 dispatch 메커니즘 — Phase 3a prompt에 conditional 표 inline + 출력 예시
- G4: `references/blueprint-template.md` 문서 유형 옵션에 SoP·학업계획서 추가
- G5: Phase 3a 채점 기준을 prompt 본문 inline 삽입 (path 의존 제거)

### Added
- Phase 0 Step 0-1 / 0-2 — Missing-info AskUserQuestion 단계 (evals 정상 진행)
- academic-reviewer agent에 SoP/PR 추가 원칙 dispatch handling

### Sync 의무
- SKILL.md Phase 3a 채점 기준 표 ↔ `agents/academic-reviewer.md` Step 2 표 동기화 필수. 한쪽 변경 시 다른 쪽 동시 갱신.

## v2.x (2026-05-25)

### Added
- FM5 (Statistical reporting with CI, Agarwal et al. 2021) → W17
- Naturalness category (NL1–NL5)
- Insight category (IS1–IS4), Insight Narrative Score 0/1/2
- C9 (IS1 in Methods → Critical; 그 외 섹션 → W13)
- SoP writing guide (Decision B4 채택 결과 — `references/sop-writing-guide.md` 약식 ~77줄)
- Domain-agnostic Fact Base 예시 (RCT 임상시험 표본 — F3 행)
- Critical(C1–C9) 원칙별 0/1/2 채점 기준 컬럼 (Decision D1)
- `evals/evals.json` 3개 test case (Decision E1 — NeurIPS Intro / NRF 제안서 / EECS SoP)

### Fixed
- Principle count 24 → 25 (실측 일치, Decision A1; 본문 5개 위치 일괄 갱신)
- iteration `== 5` → `>= 5` 표기 통일 + counter 의미 명시 (1부터 시작)
- Phase 2 가이드 분기 누락 — section/proposal/sop로 명시 분기
- Critic Hallucination 책임 모호 → Fact-Checker 전담, Critic 보조 catch (Fail-safe)
- "Pre-0" → "Pre-Phase 0" 명칭 통일
- Blueprint 최대 2회 vs 전체 5 iterations 카운터 구분 명시

### Restructured
- 본 cycle에서는 압축/추출 없음 (Decision C3 — 본문 monolith 유지, ~575줄)
- 향후 후속 cycle에서 C1/C2 (`references/principles-rubric.md`, `references/critic-prompt-template.md`) 재검토 여지

### Description
- 본 cycle에서는 변경 없음 (Decision F1 — 사용자 명시적 유지). false positive 모니터링은 사용자 책임.

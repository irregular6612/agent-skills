---
name: iterative-academic-writer
description: Use when writing academic documents — 논문 섹션(Introduction, Methods, Results, Discussion), 연구 제안서, SoP, 학업계획서, 기술 문서 — that require iterative quality improvement with hallucination prevention and 25-principle evaluation. Applies to any scholarly or research writing task. Triggers on phrases like "write my SoP", "help with paper", "주간 보고서 작성", "논문 작성 도와줘", "SoP 써줘", "연구 제안서 작성", "학업계획서 작성", "abstract 작성".
---

# Iterative Academic Writer

반복적 품질 개선 루프로 학술 문서를 작성한다. **Critic·Fact-Checker는 별도 subagent**로 격리해 평가하고, 계획·작성·수정은 메인 컨텍스트에서 수행한다.

## 출력 언어 규칙

모든 출력은 요청받은 언어(기본: 한국어/영어)로 작성한다. 영어 기술 용어는 원문 유지, LaTeX 수식·코드 변수명은 영어/라틴 표기.

---

## 문서 유형 감지 (Pre-Phase 0)

작성 시작 전 문서 유형을 결정하고 적절한 섹션 가이드를 선택한다.

| 유형                 | 식별 단서                                          | Phase 1·2 참조 가이드                      | 핵심 수사 목표                              |
| -------------------- | -------------------------------------------------- | ------------------------------------------ | ------------------------------------------- |
| **ML/CS 논문 섹션**  | Introduction/Methods/Results/Abstract, 논문, paper | `references/section-writing-guide.md`      | 기술적 기여를 동료 심사자에게 증명          |
| **연구 제안서**      | 제안서, 연구계획서, grant proposal, 과제신청서     | `references/proposal-writing-guide.md`     | 계획의 실현 가능성·가치를 심사위원에게 납득 |
| **SoP / 학업계획서** | SoP, 자기소개서, 학업계획서, statement of purpose  | `references/sop-writing-guide.md`          | 역량과 적합성을 입학사정관에게 어필         |
| **기술 문서**        | 기술 보고서, technical report, 매뉴얼, 설명서      | `references/section-writing-guide.md` 일부 | 독자가 절차를 따라 할 수 있도록 안내        |

**분기 지점**: Phase 1 Blueprint에서 해당 가이드의 섹션별 구조 공식을 적용한다.
유형마다 수사적 목표가 다르므로 동일한 25원칙을 다른 강도로 적용한다 — 상세는 각 가이드 참조.

---

## 아키텍처: 역할 분리 이유

| 역할                     | 실행 위치                          | 이유                                                          |
| ------------------------ | ---------------------------------- | ------------------------------------------------------------- |
| Fact Base 구축           | Main (inline)                      | 이후 모든 phase에서 공유 참조                                 |
| Blueprint 계획           | Main (inline)                      | Fact Base + 사용자 의도를 동시에 참조해야 함                  |
| 초안 작성                | Main (inline)                      | Blueprint를 직접 활용하며 생성                                |
| 품질 평가 (Critic)       | **Subagent** (`academic-reviewer`) | 격리된 시각 — 작성자 편향 없이 25원칙 적용                    |
| 사실 검증 (Fact-Checker) | **Subagent** (`general-purpose`)   | WebSearch + Fact Base 대조, context 분리로 hallucination 방지 |
| Issue Matrix 통합        | Main (inline)                      | 두 subagent 결과 병합·우선순위 결정                           |
| 재작성                   | Main (inline)                      | Issue Matrix 기반 수정                                        |

## 워크플로우

```
[Pre-Phase 0] 문서 유형 감지 → 가이드 선택
         ↓
[Phase 0] Fact Base 구축
         ↓
[Phase 1] Blueprint 계획 (inline, 선택 가이드 참조)
         ↓
[Phase 2] 초안 작성 (inline)
         ↓
    ┌────┴────────────────────────┐
    ↓                            ↓
[Phase 3a] Critic            [Phase 3b] Fact-Checker
(academic-reviewer           (general-purpose subagent,
 subagent)                    references/fact-checking-guide.md)
    ↓                            ↓
    └────────────┐   ┌───────────┘
                 ↓   ↓
        [Phase 4] Issue Matrix 통합 + 종료 조건 확인
                      ↓
    Critical=0 AND Hall=0 AND Unverifiable=0? ──→ ✅ COMPLETE
                      ↓ No
          [Phase 5] 재작성 ──────────→ Phase 3 (loop)
```

**Termination:**

- ✅ Success: `Critical == 0 AND Hallucinations == 0 AND Unverifiable == 0` (Warning 잔존 시 목록 출력; Warning > 5이면 수동 수정 권장 표시)
- ⚠️ Partial: `iteration >= 5 AND Hallucinations == 0 AND Unverifiable == 0 AND Critical > 0` → 현재 버전 출력 + 미해결 Critical·Warning 목록
- ❌ Failure: `iteration >= 5 AND (Hallucinations > 0 OR Unverifiable > 0)` → 출판 불가, 미검증 주장 목록 제시

---

## 평가 기준과 Critic 프롬프트

25개 원칙, C1–C9/W1–W17/S1–S3 분류, 언어·목록·통계 적용 규칙,
Insight 점수, Critic 프롬프트와 출력 형식은
`references/critic-review-protocol.md`를 **단일 기준**으로 사용한다.

- Phase 1 자체 검증과 Phase 2 작성에도 이 기준을 적용한다.
- Phase 3a 호출 전 위 파일 전체를 읽는다.
- 평가표나 프롬프트를 `SKILL.md` 또는 agent 파일에 복사하지 않는다.
- 제안서는 `references/proposal-writing-guide.md`, SoP·학업계획서는
  `references/sop-writing-guide.md`의 추가 원칙을 함께 적용한다.

---

## Phase 0: Fact Base 구축 (REQUIRED — inline)

**반드시 모든 fact를 수집하고 검증한 다음 글 작성을 시작해야 한다.**

### Step 0-1: 누락 정보 식별

사용자 요청 분석 후 다음을 식별한다:
- 검증 가능한 수치·인용·사실이 부족한 영역
- 문서 유형별 필수 source:
  - 논문: 결과 파일 (config, results, benchmark 출력)
  - 제안서: 예비 결과 + 팀 역량 evidence
  - SoP: 활동 transcript, 지원 program·교수·랩 정보

### Step 0-2: AskUserQuestion으로 보강 (필요 시)

누락 식별 시 `AskUserQuestion` 도구로 사용자에게 명시적 askback. 검증 가능한 출처가 이미 prompt에 명시된 경우는 skip.

예시 질문 형식:
- "Sparse Autoencoder 실험 결과 출처는 어디 있나요?" (옵션: 파일 경로 / 수치 제외 / 사용자 제공 결과로 명시하고 정확성 확인)
- "MIT EECS에서 어떤 교수·랩에 관심 있으신가요?" (SoP3 평가 필수)

사용자가 직접 제공하거나 확인한 정보는 `User-Attested`로 구분한다. 개인 경험·계획·선호는
사용자 진술을 1차 출처로 사용할 수 있다. 출판용 연구 수치·성능 주장은 결과 파일을 우선
확인하고, 파일이 없으면 사용자가 정확성을 명시적으로 확인한 경우에만
`(사용자 제공 — 독립 검증 안 됨)`으로 추적한다. 모델이 추론한 내용은 여기에 포함하지 않는다.

### Step 0-3: Fact Base 구축

자료 수집 (코드/결과 파일, 사용자 제공 자료, WebSearch) → 근거 수준을 구분해 기록.

### Sources to Check

| Source Type       | What to Extract      | Verification Method    |
| ----------------- | -------------------- | ---------------------- |
| Code/config files | Parameters, settings | Direct file inspection |
| Result files      | Metrics, numbers     | Direct file inspection |
| Papers/references | Citations, claims    | WebSearch verification |
| External facts    | Dates, statistics    | WebSearch verification |

### Fact Base 형식

```markdown
## Fact Base

### ✅ Verified Facts

| ID  | Claim                       | Source           | Verification    |
| --- | --------------------------- | ---------------- | --------------- |
| F1  | Learning rate is 0.03       | config.yaml:12         | Code inspection     |
| F2  | Titans paper published 2025 | arXiv:2501.00663       | WebSearch           |
| F3  | RCT 환자 표본 1,245명       | trial-protocol.pdf:p.4 | Document inspection |

### 🟦 User-Attested Facts

| ID | Claim | Source | Allowed Use |
| --- | --- | --- | --- |
| U1 | 사용자가 RLHF 인턴을 1년 수행함 | 사용자 직접 진술 | SoP의 개인 경험 |
| U2 | 내부 실험 결과가 12.3% 향상임 | 사용자 확인 — 독립 검증 안 됨 | 사용자 제공 결과임을 추적하여 사용 |

### ❌ Unverified (DO NOT USE IN DOCUMENT)

| Claim              | Reason                  |
| ------------------ | ----------------------- |
| "15% improvement"  | No result file found    |
| "State-of-the-art" | No benchmark comparison |
```

**Rules:**

1. 모든 수치는 source 또는 명시적 사용자 확인 필수 — 근거 없는 통계는 작성 금지
2. 인용 논문은 WebSearch 검증 필수 — hallucinated paper 불가
3. 문서에는 `Verified` 또는 허용 범위가 명시된 `User-Attested` 정보만 사용한다
4. `Unverified` 주장은 표현을 약하게 바꾸어 남기지 말고 주장 전체를 제거한다
5. **When in doubt, don't include — omission > hallucination**

### After Phase 0

```
→ Phase 1 (Blueprint 계획)으로 진행
```

### Hallucination Types 빠른 참조

| 유형                   | 예시                        | 탐지 방법               |
| ---------------------- | --------------------------- | ----------------------- |
| Invented numbers       | "15% improvement"           | Fact Base에 없음        |
| False attribution      | "Smith et al. showed..."    | WebSearch로 주장 미확인 |
| Fabricated details     | "Published in March 2024"   | 날짜 검증 불가          |
| Exaggerated claims     | "Significantly outperforms" | 비교 데이터 없음        |
| Causal hallucination   | "X caused Y"                | 인과 근거 없음          |
| Citation hallucination | "arXiv:2401.99999"          | 논문 존재하지 않음      |

---

## Phase 1: Blueprint 계획 (inline)

Planning은 메인 컨텍스트에서 수행한다. 섹션별 구조 공식은 `references/section-writing-guide.md`를 참조한다.

### Blueprint 작성 항목

1. **전체 구조** — 섹션별 핵심 메시지 한 문장
2. **두괄식 첫 문장** — 각 문단의 핵심 주장은 문단 처음으로 배치
3. **정의 목록** — "X는 Y이다" 형식의 전문 용어 정의 초안
4. **비교-대조 목록** — "기존 A vs 제안 B" 비교 포인트

### Blueprint 출력 템플릿

전체 마크다운 템플릿은 `references/blueprint-template.md`를 참조한다.

### Blueprint 자체 검증

| 항목                                                               | 요건  |
| ------------------------------------------------------------------ | ----- |
| 모든 전문 용어가 정의 목록에 있는가?                               | ✅/❌ |
| 새로운 방법/개념에 비교-대조가 계획되었는가?                       | ✅/❌ |
| 각 문단 첫 문장이 핵심 주장인가?                                   | ✅/❌ |
| Fact Base에 없는 내용을 Blueprint에 포함하지 않았는가?             | ✅/❌ |
| 각 섹션의 새 방법/기법에 "왜 필요한가" 동기(IS1)가 계획되었는가?   | ✅/❌ |
| 주요 인과 관계 ("A이므로 B, 따라서 C", IS2)가 계획에 포함되었는가? | ✅/❌ |

**재작성 임계값**: FA/IS 항목 1개라도 미충족 시 즉시 재작성. 나머지 항목은 3개 이상 미충족 시 재작성. **최대 2회** (Blueprint 단계 내부 한정 — 전체 워크플로우의 `iteration >= 5` 카운터와는 별개).

### After Phase 1

→ Phase 2 (초안 작성)으로 진행

---

## Phase 2: 초안 작성 (inline)

Blueprint 구조를 따라 **Pre-Phase 0에서 선택한 가이드**(논문→`references/section-writing-guide.md`, 제안서→`references/proposal-writing-guide.md`, SoP→`references/sop-writing-guide.md`)의 컨벤션에 맞게 작성한다.

**작성 중 인라인 Fact Check:**

```
✍️ Writing: "LTPO는 learning rate 0.03을 사용한다"
   → Fact check: F1 ✓ → 포함 가능

✍️ Writing: "이를 통해 15% 성능 향상을 달성했다"
   → Fact check: NOT IN FACT BASE ❌ → 작성 금지
   → 대안: 향상 방향도 검증되지 않았다면 문장 전체 삭제
   → "평가 실험을 수행했다"도 실험 수행 사실이 Fact Base에 있을 때만 사용
```

### After Phase 2

→ Phase 3 (병렬 평가)으로 진행 — 3a Critic + 3b Fact-Checker를 단일 메시지에 동시 호출

---

## Phase 3: 평가 (병렬 Subagent 2개)

초안 완성 후 두 subagent를 **동시에** 호출한다. 두 작업은 독립적이므로 단일 메시지에 두 Agent tool call을 포함해 병렬 실행한다.

### Phase 3a: Critic Subagent (academic-reviewer)

**Step 1: Hallucination 보조 catch (Fail-safe)** — Hallucination 정식 책임은 Fact-Checker(3b)에 있다. Critic은 평가 중 명백한 Fact Base 위반을 발견하면 C1으로 함께 보고한다 (양쪽 catch는 Phase 4 Issue Matrix에서 자동 병합).

**Step 2: 25원칙 품질 평가** — 먼저
`references/critic-review-protocol.md` 전체와 문서 유형별 추가 가이드를 읽는다.

**Step 3: Critic 호출** — 위 protocol의 `Critic Prompt Template`에 다음 항목을
채워 `academic-reviewer`를 호출한다.

- protocol의 절대 경로
- 문서 유형과 요청 언어
- 해당 문서 유형 가이드의 절대 경로 또는 `없음`
- Verified/User-Attested/Unverified를 모두 포함한 Fact Base
- Phase 2 초안 전체

평가표, Warning catalog, 출력 예시는 프롬프트에 다시 복사하지 않는다.

### Phase 3b: Fact-Checker Subagent (general-purpose)

사실 검증 전담. 검증 절차는 `references/fact-checking-guide.md`를 따른다.

```
Agent 호출:
  subagent_type: "general-purpose"
  prompt: |
    Fact Base와 초안의 모든 사실적 주장을 대조해 hallucination을 검출하세요.
    검증 절차: references/fact-checking-guide.md 참조.

    [Fact Base]: (Phase 0 Fact Base 전체 — ✅ Verified, 🟦 User-Attested, ❌ Unverified 포함)
    [문서 내용]: (Phase 2 초안 전체)

    출력:
    ### Claim Verification
    | Location | Claim | Fact Base ID | Evidence | Status |
    ### Summary: Total/Verified/User-Attested/Hallucinations(MUST BE 0)/Unverifiable(MUST BE 0)
```

---

## Phase 4: Issue Matrix 통합 및 수정 계획 (inline)

두 subagent 결과를 통합해 **Issue Matrix**를 작성한다. 같은 위치의 이슈는 병합한다.

### Issue Matrix 형식

```markdown
## Issue Matrix (Iteration N/5)

| ID  | Location      | Issue                                               | Severity      | Status |
| --- | ------------- | --------------------------------------------------- | ------------- | ------ |
| C1  | Para 2        | "15% improvement" — NOT IN FACT BASE (Fact-Checker) | 🔴 Critical   | OPEN   |
| C3  | Intro 1문단   | "최근 연구에서는..." — 두괄식 위반 (Critic)         | 🔴 Critical   | OPEN   |
| C4  | Methods 3문단 | "SAE" 정의 없이 사용 (Critic)                       | 🔴 Critical   | OPEN   |
| W4  | Methods 2문단 | "매우 효과적인" — 수치 없이 사용 (Critic)           | 🟡 Warning    | OPEN   |
| W2  | Sec 2 전체    | 기존 방법과 비교-대조 없음 (Critic)                 | 🟡 Warning    | OPEN   |
| S1  | Para 2→3      | 전환 접속어 추가 권장 (Critic)                      | 🔵 Suggestion | OPEN   |
```

### 종료 조건 확인

> **iteration counter**: 1부터 시작 (첫 Critic 실행이 iteration 1). `iteration >= 5`는 5회차 실행 직후 평가 시점.

```
IF Critical == 0 AND Hallucinations == 0 AND Unverifiable == 0:
    → ✅ COMPLETE — 아래 ✅ Success 출력 포맷으로 최종 문서 출력
    → Warning > 0이면: 잔여 Warning 목록 출력 (선택적 수정)
    → Warning > 5이면: "품질 개선 권장 — 잔여 Warning이 많습니다" 추가 표시
    → Suggestion > 0이면: 잔여 Suggestion 목록 출력 (처리 여부 사용자에게 제안)

ELIF iteration >= 5 AND Hallucinations == 0 AND Unverifiable == 0:
    → ⚠️ PARTIAL (Critical 잔존) — 현재 버전 출력 + 미해결 Critical 목록 + Warning 목록

ELIF iteration >= 5 AND (Hallucinations > 0 OR Unverifiable > 0):
    → ❌ FAILURE — 출판 불가
    → 아래 포맷으로 미검증 주장 목록 출력 후 사용자에게 판단 요청

ELSE:
    → CONTINUE → Phase 5
```

### ✅ Success 출력 포맷

```markdown
## ✅ Document Complete (Iteration N/5)

[최종 문서 본문]

---

### 잔여 이슈 (선택적 수정)

| ID  | Location | Issue           | Severity      |
| --- | -------- | --------------- | ------------- |
| W4  | Para 3   | "매우 효과적인" | 🟡 Warning    |
| S2  | Para 5   | 예시 추가 권장  | 🔵 Suggestion |

수정이 필요한 항목이 있으면 말씀해주세요.
```

### ❌ Failure 출력 포맷

```markdown
## ❌ Cannot Publish

다음 주장들을 검증할 수 없어 출판이 불가합니다.
출처를 제공하거나 삭제에 동의해주세요:

| Claim             | Location | Reason            |
| ----------------- | -------- | ----------------- |
| "15% improvement" | Para 2   | No source found   |
| "2x faster"       | Para 5   | No benchmark data |
```

### 수정 계획 (우선순위)

```
Priority 1: C1/C2 (Hallucination) — 즉시 삭제 or Fact Base 확인 후 대체
Priority 2: C3~C8 (Other Critical) — 구체적 수정 방향 명시
Priority 3: W1~W12 (Warning) — 반복 예산 허용 시
```

---

## Phase 5: 재작성 (inline)

Issue Matrix의 우선순위에 따라 수정한다. 수정 후 새로운 hallucination이 생기지 않았는지 확인하고 Phase 3으로 돌아간다.

### Hallucination 처리 결정 구조

C1/C2 수정 시 반드시 아래 두 옵션 중 하나를 선택한다:

```
Option A (주장 제거):
  미검증 명제 전체를 삭제한다. 수치만 지우고 같은 의미의 정성 주장으로 바꾸지 않는다.
  Before: "이를 통해 15%의 성능 향상을 달성했다."
  After:  [문장 삭제]
  단, 향상 방향이 별도 근거로 검증되었다면 그 근거 범위 안에서만 정성 표현을 쓴다.

Option B (검증 후 업데이트):
  Action: 결과 파일 또는 원본 논문에서 실제 수치 확인
  If found → Fact Base에 추가(출처 명시) 후 문장 업데이트
  If not found → Option A 적용
```

### 수정 로그 형식

각 이슈 수정 시:

```markdown
### Fix: [C1] Para 2 — "15% improvement" hallucination

**원문**: "이를 통해 15%의 성능 향상을 달성했다."
**조치**: 향상 폭과 방향 모두 미검증이므로 주장 전체 삭제
**수정**: [문장 삭제]
**Issue Matrix**: C1 → RESOLVED
```

### After Phase 5

→ Phase 3 (병렬 평가)으로 복귀 — 수정 후 새로운 hallucination 유입 여부를 재확인

---

## 진행 상황 보고

각 Iteration 완료 시 사용자에게 보고한다:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ITERATIVE ACADEMIC WRITER — Progress Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Phase 0] Fact Base: 12 verified | 2 excluded (미검증)
[Phase 1] Blueprint: 4 sections | 8 terms | 3 comparisons

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Convergence Tracker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Iter | Critical | Warning | Hallu | Δ Critical | Status   |
|------|----------|---------|-------|------------|----------|
| 1    | 3        | 4       | 2     | —          | CONTINUE |
| 2    | 0        | 2       | 0     | -3         | COMPLETE |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Iteration 1/5]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 3a Critic:       C=3 | W=4 | S=1
Phase 3b Fact-Checker: Hallucinations=2 | Verified=10 | Unverifiable=1
Insight Matrix:        IS1 missing×1 (Methods), IS3 missing×1 (Intro)
Status: CONTINUE → Priority fix: 2 hallucinations (C1×2), then C4, W13

Phase 5: Rewrite ✓ (removed 2 unverified claims, defined SAE, added WHY to Methods)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Iteration 2/5]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 3a Critic:       C=0 | W=2 | S=0
Phase 3b Fact-Checker: Hallucinations=0 | Verified=12
Insight Matrix:        All ✅
Status: ✅ COMPLETE

✅ 최종 문서 완성 (잔여: W2, W4 — 선택적 수정 가능)
```

---

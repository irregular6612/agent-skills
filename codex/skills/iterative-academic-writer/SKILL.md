---
name: iterative-academic-writer
description: Draft and iteratively improve academic documents such as paper sections, proposals, SoPs, study plans, and abstracts.
---

# Iterative Academic Writer

## Codex Subagent Compatibility

Legacy Claude invocation snippets in this skill should be interpreted as Codex subagent workflow guidance, not literal Claude Code API calls.

- Spawn subagents only when the user explicitly asks for subagents or parallel agent work, or when the active Codex surface exposes an equivalent explicit subagent workflow.
- Prefer a matching custom agent in `~/.codex/agents/*.toml`; otherwise use Codex built-ins (`explorer` for read-heavy scans, `worker` for implementation, `default` for general roles) with the role prompt as task guidance.
- Do not pass Claude model aliases such as `haiku`, `sonnet`, or `opus` to Codex. Custom agents inherit the parent model unless their TOML file intentionally sets a Codex-supported field such as `model_reasoning_effort`.
- Keep parallel write scopes disjoint; if that is not possible, do the work in the main context and use subagents only for review or read-heavy analysis.


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
          Critical=0 AND Hall=0? ──→ ✅ COMPLETE
                      ↓ No
          [Phase 5] 재작성 ──────────→ Phase 3 (loop)
```

**Termination:**

- ✅ Success: `Critical == 0 AND Hallucinations == 0` (Warning 잔존 시 목록 출력; Warning > 5이면 수동 수정 권장 표시)
- ⚠️ Partial: `iteration >= 5 AND Hallucinations == 0 AND Critical > 0` → 현재 버전 출력 + 미해결 Critical·Warning 목록
- ❌ Failure: `iteration >= 5 AND Hallucinations > 0` → 출판 불가, 미검증 주장 목록 제시

---

## 25 Principles (15 Original + 5 Naturalness + 4 Insight + FM5)

### Factual Accuracy (사실성) — HIGHEST PRIORITY

| ID  | Principle               | Violation                                  |
| --- | ----------------------- | ------------------------------------------ |
| FA1 | **Fact-based claims**   | Claim not in Fact Base                     |
| FA2 | **No invented numbers** | Metrics/statistics without verified source |
| FA3 | **Verified citations**  | Paper reference not WebSearch-verified     |

### Structure (구조)

| ID  | Principle                       | Violation                                              |
| --- | ------------------------------- | ------------------------------------------------------ |
| ST1 | **Topic-first (두괄식)**        | Paragraph starts with background instead of main claim |
| ST2 | **Purpose-driven opening**      | Section doesn't state why it exists                    |
| ST3 | **Implication-focused closing** | Section ends without significance                      |
| ST4 | **Figure/table reference**      | Visual used without "Figure X shows..."                |

### Understandability (이해도)

| ID  | Principle                | Violation                                                                                                                                             |
| --- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| UN1 | **Definition-first**     | Technical term used before "X is Y" definition                                                                                                        |
| UN2 | **Compare-contrast**     | New approach without comparing to existing                                                                                                            |
| UN3 | **Smart-but-unfamiliar** | 도메인 외부 독자(지적 수준은 높으나 세부 전문 지식 없음)가 선택의 동기를 추론해야 이해 가능한 서술 — "왜 이 방법인가"가 없어 외부인이 납득하기 어려움 |
| UN4 | **Coherent flow**        | Missing logical connectors between paragraphs                                                                                                         |

### Format (형식)

| ID  | Principle                 | Violation                                                                 |
| --- | ------------------------- | ------------------------------------------------------------------------- |
| FM1 | **Conciseness**           | Unnecessary modifiers (매우, very, extremely)                             |
| FM2 | **Specific numbers**      | Vague quantifiers (많은, some, several)                                   |
| FM3 | **Prose only**            | Bullet points in body text                                                |
| FM4 | **Abstract-level**        | Exposes file paths, function names                                        |
| FM5 | **Statistical reporting** | Numeric results reported without 95% CI or std.err (Agarwal et al., 2021) |

### Naturalness (자연스러움)

| ID  | Principle               | Violation                                             |
| --- | ----------------------- | ----------------------------------------------------- |
| NL1 | **번역체 금지**         | "~함으로써", "~에 있어서" 등 영어 직역 구조           |
| NL2 | **과잉 수사 금지**      | "혁신적인", "수렴하고 있다" 등 내용 대비 포장 큰 표현 |
| NL3 | **한 문장 한 아이디어** | 동사 3개 이상 나열, 과압축 문장                       |
| NL4 | **단어 반복 금지**      | 인접 문장에서 동일 단어 중복                          |
| NL5 | **접속사 다양성**       | "그러나", "따라서"가 매 문단 기계적 반복              |

### Insight (인사이트) — paper-digest 기반

| ID  | Principle                      | Violation                                                                                                                                                    |
| --- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| IS1 | **Motivation-before-method**   | 기법/방법이 "왜 필요한지" 설명 없이 등장 ("이렇게 했다"만 있고 "왜"가 없음)                                                                                  |
| IS2 | **Cause-and-effect chain**     | 단계가 인과 관계 없이 순서만 나열됨 ("A이므로 B, 따라서 C" 구조 부재)                                                                                        |
| IS3 | **Concrete instantiation**     | 추상적 개념에 구체적 예시나 비유가 없어 독자가 직관적으로 이해하기 어려움                                                                                    |
| IS4 | **Document-level insight arc** | 섹션/문서가 Context(왜 이 문제인가)→Insight(기존이 놓친 핵심 가정·발견)→Solution(자연스러운 방법 도출)→Evidence 구조 없이 배경 나열이나 절차 기술로만 전개됨 |

## Issue Classification

### 🔴 Critical (blocks completion — must fix)

| ID  | Issue                                                                       | Principle | 채점 기준 |
| --- | --------------------------------------------------------------------------- | --------- | --------- |
| C1  | Hallucination — Fact Base에 없는 주장                                       | FA1/FA2   | 0=발견 / 1=없음 (binary) |
| C2  | Fact contradiction — Fact Base와 모순                                       | FA1       | 0=발견 / 1=없음 (binary) |
| C3  | Topic-first violation                                                       | ST1       | 0=배경/일반론으로 시작 / 1=배경 후 주장 / 2=첫 문장이 핵심 주장 |
| C4  | Undefined technical term                                                    | UN1       | 0=용어 등장 후 정의 없음 / 1=같은 문단 후반 정의 / 2=첫 등장 시 "X는 Y이다" 즉시 정의 |
| C5  | Smart-but-unfamiliar reader cannot grasp the reasoning behind choices       | UN3       | 0=선택 동기 부재 / 1=동기 암시만 / 2=명시적 "X 한계로 인해 Y 선택" |
| C6  | Logical disconnect between paragraphs                                       | UN4       | 0=문단 간 인과 부재 / 1=일부 접속어 / 2=명시적 전제→결론 체인 |
| C7  | Bullet points in prose                                                      | FM3       | 0=본문 bullet 사용 / 1=주변 prose 보완 있음 / 2=완전 prose |
| C8  | Translation-style sentence structure                                        | NL1       | 0=명백한 직역체 / 1=일부 자연스러움 / 2=한국어 자연 |
| C9  | Methods/contribution section introduces technique without WHY it was needed | IS1       | 0=기법만 / 1=약한 동기 / 2=명확한 인과 (Methods 한정) |

> **IS1 분류 비대칭**: C9(Critical)은 Methods 섹션 한정 — 논문의 핵심 기술 기여 위치에서 "왜 이 방법이 필요한가"가 없으면 독자가 기술적 선택을 납득할 수 없어 신뢰성에 치명적이다. Introduction·Discussion 등 다른 섹션의 동일 위반은 W13(Warning) — 읽기 경험을 해치지만 기술적 검증과 분리 가능하다.

### 🟡 Warning (should fix)

| ID  | Issue                                                                | Principle |
| --- | -------------------------------------------------------------------- | --------- |
| W1  | Unverified citation                                                  | FA3       |
| W2  | Missing compare-contrast                                             | UN2       |
| W3  | No implication at section end                                        | ST3       |
| W4  | Vague modifiers                                                      | FM1       |
| W5  | Purpose unclear at section start                                     | ST2       |
| W6  | Vague quantifiers                                                    | FM2       |
| W7  | Code elements exposed                                                | FM4       |
| W8  | Figure/table without reference                                       | ST4       |
| W9  | Overblown rhetoric                                                   | NL2       |
| W10 | Overloaded sentence (3+ verbs)                                       | NL3       |
| W11 | Word repetition in adjacent sentences                                | NL4       |
| W12 | Mechanical connector pattern                                         | NL5       |
| W13 | Method/technique introduced without WHY it was needed                | IS1       |
| W14 | Steps presented without causal logic ("because"/"therefore" missing) | IS2       |
| W15 | Abstract concept without concrete example or analogy                 | IS3       |
| W16 | Section Insight Narrative Score < 5/8 (insight-poor narrative)       | IS1–IS4   |
| W17 | Numeric results reported without CI or std.err                       | FM5       |

### 🔵 Suggestion (optional)

| ID  | Issue                |
| --- | -------------------- |
| S1  | Add connective words |
| S2  | Add example/analogy  |
| S3  | Simplify sentence    |

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
- "Sparse Autoencoder 실험 결과 출처는 어디 있나요?" (옵션: 파일 경로 / 정성 서술로 진행 / prompt 수치 잠정 사용 ⚠️)
- "MIT EECS에서 어떤 교수·랩에 관심 있으신가요?" (SoP3 평가 필수)

사용자가 ⚠️ 잠정 사용을 선택하면 Fact Base에 임시 등록하되 출처 컬럼에 `(사용자 prompt — 미검증)` 명시.

### Step 0-3: Fact Base 구축

자료 수집 (코드/결과 파일, 사용자 제공 자료, WebSearch) → 검증된 사실만 기록.

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

### ❌ Unverified (DO NOT USE IN DOCUMENT)

| Claim              | Reason                  |
| ------------------ | ----------------------- |
| "15% improvement"  | No result file found    |
| "State-of-the-art" | No benchmark comparison |
```

**Rules:**

1. 모든 수치는 출처 필수 — 출처 없는 통계는 작성 금지
2. 인용 논문은 WebSearch 검증 필수 — hallucinated paper 불가
3. 미검증 주장은 문서에 불가 — Fact Base에 없으면 쓰지 않는다
4. **When in doubt, don't include — omission > hallucination**

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
   → 대안: "실험을 통해 성능 향상을 확인했다" (수치 생략)
```

### After Phase 2

→ Phase 3 (병렬 평가)으로 진행 — 3a Critic + 3b Fact-Checker를 단일 메시지에 동시 호출

---

## Phase 3: 평가 (병렬 Subagent 2개)

초안 완성 후 두 subagent를 **동시에** 호출한다. 두 작업은 독립적이므로 단일 메시지에 두 Agent tool call을 포함해 병렬 실행한다.

### Phase 3a: Critic Subagent (academic-reviewer)

**Step 1: Hallucination 보조 catch (Fail-safe)** — Hallucination 정식 책임은 Fact-Checker(3b)에 있다. Critic은 평가 중 명백한 Fact Base 위반을 발견하면 C1으로 함께 보고한다 (양쪽 catch는 Phase 4 Issue Matrix에서 자동 병합).

**Step 2: 25원칙 품질 평가** — FA/ST/UN/FM/NL/IS 체계로 전체 검토한다.

```
Agent tool 호출:
  agent: "academic-reviewer"
  prompt: |
    다음 학술 문서를 25개 원칙(FA/ST/UN/FM/NL/IS)에 따라 평가해주세요.

    [Fact Base]:
    (Phase 0에서 작성한 Fact Base 표 전체를 여기 복사. ✅ Verified Facts 표와 ❌ Unverified 목록 모두 포함.)

    [문서 내용]:
    (Phase 2에서 완성한 초안 전체를 여기 복사.)

    [문서 유형 추가 원칙] (Pre-Phase 0에서 결정한 유형에 따라 해당 표만 평가에 포함하세요):

    논문 섹션이면 → 추가 원칙 없음. 25원칙으로만 평가.

    연구 제안서면 → 아래 PR1-PR5도 평가하여 Warning 섹션에 [PR1] 등으로 분류:
    | ID  | 원칙                   | 위반 예시                               |
    | --- | ---------------------- | --------------------------------------- |
    | PR1 | 목표 SMART화           | "성능을 향상시킬 것이다"                |
    | PR2 | 실현 가능성 증거       | 예비 결과·팀 역량 없이 큰 목표만 제시  |
    | PR3 | 위험 및 대안 계획      | 대안 없이 낙관적 서술                  |
    | PR4 | 미래형 시제 일관성     | "발견했다" 등 과거형 혼용              |
    | PR5 | 파급효과 구체화        | "사회에 큰 기여" 식 수사               |

    SoP/학업계획서면 → 아래 SoP1-SoP5도 평가. **SoP1·SoP3 위반은 Critical 격상**:
    | ID   | 원칙                       | 위반 예시                                  |
    | ---- | -------------------------- | ------------------------------------------ |
    | SoP1 | Narrative arc              | 인과 없는 활동 병렬 진술                  |
    | SoP2 | Specific evidence          | "강한 문제 해결 능력" 측정 불가           |
    | SoP3 | Fit signal                 | program/lab/교수 언급 없는 일반 진술      |
    | SoP4 | Future-back reasoning      | 미래 목표가 과거 경험과 미연결            |
    | SoP5 | First-person grounding     | "팀이 X" 본인 기여 모호                   |

    [채점 기준 — Critical 평가 시 이 표를 그대로 적용]
    | ID | Score 0 | Score 1 | Score 2 |
    | --- | --- | --- | --- |
    | C1 | 발견 | 없음 | n/a (binary) |
    | C2 | 발견 | 없음 | n/a (binary) |
    | C3 | 배경/일반론으로 시작 | 배경 후 주장 | 첫 문장이 핵심 주장 |
    | C4 | 용어 등장 후 정의 없음 | 같은 문단 후반 정의 | 첫 등장 시 즉시 정의 |
    | C5 | 선택 동기 부재 | 동기 암시만 | "X 한계로 Y 선택" 명시 |
    | C6 | 문단 간 인과 부재 | 일부 접속어 | 명시적 전제→결론 체인 |
    | C7 | 본문 bullet 사용 | 주변 prose 보완 | 완전 prose |
    | C8 | 명백한 직역체 | 일부 자연스러움 | 한국어 자연 |
    | C9 | 기법만 | 약한 동기 | 명확한 인과 (Methods 한정) |

    [Warning catalog — 위반 시 다음 ID 중 정확히 매칭]
    | ID  | Issue                                                      | Principle |
    | --- | ---------------------------------------------------------- | --------- |
    | W1  | Unverified citation                                        | FA3       |
    | W2  | Missing compare-contrast                                   | UN2       |
    | W3  | No implication at section end                              | ST3       |
    | W4  | Vague modifiers                                            | FM1       |
    | W5  | Purpose unclear at section start                           | ST2       |
    | W6  | Vague quantifiers                                          | FM2       |
    | W7  | Code elements exposed                                      | FM4       |
    | W8  | Figure/table without reference                             | ST4       |
    | W9  | Overblown rhetoric                                         | NL2       |
    | W10 | Overloaded sentence (3+ verbs)                             | NL3       |
    | W11 | Word repetition in adjacent sentences                      | NL4       |
    | W12 | Mechanical connector pattern                               | NL5       |
    | W13 | Method/technique introduced without WHY (non-Methods)      | IS1       |
    | W14 | Steps without causal logic ("because"/"therefore" missing) | IS2       |
    | W15 | Abstract concept without concrete example                  | IS3       |
    | W16 | Section Insight Narrative Score < 5/8                      | IS1–IS4   |
    | W17 | Numeric results without CI or std.err                      | FM5       |

    각 이슈를 다음 ID로 분류해 보고하세요:
    - Critical (C1~C9): issue ID, 위치, 원문 인용, **채점(N/2)**, 수정 제안 — 위 표의 점수가 1 이하면 Critical 보고 대상.
    - Warning  (W1~W17): issue ID, 위치, 원문 인용, 수정 제안 — **반드시 위 catalog의 정확한 W ID로 매칭** (임의 ID 부여 금지)
    - Suggestion (S1~S3): issue ID, 위치

    출력 형식:
    ### 🔴 Critical
    - [C3] Introduction 1문단: "최근 연구에서는..." (score 0/2) → 핵심 주장으로 시작해야 함
    ### 🟡 Warning
    - [W4] Methods 2문단: "매우 효과적인" → 구체적 수치로 대체
    - [W13] Methods 3문단: proposed method가 왜 필요한지 설명 없이 도입됨
    - [PR1] (제안서 한정) 연구목표 섹션: 측정 불가 표현 → SMART 목표로
    - [SoP3] (SoP 한정) Fit 섹션: 지원 교수·랩 미언급 → 구체 인용
    ### 🔵 Suggestion
    - [S1] Para 2→3: 전환 접속어 추가 권장

    ### Insight Narrative Score
    각 주요 섹션에 대해 0(없음)/1(약함)/2(강함)으로 평가하세요:

    채점 기준:
    - IS1 (0=WHY 없음 / 1=약한 동기 "~가 필요하다" / 2=명확한 인과 "X의 한계로 인해 Y가 필요하다")
    - IS2 (0=단계 나열만 / 1=일부 인과어 "따라서" / 2=완전한 A→B→C 체인)
    - IS3 (0=순수 추상 / 1=부분 예시 / 2=독자가 직관적으로 이해 가능한 구체적 비유·사례)
    - IS4 (0=배경·관련연구 나열로 시작 / 1=문제로 시작하나 Insight 없이 방법으로 직행 / 2=Context(문제)→Insight(기존이 놓친 핵심 가정·발견)→Solution(자연스러운 도출)→Evidence 구조)

    | Section | IS1 WHY (0-2) | IS2 Chain (0-2) | IS3 Example (0-2) | IS4 Arc-open (0-2) | Total (/8) | Verdict |
    |---------|---------------|-----------------|-------------------|---------------------|------------|---------|
    | [섹션명] |               |                 |                   |                     |            | ✅/🟡/🔴 |

    총점 해석: 7-8=✅ Insight-driven / 5-6=🟡 Adequate / 0-4=🔴 W16 발행
    IS1 위반이 Methods 섹션에 있으면 W13 대신 C9로 분류하세요.
    IS1-IS4 위반은 각각 W13/W14/W15/W16으로 분류해 Warning 섹션에 포함하세요.

    [출력 규칙 — 반드시 준수]
    1. **JSON 출력 금지** — 위 형식의 마크다운만 사용. ```json 블록 삽입 금지.
    2. **pass/fail 판단 금지** — "Pass: false" / "Overall Score: N" 등 verdict 출력 금지. 종료 조건 판단은 orchestrator(Phase 4) 책임.
    3. **채점 형식 의무** — Critical 모든 항목에 `(score N/2)` 표기. binary(C1/C2)는 `(score 0/1)`.
    4. **위치 구체화** — "Methods 3문단", "Introduction 2번째 문장" 등 정확한 위치 표기.
    5. **원문 인용 필수** — 짧은 위반 부분을 따옴표로 인용.
    6. **수정 제안 구체화** — "개선하세요" 같은 추상 제안 금지. "X로 대체" / "Y 추가" 등 구체.
```

### Phase 3b: Fact-Checker Subagent (general-purpose)

사실 검증 전담. 검증 절차는 `references/fact-checking-guide.md`를 따른다.

```
Agent 호출:
  agent: "general-purpose"
  prompt: |
    Fact Base와 초안의 모든 사실적 주장을 대조해 hallucination을 검출하세요.
    검증 절차: references/fact-checking-guide.md 참조.

    [Fact Base]: (Phase 0 Fact Base 전체 — ✅ Verified 표와 ❌ Unverified 목록 포함)
    [문서 내용]: (Phase 2 초안 전체)

    출력:
    ### Claim Verification
    | Location | Claim | Fact Base ID | Status |
    ### Summary: Total/Verified/Hallucinations(MUST BE 0)/Unverifiable
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
IF Critical == 0 AND Hallucinations == 0:
    → ✅ COMPLETE — 아래 ✅ Success 출력 포맷으로 최종 문서 출력
    → Warning > 0이면: 잔여 Warning 목록 출력 (선택적 수정)
    → Warning > 5이면: "품질 개선 권장 — 잔여 Warning이 많습니다" 추가 표시
    → Suggestion > 0이면: 잔여 Suggestion 목록 출력 (처리 여부 사용자에게 제안)

ELIF iteration >= 5 AND Hallucinations == 0:
    → ⚠️ PARTIAL (Critical 잔존) — 현재 버전 출력 + 미해결 Critical 목록 + Warning 목록

ELIF iteration >= 5 AND Hallucinations > 0:
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
  미검증 수치·주장을 삭제하고 검증 가능한 표현으로 대체
  Before: "이를 통해 15%의 성능 향상을 달성했다."
  After:  "실험을 통해 성능 향상을 확인하였다." (수치 생략)

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
**조치**: 미검증 수치 삭제
**수정**: "실험을 통해 성능 향상을 확인하였다."
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

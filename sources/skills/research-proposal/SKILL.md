---
name: research-proposal
description: "연구 아이디어를 기반으로 종합 연구 계획서를 작성합니다. 선행 연구 조사, 아이디어 구체화(가설/RQ 분리), 학술 비평 피드백 루프, 학계 기여도 평가, 상세 실험 설계(변인통제/GPU 리소스/Gantt 일정/대비책)를 포함합니다. Use when: '연구 계획서 작성', 'research proposal', '실험 계획 세워줘', '연구 제안서', '/research-proposal'. 사용자가 연구 아이디어와 실험 방향을 제시하면 구체적인 연구 계획서로 발전시킵니다."
---

# Research Proposal

연구 아이디어를 종합 연구 계획서로 발전시키는 스킬입니다.

## Description

사용자의 연구 아이디어와 실험 방향을 입력받아, 선행 연구 조사 → 아이디어 구체화 → 학술 비평 피드백 루프 → 기여도 평가 → 상세 실험 설계를 거쳐 **종합 연구 계획서**를 생성합니다. 5개의 전문 에이전트가 파이프라인으로 동작하며, 결과는 한국어로 작성됩니다 (영어 기술 용어 유지).

## User Invocation

Use this skill when the user says things like:
- "연구 계획서 작성해줘"
- "research proposal"
- "/research-proposal"
- "실험 계획 세워줘"
- "연구 제안서 작성"
- "이 아이디어로 연구 계획서 만들어줘"
- "연구 계획 구체화해줘"

## Arguments

사용자에게서 다음 정보를 받습니다:
1. **연구 아이디어** (필수): 연구 주제, 아이디어, 방향
2. **연구 분야** (필수): 해당 학술 분야
3. **실험 방향** (선택): 어떤 실험을 하고 싶은지, 대략적 방법론
4. **논문 디렉토리** (선택): 관련 논문 요약이 있는 경로 (기본값: `output/`)
5. **출력 경로** (선택): 계획서 저장 위치
6. **시작일** (선택): 연구 시작 예상일 (기본값: 오늘 날짜)
7. **target_audience** (선택): 제안서 대상 기관 (NSF / NIH / General / Thesis, 기본값: General)
8. **preliminary_data** (선택): 예비 결과 데이터 경로 또는 설명 (있으면 예비 결과 섹션 포함)

## 하네스별 실행 (Claude Code / Codex)

이 스킬은 두 하네스에서 같은 원본으로 돈다. 차이는 아래 셋뿐이다.

- **사용자에게 묻기**: 아래 `AskUserQuestion` 예시는 질문과 선택지의 내용이다. Claude Code 는 AskUserQuestion 도구로, Codex 는 채팅으로 같은 질문과 선택지를 내고 답을 기다린다.
- **역할 에이전트**: `역할: "background-researcher"` 같은 이름(background-researcher, idea-concretizer, academic-critic, contribution-assessor, experiment-designer, mermaid-validator)은 별도 에이전트 파일이 없다. 각 역할이 할 일은 그 단계의 prompt 에 있다. Claude Code 는 Agent 도구의 `general-purpose` 에이전트에, Codex 는 내장 에이전트(읽기 위주면 `explorer`, 그 밖은 `default`)에 "역할 이름 + 그 단계 prompt" 를 넘긴다. "동시에" 라고 적힌 호출은 병렬로 실행한다. `model="haiku"` 같은 모델 지정은 Claude Code 에서만 쓴다.
- **파일 경로**: `{스킬폴더}` 는 이 SKILL.md 가 있는 폴더다 (Claude Code `~/.claude/skills/research-proposal`, Codex `~/.codex/skills/research-proposal`).

## Instructions

### Phase 0: 요청 파싱 (Interactive)

사용자의 요청에서 필요한 정보를 추출합니다. 누락된 필수 정보가 있으면 AskUserQuestion으로 확인합니다.

```
AskUserQuestion 예시:
질문: "연구 아이디어와 분야에 대해 알려주세요."
옵션:
  - "아이디어와 분야를 함께 입력" (기본)
  - "예시 보여주기"
```

**최소 필요 정보**:
- 연구 아이디어 (무엇을 연구하고 싶은지)
- 연구 분야 (어떤 학술 분야인지)

**선택 정보 기본값**:
- 논문 디렉토리: `output/`
- 출력 경로: `{논문 디렉토리 상위}/research-proposals/`
- 시작일: 현재 날짜

정보가 확보되면, 논문 디렉토리에 관련 파일이 있는지 Glob으로 확인합니다.

#### Pitfall Pre-screening

`references/pitfall-checklist.md`의 Pre-screening 진단표를 사용하여 조기 검증:
1. **범위 체크**: 연구 질문을 한 문장으로 기술할 수 있는가?
2. **문제 정의 체크**: "So what?"에 설득력 있게 답할 수 있는가?
3. **RQ-방법론 정렬 체크**: 각 RQ에 대응하는 실험이 구상되어 있는가?
4. **실현가능성 체크**: 주어진 시간/자원 내에 완료 가능한가?

하나라도 ❌이면 사용자에게 피드백하고 수정 후 진행.

---

### Phase 1 + 2: 선행 연구 조사 & 아이디어 구체화 (병렬)

**background-researcher**와 **idea-concretizer** 에이전트를 **동시에** Agent 도구로 실행합니다.

```
Agent 호출 1 (병렬):
- 역할: "background-researcher"
- prompt: 다음 정보를 전달
  - 연구 아이디어 전체 내용
  - 연구 분야
  - 논문 디렉토리 경로 (있는 경우)
  - 실험 방향 (있는 경우)

Agent 호출 2 (병렬):
- 역할: "idea-concretizer"
- prompt: 다음 정보를 전달
  - 연구 아이디어 전체 내용
  - 연구 분야
  - 실험 방향 (있는 경우)
  - (선행 연구 보고서는 아직 없으므로 없이 실행)
```

두 에이전트의 결과를 스크래치패드에 저장합니다.

**Agent 프롬프트 추가 지시**:
- **background-researcher**: "해당 분야의 landmark 논문 (피인용 수 상위)을 반드시 3편 이상 포함하세요. 연구 갭이 선행 연구로부터 자연스럽게 도출되는지 확인하세요."
- **idea-concretizer**: "scope/feasibility를 사전검증하세요. 연구 질문이 한 문장으로 기술 가능한지, 주어진 자원 내에 완료 가능한지 확인하세요."

---

### 중간 확인: 사용자에게 결과 요약 제시

Phase 1-2 결과를 간략히 요약하여 사용자에게 제시하고 진행 확인:

```
AskUserQuestion:
질문: "선행 연구 조사와 아이디어 구체화가 완료되었습니다. 결과를 확인하고 진행하시겠습니까?"

[결과 요약 표시]:
- 발견된 선행 연구 수
- 식별된 연구 갭
- 구조화된 RQ/가설 목록
- 핵심 가정

옵션:
  - "좋습니다, 학술 비평 진행" (기본)
  - "아이디어를 수정하고 싶습니다" → 수정 사항 반영 후 idea-concretizer 재실행
  - "선행 연구를 더 조사해주세요" → background-researcher 재실행
```

---

### Phase 3: 학술 비평 피드백 루프 (최대 3라운드)

**academic-critic** 에이전트로 비평을 수행합니다. 최대 3라운드까지 피드백 루프가 돌 수 있습니다.

#### 라운드 실행

```
Agent 호출:
- 역할: "academic-critic"
- prompt: 다음 정보를 전달
  - idea-concretizer의 출력 (구체화된 RQ, 가설, 가정, 접근방법)
  - background-researcher의 출력 (선행 연구)
  - 이전 비평 이력 (2라운드 이후)
```

**Critic 프롬프트 추가 지시**:
- "방법론 섹션이 전체 계획서의 30-40% 비중을 차지하는지 확인하세요. 부족하면 구체화를 요구하세요."
- "Reviewer가 물을 가능성이 높은 핵심 질문 3개를 반드시 포함하세요."
- "`references/pitfall-checklist.md`의 Top 10 pitfalls에 해당하는 문제가 있으면 명시적으로 지적하세요."

#### 점수 기반 분기

에이전트로부터 25점 만점의 점수를 받으면:

**Score ≥ 20 (통과)**:
- 비평 보고서 저장
- 다음 Phase로 진행

**Score 15-19 (조건부 통과)**:
```
AskUserQuestion:
질문: "비평 점수 {점수}/25입니다. 주요 피드백: {치명적 약점 요약}. 어떻게 하시겠습니까?"
옵션:
  - "자동 수정 후 재평가" → idea-concretizer에 critic 피드백을 포함하여 재실행 → 재비평
  - "직접 수정할 내용을 입력" → 사용자 입력 + critic 피드백 → idea-concretizer 재실행 → 재비평
  - "현재 상태로 진행" → 경고 추가 후 다음 Phase로 진행
```

**Score < 15 (근본 수정 필요)**:
```
AskUserQuestion:
질문: "비평 점수 {점수}/25로 근본적 문제가 지적되었습니다. {치명적 약점 상세}. 어떻게 하시겠습니까?"
옵션:
  - "문제점을 반영하여 대폭 수정" → 사용자의 수정 방향 입력 → idea-concretizer 재실행 → 재비평
  - "현재 상태로 진행 (경고 포함)" → 경고 추가 후 다음 Phase로 진행
```

**3라운드 후 여전히 20점 미만**:
- 경고 메시지를 추가하고 강제 진행
- 최종 비평 보고서에 "3라운드 후 강제 진행" 표시

#### 피드백 루프 시 idea-concretizer 재실행

```
Agent 호출 (재실행):
- 역할: "idea-concretizer"
- prompt: 다음 정보를 전달
  - 원래 연구 아이디어
  - background-researcher 결과
  - academic-critic의 피드백 보고서 전문
  - 사용자의 수정 사항 (있는 경우)
  - "비평 피드백을 반영하여 구체화를 업데이트하세요"
```

---

### Phase 4 + 5: 기여도 평가 & 실험 설계 (병렬)

비평을 통과한 후, **contribution-assessor**와 **experiment-designer**를 **동시에** 실행합니다.

```
Agent 호출 1 (병렬):
- 역할: "contribution-assessor"
- prompt: 다음 정보를 전달
  - idea-concretizer의 최종 출력
  - background-researcher의 출력
  - academic-critic의 최종 점수표

Agent 호출 2 (병렬):
- 역할: "experiment-designer"
- prompt: 다음 정보를 전달
  - idea-concretizer의 최종 출력
  - background-researcher의 출력
  - academic-critic의 최종 평가
  - 시작일 (사용자 제공 또는 현재 날짜)
```

**Agent 프롬프트 추가 지시**:
- **contribution-assessor**: "Broader Impacts (사회적 영향)과 윤리적 고려사항을 반드시 평가에 포함하세요. target_audience가 NSF/NIH인 경우 특히 강조하세요."
- **experiment-designer**: "예산 정당화 섹션을 포함하세요 (`references/resource-estimation-guide.md` 참조). preliminary_data가 있으면 예비 결과 섹션을 통합하여 실현 가능성 증거로 활용하세요."

---

### Phase 6: 최종 계획서 조합 + 저장

모든 Phase의 결과를 `references/research-proposal-template.md`의 형식에 따라 하나의 계획서로 조합합니다.

#### 템플릿 로딩

`{스킬폴더}/references/research-proposal-template.md`를 읽어 정확한 형식을 따릅니다.

#### 섹션 매핑

| 계획서 섹션 | 소스 |
|-------------|------|
| 0. 초록 (Abstract) | 전체 요약 (최종 단계에서 작성) |
| 1. 연구 개요 | Phase 0 (사용자 입력) + idea-concretizer |
| 2. 연구 배경 | background-researcher |
| 3. 선행 연구 분석 | background-researcher |
| 4. 연구 질문 및 가설 | idea-concretizer (최종) |
| 5. 학술적 기여 | contribution-assessor |
| 6. 실험 설계 | experiment-designer (변수통제표, 파이프라인) |
| 7. 예비 결과 | preliminary_data (있는 경우만 포함) |
| 8. 실험 일정 | experiment-designer (Gantt) |
| 9. 예상 결과 및 분석 | experiment-designer (시나리오) |
| 10. 사회적 영향 및 파급 효과 | contribution-assessor (Broader Impacts) |
| 11. 윤리적 고려사항 | contribution-assessor + idea-concretizer |
| 12. 예산 정당화 | experiment-designer (리소스 추정) |
| 13. 대비 계획 | experiment-designer (위험/Plan B) |
| 14. 비평 및 개선 이력 | academic-critic (모든 라운드) |
| 15. 참고 문헌 | background-researcher + 전체 |

#### YAML Frontmatter

```yaml
---
연구 제목: "{연구 제목}"
연구자: "{사용자명 또는 미지정}"
작성일: "{YYYY-MM-DD}"
연구 분야: "{분야}"
키워드: ["{keyword1}", "{keyword2}", "{keyword3}"]
비평 점수: "{최종 점수}/25"
비평 라운드: {N}
상태: "{통과/조건부 통과/경고 포함 진행}"
target_audience: "{NSF/NIH/General/Thesis}"
preliminary_data: "{경로 또는 N/A}"
broader_impacts: "{포함/해당없음}"
ethical_review: "{필요/해당없음}"
---
```

#### 저장

계획서를 지정된 출력 경로에 저장합니다:
- 디렉토리가 없으면 생성 (Bash `mkdir -p`)
- 파일명: `{연구제목_축약}_research_proposal_{YYYYMMDD}.md`
- 저장 완료 후 경로를 사용자에게 안내

#### Mermaid Validation

계획서 저장 후, Mermaid 다이어그램을 검증합니다:

```
Agent(
  역할="mermaid-validator",
  prompt="Validate and fix all Mermaid diagrams in: {계획서 파일 경로}\n\nExtract all ```mermaid blocks (flowchart, gantt 등), compile-test each with mmdc, and fix any syntax errors. Write corrected diagrams back to the source file.",
  model="haiku"
)
```

실험 파이프라인 flowchart, Gantt 차트 등 계획서 내 모든 Mermaid 블록이 mmdc 컴파일을 통과하는지 확인합니다.

---

## Reference Files

이 스킬은 다음 레퍼런스 파일을 참조합니다:

**직접 포함**:
- `references/research-proposal-template.md` — 최종 계획서 16개 섹션 템플릿 (초록, 예비결과, 사회적영향, 윤리, 예산정당화 포함)
- `references/academic-review-rubric.md` — 학술 비평 5차원 25점 루브릭
- `references/resource-estimation-guide.md` — GPU/시간/비용 추정 가이드
- `references/gantt-schedule-guide.md` — Mermaid Gantt 차트 가이드
- `references/pitfall-checklist.md` — Top 10 제안서 pitfalls 체크리스트

**경로 참조 (research-ideator에서 재사용)**:
- `~/.claude/skills/research-ideator/references/variable-table-guide.md` — 변수 통제표 가이드 (research-ideator 스킬이 없으면 건너뛴다)
- `~/.claude/skills/research-ideator/references/mermaid-experiment-guide.md` — 실험 설계 Mermaid 가이드 (research-ideator 스킬이 없으면 건너뛴다)

## Agents Used

이 스킬은 다음 에이전트들을 순차/병렬로 호출합니다:

| 에이전트 | Phase | 역할 | 병렬 |
|----------|-------|------|------|
| `background-researcher` | 1 | 선행 연구 조사 및 배경 구성 | Phase 2와 병렬 |
| `idea-concretizer` | 2 | 가설/RQ 구조화, 가정 분리 | Phase 1과 병렬 |
| `academic-critic` | 3 | 학술 비평 + 피드백 루프 | 순차 (최대 3라운드) |
| `contribution-assessor` | 4 | 학계 기여도 평가 | Phase 5와 병렬 |
| `experiment-designer` | 5 | 실험 설계 (리소스/Gantt/대비책) | Phase 4와 병렬 |

### 파이프라인 흐름

```
Phase 0: 요청 파싱 (interactive)
    |
    +--- Phase 1: background-researcher ---|  (병렬)
    +--- Phase 2: idea-concretizer --------|
    |
    v
중간 확인: 사용자에게 결과 요약 제시 + 확인
    |
    v
Phase 3: academic-critic 피드백 루프 (최대 3라운드)
    |  Score ≥ 20 → 통과
    |  Score 15-19 → 피드백 + 사용자 선택 → 수정 → 재평가
    |  Score < 15  → 근본 문제 지적 + 사용자 수정 → 재평가
    |  3라운드 후  → 경고 포함 강제 진행
    |
    +--- Phase 4: contribution-assessor ---|  (병렬)
    +--- Phase 5: experiment-designer -----|
    |
    v
Phase 6: 최종 계획서 조합 + 저장
```

## Output Language

- 모든 출력은 **한국어**로 작성
- 영어 기술 용어는 원문 유지 (예: "Chain-of-Thought", "Ablation Study", "Transformer")
- 논문 제목은 원어 유지
- Mermaid 다이어그램 내 한국어 사용 가능

## Error Handling

- **필수 정보 누락**: AskUserQuestion으로 재요청
- **논문 디렉토리 비어있음**: 선행 연구 조사를 웹 검색 중심으로 전환
- **에이전트 실행 실패**: 해당 Phase 1회 재시도, 실패 시 해당 섹션 "수동 작성 필요" 표시
- **비평 루프 3회 초과**: 경고와 함께 강제 진행
- **출력 경로 접근 불가**: 대안 경로 제안

## Example Usage

```
사용자: LLM의 temperature 변화에 따른 introspection 능력 측정 연구 계획서 작성해줘

응답 흐름:
1. Phase 0: 분야 확인 (NLP/AI) → 디렉토리 확인
2. Phase 1+2 (병렬): 선행 연구 조사 + 아이디어 구체화
3. 중간 확인: 결과 요약 → 사용자 확인
4. Phase 3: 학술 비평 → 20/25 통과
5. Phase 4+5 (병렬): 기여도 평가 + 실험 설계
6. Phase 6: 최종 계획서 저장
   → research-proposals/llm_introspection_research_proposal_20260205.md
```

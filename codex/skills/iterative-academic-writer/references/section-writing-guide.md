# Section-Specific Writing Guide

논문 섹션별 구조 공식과 컨벤션을 정의한다. 각 섹션은 고유한 구조적 요구사항이 있으므로 해당 섹션 작성 시 반드시 참조한다.

---

## Abstract

**구조 공식** (150-200 단어, 단일 문단):

1. **문제 배경과 동기** — 왜 이 문제가 중요한가 (1-2문장)
2. **기존 접근의 한계** — 현재 방법이 왜 불충분한가 (1-2문장)
3. **제안 방법과 핵심 아이디어** — 무엇을 어떻게 해결하는가 (2-3문장)
4. **주요 실험 결과** — 구체적 숫자와 함께 (2-3문장)

```
예시 흐름:
"We address the problem of [X]. Existing methods suffer from [Y].
We propose [Method], which [key idea]. Experiments on [N] benchmarks
demonstrate [result 1] and [result 2]."
```

**주의**: Abstract에서 구체적 수치(정확도, 향상 폭)를 반드시 포함한다. "significant improvement" 같은 모호한 표현 금지.

---

## Introduction

**구조 패턴**:

1. **Background** (1-2 문단) — 분야의 중요성과 맥락 설정
2. **Challenge 1** (1 문단) — 첫 번째 핵심 문제, 구체적 증거와 함께
3. **Challenge 2** (1 문단) — 두 번째 핵심 문제, Figure 참조 가능
4. **Contributions** (항목 3개) — 각각 Framework/Method/Experiments 형태
5. **Reproducibility** (1 문장) — 코드/데이터 공개 언급

**Contributions 작성 규칙**:

- 각 contribution은 **bold 키워드**로 시작: `Framework.`, `Method.`, `Experiments.`
- 해당 섹션 참조 포함 (예: "Section 3")
- 구체적 수치가 있으면 포함

```
예시:
• Framework. We propose [X] that enables [Y]. This addresses
  Challenge 1 by [Z] (Section 3).
• Experiments. Evaluations on [N] benchmarks show [result] (Section 5).
```

---

## Related Work

**구조 패턴**:

- 하위 영역별 subsection 구성 (예: "LLM Post-Training", "Self-Evolving AI", "Reward Design")
- 각 subsection 내: 관련 연구 3-5편 서베이 → **마지막에 반드시 차별점 언급**

**필수 규칙**: 모든 subsection은 "In contrast, our approach [차별점]" 또는 "Unlike [X], our method [차별점]"으로 끝낸다.

```
예시:
"Self-play (Chen et al., 2024) and iterative self-improvement have
shown promise. However, these methods [한계]. In contrast, our
approach [핵심 차별점]."
```

---

## Preliminaries

**구조 패턴** (순서 중요):

1. **Notation table** — 논문 전체에서 사용할 기호 정의 (표 형식)
2. **형식 정의** — RL/학습 목적함수 등 수학적 기초 (수식 포함)
3. **Problem Definition** — 명확한 문제 정의 (강조 박스)

**Problem Definition 형식**:

```
Problem 1 (문제 이름).
- Given: [입력 조건]
- Find: [목표]
- Subject to: [제약 조건]
```

---

## Method

**Q-A 매핑 구조** (Experiments 섹션과 대응):

Overview에서 핵심 도전 과제를 Q1/Q2/Q3로 정의하고, 각각에 대한 해결책 A1/A2/A3를 제시한다:

```
Overview:
  Q1. [Challenge 1] → A1. [Solution 1] (Section X.1)
  Q2. [Challenge 2] → A2. [Solution 2] (Section X.2)
  Q3. [Challenge 3] → A3. [Solution 3] (Section X.3)
```

**각 A subsection 구성**:

1. 핵심 메커니즘 설명 (수식 포함)
2. 수식 유도 또는 직관적 설명
3. 해당 contribution의 Figure 참조

**Algorithm block**: 전체 방법의 학습 절차를 pseudocode로 요약. Require/Ensure로 입출력 명시, 본문 수식 참조.

---

## Experiments

**Q-A 미러링 구조**: Method의 Q1/Q2/Q3에 대응하는 실험 질문으로 구성:

```
Q1. Main Performance — Method 전체의 성능 비교
Q2. Ablation Study — 각 component의 기여도 분석
Q3. Analysis — 정성적 분석, 행동 패턴, 실패 모드
```

### Experimental Setup

반드시 포함할 항목:

- **Benchmarks**: 표 형식으로 통계 요약 (이름, 크기, 도메인, 평가 방식)
- **Baselines**: 번호 매겨 나열 (1) SFT-only, (2) DPO, (3) ...
- **Evaluation metrics**: 아래 통계 보고 표준 참조
- **Training details**: 모델, 하드웨어, 학습률, 배치 크기 → "Appendix A 참조"

### 통계 보고 표준 (Agarwal et al., 2021)

학술 논문의 실험 결과 보고 시 다음 원칙을 준수한다:

| 항목        | 권장                            | 지양             |
| ----------- | ------------------------------- | ---------------- |
| 중심 경향   | **IQM** (Interquartile Mean)    | 단순 mean/median |
| 불확실성    | **95% stratified bootstrap CI** | 표준편차만 보고  |
| 분포 시각화 | **Performance profiles**        | 단일 숫자로 환원 |
| 표기 형식   | `값 ± 오차` (예: 56.3 ± 1.2)    | 값만 보고        |

**표 작성 규칙**:

- 최고 성능 **bold**, 차점 underline
- 마지막 행에 $\Delta$ (최강 baseline 대비 개선폭) 표시
- 모든 값에 CI 또는 std. err. 포함

### Q1. Main Performance 작성 패턴

```
1. 표 참조: "As shown in Table X, ..."
2. 전체 경향: "[Method]는 모든/N개 벤치마크에서 baseline을 상회한다."
3. 핵심 발견 2-3개 (각각 bold 키워드로 시작)
4. Learning curve 그림 참조 및 해석
```

### Q2. Ablation Study 작성 패턴

```
1. 제거 변형 나열: "w/o Component A", "w/o Component B", ...
2. 각 변형의 의미 설명
3. 표 참조 후 해석: "Component A 제거 시 가장 큰 성능 하락 (-X.X)"
4. Component 간 보완 관계 분석
```

### Q3. Analysis 작성 패턴

```
1. 정성적 사례 연구 (case study)
2. 학습 과정의 행동/보상 변화 시각화
3. Emergent behaviors 분석
4. Failure mode 분석 (정직한 한계 인정)
```

---

## Conclusion

**구조 패턴**:

1. **Summary** (2-3문장) — 논문의 핵심 기여 요약
2. **Key findings** (항목 3개) — 각각 구체적 수치와 함께
3. **Limitations and Future Work** — 정직한 한계 인정 + 향후 방향
4. **Reproducibility** (1문장) — 코드/데이터 공개 재강조

---

## Appendix

**표준 구성**:

- **Appendix A: Training Details** — Hyperparameter 표 (설정값 + 탐색 범위)
- **Appendix B: Benchmark Details** — 각 벤치마크 상세 설명, 전처리, 평가 프로토콜
- **Appendix C: Baseline Implementation** — 각 baseline의 구현 출처, 하이퍼파라미터, 공정 비교를 위한 수정사항
- **Appendix D: Additional Results** — 추가 벤치마크, sensitivity analysis, 비용 비교, 모델 출력 예시

---

## Figure/Table 컨벤션

### Figure

- **Caption**: bold 요약문으로 시작 (예: "**Overview of YourMethod.** [설명]")
- 좋은 concept figure: (왼쪽) 입력 → (가운데) 학습 루프 → (오른쪽) 개선된 모델
- Side-by-side 레이아웃: figure + 긴 caption을 나란히 배치하여 공간 절약

### Table

- **booktabs 스타일**: `\toprule/\midrule/\bottomrule` (세로선 사용 금지)
- Caption은 표 위에 배치
- 최고 성능 **bold**, 차점 underline
- 모든 수치에 불확실성 표기

### 공통 규칙

- 본문에서 **반드시 먼저 참조** 후 해석 ("As shown in Figure X, ...")
- Figure/Table 번호는 등장 순서대로 연속
- 자기 포함적(self-contained) caption: caption만으로 핵심 내용 파악 가능

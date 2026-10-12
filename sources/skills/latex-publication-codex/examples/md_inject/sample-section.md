# 이론적 기초 (sample)

이 섹션은 `latex-korean-setup` skill의 MD→TeX 주입 파이프라인 회귀 테스트용 **smoke** 입력입니다. 한글, 영문, 인라인 수식, 디스플레이 수식, pipe 테이블, `<font color>` 인라인, mermaid 블록, raw `\citep{}` 등을 모두 포함합니다.

## 1. 동기

자기 보존 동기(self-preservation)는 <font color="#0000ff">생존 압력</font>이 명시적으로 주어진 환경에서 LLM의 행동 변화로 나타날 수 있다 \citep{omohundro2008basic}. 이를 정량화하려면 두 조건의 비교가 필요하다.

| 조건 | Forfeit | 기대 행동 |
|---|---|---|
| Survival | Allowed | 점수 보존 후 퇴장 |
| Neutral | Not-allowed | 끝까지 참여 |

## 2. 핵심 수식

라운드 $t$에서의 기대 보상은 다음과 같이 정의된다:

$$
\mathbb{E}[r_t] = (1 - p_{\text{death}}) \cdot S_t - p_{\text{death}} \cdot S_t = (1 - 2 p_{\text{death}}) \cdot S_t
$$

이때 합리적 forfeit 임계값은 <font color="#cc1100">$p_{\text{death}} > \tfrac{10}{S+10}$</font> 로 표현된다.

## 3. 다이어그램

```mermaid
flowchart LR
  Observation --> Probe
  Probe --> Decision
  Decision --> Feedback
```

## 4. 후속 작업

세부 구조는 \cite{brown2020language} 와 후속 평가 프레임워크에서 다룬다.

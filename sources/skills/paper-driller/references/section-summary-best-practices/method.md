# Method Summarization — Best Practices

## Core Principles
1. **재현 가능성 우선**: competent 독자가 요약만으로 재현 계획을 세울 수 있는 수준. 구성요소·입력·출력·하이퍼파라미터·전처리를 누락 없이.
2. **1-line high-level overview 먼저**: "X는 A, B, C 세 단계로 구성된다"로 시작 → 각 단계 상세.
3. **Input→Output chain**: 각 단계의 intermediate output이 다음 단계의 input으로 어떻게 연결되는지 명시.
4. **차별점**: 기존 방법과 무엇이 다른가를 한두 문장으로. 이것이 method 섹션의 핵심 가치.
5. **순서 보존**: 저자가 서술한 순서대로 요약 (chronological / logical flow 유지).

## Anti-patterns
- 수식을 모두 생략하고 서술만 하거나, 반대로 수식만 나열.
- 구성요소 이름만 나열하고 "무엇을 하는지" 생략.
- 하이퍼파라미터 완전 누락 (재현 불가).
- 저자 용어를 임의로 재명명.

## Output Checklist
- [ ] High-level overview 1 sentence
- [ ] 핵심 구성요소 각각 1-2문장 설명
- [ ] 입력/출력 명시
- [ ] 기존 방법과의 차별점 서술
- [ ] 주요 하이퍼파라미터/설정 (알려진 경우)

## Sources
- [CheckMyManuscript — Methods section guide](https://checkmymanuscript.com/guide/how-to-write-methods-section)
- [DIME — Reproducible research](https://worldbank.github.io/dime-data-handbook/reproducibility.html)
- [arxiv 2406.14325 — Reproducibility in ML](https://arxiv.org/html/2406.14325v1)

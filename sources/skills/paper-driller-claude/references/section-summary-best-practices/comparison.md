# Comparison Matrix — Best Practices

## 비교 대상 선정 (3-5편)
1. **직접 비교** (동일 문제, 다른 방법) — 1-2편
2. **기반 연구** (본 논문이 확장/개선) — 1편
3. **최신 SOTA** — 1편
4. **대안 패러다임** — 0-1편

## 비교 축 (행 고정)
`핵심 접근 | 문제 정의 | 데이터 | 핵심 메트릭 | 확장성 | 한계 | 코드 공개`

## 작성 원칙
1. **공통 차원 필수**: 모든 셀이 같은 축으로 비교 가능해야 함 (RQ가 다르면 축을 맞출 수 없음 → 선정 단계에서 걸러냄).
2. **축 중 답이 동일한 것은 제외**: 모든 논문이 "코드 공개=✅"면 컬럼 의미 없음 → 다른 축으로 교체.
3. **숫자 있는 곳은 숫자로**: 정성 평가("좋다")보다 정량("72.1 F1").
4. **한계는 저자 인정 + 독자 식별 구분**.
5. **본 논문을 첫 컬럼**에 고정, 비교 대상을 옆 컬럼으로.

## Anti-patterns
- 주관적 평가어만 사용 ("우수하다", "혁신적").
- 본 논문에 불리한 축 누락 (cherry-picking).
- 선정 근거 미기재.

## Output Checklist
- [ ] 3편+ 비교 대상
- [ ] 축 7개 전부 채움
- [ ] 코드 공개 여부 명시
- [ ] 선정 근거 1-2문장 전문

## Sources
- [Duquesne — Review matrix](https://guides.library.duq.edu/matrix)
- [Otio — Literature review matrix](https://otio.ai/blog/literature-review-matrix)
- [Brandeis — Matrix method](https://www.brandeis.edu/writing-program/resources/faculty/handouts/matrix-method-literature-reviews.html)

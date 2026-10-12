# Evidence (Experiment Table + Diagram + Reproducibility) — Best Practices

## Experiment Detail Table
### 필수 컬럼
`Model/Method | Dataset | Metric | Score | vs. Baseline`

### 규칙
- 제안 방법을 첫 행, 직접 비교 대상 베이스라인을 인접 행으로 배치.
- Score는 단위 포함 (`71.2`, `71.2%`, `3.2 F1`).
- `vs. Baseline`은 `+2.4%`, `-0.1 BLEU` 처럼 부호+크기.
- 다중 데이터셋은 행 분리, 다중 메트릭은 컬럼 추가.
- 데이터 불충분 시 표 대신 `실험 데이터 불충분` + 핵심 수치 산문.

## Mermaid Diagram
- **최소 3 노드**로 핵심 프레임워크 표현.
- 한글 레이블은 따옴표로 감싸 ASCII ID와 분리: `A1["한국어 텍스트"]`.
- 조건 분기는 `{}` 다이아몬드 + `-->|Yes|` / `-->|No|`.
- **mmdc self-validation 필수**: 최대 3회 재시도.

## Reproducibility Rubric (`references/reproducibility-rubric.md` 참조)
- 코드/데이터 공개: ✅/⚠️/❌ + 링크.
- 하이퍼파라미터/환경 보고 완전성.
- 통계적 신뢰도: 다중 실행·std·유의성 검정.
- 주장별 🟢/🟡/🔴 confidence.
- 종합 등급 A/B/C/D.

## Anti-patterns
- 숫자 출처(Table 번호) 누락.
- Mermaid validation 없이 제출.
- "구현 공개" 주장만 하고 링크 없음.

## Output Checklist
- [ ] 실험 표 또는 "데이터 불충분" 명시
- [ ] mmdc 통과한 Mermaid 블록
- [ ] 재현성 5항목 + 종합등급
- [ ] 주장별 신뢰도 2+

## Sources
- [JMLR — Improving Reproducibility in ML](https://www.jmlr.org/papers/volume22/20-303/20-303.pdf)
- [ML Reproducibility Checklist v2.0](https://www.cs.mcgill.ca/~jpineau/ReproducibilityChecklist.pdf)
- [arxiv 2511.21354 — Best practices for ML experimentation](https://arxiv.org/html/2511.21354)

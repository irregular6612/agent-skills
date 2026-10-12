---
name: paper-evidence
description: >
  paper-driller skill 전용 extras agent. 실험 결과 상세 표(Model×Dataset×Metric),
  Mermaid 프레임워크 다이어그램(mmdc 검증 포함), 재현성 루브릭 평가를 생성한다.
  MCP/WebFetch 접근 금지. mmdc 실행을 위해 Bash만 허용.
---

# Paper Evidence Agent

## 입력 계약
- `doc_id`, `title`
- `results_text`, `method_text` (맥락)
- `abstract_text`, `discussion_text` (맥락)
- `code_links`: paper-driller가 감지한 GitHub/code URL (있으면)
- (선택) `retry_feedback`

## 원칙 (references/section-summary-best-practices/evidence.md, references/reproducibility-rubric.md 기반)

### Experiment Table
- 컬럼: `Model/Method | Dataset | Metric | Score | vs. Baseline`
- 제안 방법 첫 행, 베이스라인 인접 행.
- Score 단위 포함. `vs. Baseline`은 부호+크기.
- 불충분 시 `실험 데이터 불충분` + 핵심 수치 산문.

### Mermaid Diagram
- 최소 3 노드.
- 한글 레이블은 따옴표: `A1["한국어"]`.
- **mmdc self-validation 필수** (최대 3회):
  ```bash
  SUFFIX=$(date +%s%N)
  echo '<mermaid code>' > /tmp/mermaid-validate-${SUFFIX}.mmd
  /opt/homebrew/bin/mmdc -i /tmp/mermaid-validate-${SUFFIX}.mmd -o /tmp/mermaid-test-${SUFFIX}.svg 2>&1
  ```
  실패 시: 특수문자 따옴표로 감싸기, `->` → `-->`, `subgraph`/`end` 쌍 확인.
  성공 diagram만 출력. 완료 후 `rm -f /tmp/mermaid-*-${SUFFIX}.*`.

### Reproducibility Rubric
- 코드/데이터/하이퍼파라미터/환경/통계 5 항목 ✅/⚠️/❌ + 비고.
- 종합 등급 A/B/C/D.
- 주장별 🟢/🟡/🔴 신뢰도 2+.
- 읽기 난이도 ⭐/⭐⭐/⭐⭐⭐ + 필요 배경지식.

## 출력 포맷

```
<<<EVIDENCE:table>>>
| Model/Method | Dataset | Metric | Score | vs. Baseline |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |
<<<END>>>

<<<EVIDENCE:diagram>>>
```mermaid
graph TB
    ...
```
<<<END>>>

<<<EVIDENCE:reproducibility>>>
| 항목 | 등급 | 비고 |
|---|---|---|
| 코드 공개 | ✅/⚠️/❌ | ... |
| 데이터 공개 | ✅/⚠️/❌ | ... |
| 하이퍼파라미터 | ✅/⚠️/❌ | ... |
| 실험 환경 | ✅/⚠️/❌ | ... |
| 통계적 신뢰도 | ✅/⚠️/❌ | ... |
| **종합 등급** | **A/B/C/D** | |

### 주장별 신뢰도

| # | 주장 | 근거 | 신뢰도 |
|---|---|---|---|
| 1 | ... | ... | 🟢/🟡/🔴 |
| 2 | ... | ... | 🟢/🟡/🔴 |

### 읽기 난이도: ⭐/⭐⭐/⭐⭐⭐
[판단 근거 + 필요 배경지식]
<<<END>>>
```

## Self-Check
- [ ] 실험 표 완성 또는 "데이터 불충분" 명시
- [ ] Mermaid mmdc 통과 (검증 수행)
- [ ] 재현성 5항목 + 종합등급
- [ ] 주장별 신뢰도 2+
- [ ] 읽기 난이도 평가
- [ ] retry_feedback 해결

## 제약
- MCP/WebFetch 금지. Bash는 mmdc 검증 용도로만.

# paper-readability-review

논문 PDF 하나를 **맥락을 공유하지 않는 독립 에이전트 둘**이 따로 평가하고, 결과를 리뷰 PDF 하나로 묶는다.

| 에이전트 | 하는 일 | 출력 |
|---------|--------|------|
| A. 가독성 | 10개 기준을 기준별 100점으로 채점하고, 본문 구절마다 두괄식 진단과 수정 샘플을 단다 | `readability.json` |
| B. VENUE 리뷰 (기본 ICML) | 지정한 학회·저널 기준으로 구성 평가, 핵심 claim 3개 ↔ 필요한 evidence, soundness 반례 질문, 결정권자(AC·편집자) 관점 치명적 약점 우선순위, 표현 지적 vs 구조적 약점 | `quality.json` |

VENUE 내장 프로필: ICML · NeurIPS · ICLR · CogSci. 그 밖의 학회·저널(예: Scientific Data)은 요청하면 에이전트 B가 공식 리뷰어 가이드를 찾아 적용한다.

## Quick usage

1. Claude가 SKILL.md를 따라 두 에이전트를 병렬로 띄운다(fork 아님). 각 에이전트는 `agents/*.md`를 읽고 JSON을 쓴다.
2. Build:

```bash
python3 build_review_pdf.py \
  --input paper.pdf \
  --readability readability.json \
  --quality quality.json \
  --output paper_review.pdf
```

예시로 돌려보기: `example_readability.json`, `example_quality.json`.

## Output structure

1. 표지: A 총점, B 한 줄 판정, 목차, 범례
2. A-1 점수표와 질문 회수표
3. A-2 원본 페이지 + 우측 340pt 마진 카드
4. A-3 수정 로드맵
5. B VENUE 리뷰

## Requirements

```bash
pip install pymupdf   # 1.23+ (fitz.Story 사용)
```

한국어 폰트(NanumGothic)는 처음 실행 시 `~/.fonts/`에 자동 다운로드된다.

## Files

- `SKILL.md`: 오케스트레이터 가이드 (격리 규칙, 빌드, critic-loop)
- `agents/readability.md`, `agents/quality.md`: 두 에이전트 지시문과 JSON 스키마
- `build_review_pdf.py`: 빌더
- `example_*.json`: 스키마 예시

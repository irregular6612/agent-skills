---
name: paper-readability-review
description: 논문 PDF를 맥락을 공유하지 않는 독립 에이전트 둘이 따로 평가하고, 결과를 리뷰 PDF 하나로 묶는다. (A) 가독성 에이전트는 10개 기준(논리·두괄식·비전문가 접근성·단어 선택·AI 문체·압축도·연결성·절 내부 흐름·질문 회수·기여–결과 대응)을 기준별 100점으로 채점하고, 본문 위에 하이라이트 + 수정 샘플 카드를 붙인다. (B) 품질 에이전트는 지정한 학회·저널(기본 ICML; 내장 ICML·NeurIPS·ICLR·CogSci, 그 밖의 학회·저널도 요청 시 그 심사 기준을 찾아 적용) 리뷰어 입장에서 핵심 약점 기준 구성 평가·핵심 claim 3개와 필요한 evidence·soundness 반례 질문·결정권자(AC·편집자) 관점 치명적 약점 우선순위·표현 지적 vs 구조적 약점을 낸다. 사용자가 자기 논문이나 학생·동료 원고를 첨부하고 "가독성 봐줘", "리뷰 PDF 만들어줘", "피드백 달아줘", "ICML 리뷰어처럼 봐줘", "NeurIPS 기준으로 봐줘", "Scientific Data 리뷰어처럼", "점수 매겨줘" 같은 요청을 할 때 사용한다. MANDATORY TRIGGERS - 가독성 리뷰, 논문 피드백, readability review, 박스 코멘트, 마진 코멘트, annotated review, paper feedback, 리뷰 PDF, 원고 점검, 논문 점수, ICML 리뷰, NeurIPS 리뷰, ICLR 리뷰, CogSci 리뷰, 저널 리뷰, 리뷰어 관점, reject 근거, soundness 점검, claim-evidence
---

# Paper Review: 가독성 + 학회·저널 품질 리뷰

원고 PDF 하나를 **서로 맥락을 공유하지 않는 두 에이전트**가 따로 평가한다. 원고가 `.docx`면 먼저 PDF로 바꾼다(LibreOffice: `soffice --headless --convert-to pdf`). 오케스트레이터(너)는 평가하지 않는다. 두 에이전트를 띄우고, 결과 JSON을 검증하고, PDF로 묶는 일만 한다.

```
[원고 PDF]
    ├─▶ 에이전트 A: 가독성   (agents/readability.md) ─▶ readability.json
    └─▶ 에이전트 B: VENUE 리뷰 (agents/quality.md)    ─▶ quality.json
                                  ↓ (두 JSON은 빌드 스크립트에서만 만난다)
              build_review_pdf.py ─▶ PAPER_review.pdf
```

## 결과 PDF 구성

1. **표지**: A 총점과 한 줄 진단, B 한 줄 판정과 결정권자 우선순위 상위 3, 목차, 카드 범례
2. **A-1 점수표**: 10개 기준 점수(각 100점)와 핵심 한 줄, 기준별 근거와 가장 효과 큰 수정, 질문 회수표
3. **A-2 원문 + 마진 카드**: 하이라이트된 구절마다 [두괄식 진단 + 그대로 붙여 넣을 수정 샘플]
4. **A-3 수정 로드맵**: 카드를 우선순위순으로 정렬
5. **B VENUE 리뷰**: 적용한 심사 기준 · 구성 평가 · claim 3개 ↔ evidence · 반례 질문 · 결정권자 우선순위 · 구조적 약점 vs 표현 지적

## Workflow

### 0. VENUE 정하기

사용자 요청에서 투고처를 읽는다.

- 이름을 말했으면 그대로 쓴다. 예: "NeurIPS 기준으로", "Scientific Data에 낼 원고"
- 원고나 파일 경로에 투고처가 드러나 있어도(예: `25-ScientificData/`) **사용자가 말하지 않았으면 추측하지 않는다.** 기본값 `ICML`로 돌리고, 보고할 때 "경로상 X 투고로 보이는데, X 기준으로 다시 돌릴까요?"라고 한 줄 묻는다.
- 내장 프로필: ICML · NeurIPS · ICLR · CogSci. 그 밖의 학회·저널은 에이전트 B가 공식 리뷰어 가이드를 찾아 기준을 세운다(`agents/quality.md` 0절).

### 1. 작업 폴더 준비

원고 옆이나 scratchpad에 작업 폴더를 만든다. 이후 경로는 모두 절대경로로 쓴다.

```
WORK/
  readability.json   ← 에이전트 A가 씀
  quality.json       ← 에이전트 B가 씀
  PAPER_review.pdf   ← 빌드 결과
```

### 2. 두 에이전트를 동시에 띄운다 (격리 규칙)

**한 메시지에서 Agent 도구를 두 번** 호출해 병렬로 띄운다. 둘 다 `subagent_type: "general-purpose"`이다. **fork를 쓰지 않는다.** fork는 오케스트레이터의 맥락을 물려받아 격리가 깨진다.

프롬프트에는 아래 세 줄만 넣는다. 오케스트레이터가 논문에서 받은 인상, 사용자와 나눈 대화, 다른 에이전트의 존재는 넣지 않는다.

```
<SKILL_DIR>/agents/readability.md 를 읽고 그 지시를 그대로 따르라.
PAPER=<원고 PDF 절대경로>
OUT=<WORK>/readability.json
```

```
<SKILL_DIR>/agents/quality.md 를 읽고 그 지시를 그대로 따르라.
PAPER=<원고 PDF 절대경로>
OUT=<WORK>/quality.json
VENUE=<0단계에서 정한 학회·저널>
```

VENUE는 에이전트 B에만 준다. 가독성 평가는 투고처와 무관하다.

`<SKILL_DIR>`은 이 SKILL.md가 있는 폴더다. 사용자가 특정 독자층·분야를 지정했으면 해당 에이전트 프롬프트에 한 줄만 덧붙인다. 예: "독자: 인지과학 전공 비ML 연구자".

### 3. 빌드

두 에이전트가 모두 끝나면 빌드한다.

```bash
python3 <SKILL_DIR>/build_review_pdf.py \
  --input PAPER.pdf \
  --readability WORK/readability.json \
  --quality WORK/quality.json \
  --output WORK/PAPER_review.pdf
```

여러 학회·저널 기준으로 보고 싶다면(예: ICML로 돌린 뒤 Scientific Data로 한 번 더), VENUE마다 에이전트 B를 따로 띄워 `quality_<venue>.json`을 만든다. 기존 JSON은 지우지 않는다. 그다음 `--quality`에 JSON을 모두 넘기면 한 PDF 안에 B-1, B-2, …로 들어간다. 가독성 결과는 다시 만들지 않는다.

**집중 분석 (선택, C절):** 사용자가 특정 분석 하나를 깊이 봐 달라고 하면 그 주제만 보는 에이전트를 따로 띄운다(예: "identity consistency 계산에 문제 없는지"). 이 에이전트도 fresh agent이고, 앞선 리뷰의 결론을 프롬프트에 넣지 않는다. 대신 원고, 관련 코드·결과 폴더 경로, 아래 스키마를 준다. 결과는 `--extra extra_<topic>.json ...`으로 넘기고, PDF 끝에 C(여러 개면 C-1, C-2, …)로 들어간다.

```json
{"schema": "paper-review-extra-v1", "title": "...", "scope": "본 범위·파일", "summary": "두괄식 결론",
 "findings": [{"rank": 1, "severity": "fatal|major|minor", "issue": "...", "where": "...",
               "detail": "...", "check": "확인 방법", "fix": "처방"}]}
```

스크립트는 다음을 검증한다: 점수 id 1–10이 모두 있는지, 점수가 0–100인지, 카드의 `criterion`이 유효한지, claim이 3개인지. 총점(10개 기준 평균)은 스크립트가 계산한다.

### 4. phrase 불일치 처리

`[WARN] phrase not found`가 나오면 해당 카드는 PDF에 빠진다. 경고 목록을 **에이전트 A에게만** SendMessage로 돌려보내 그 카드의 `phrase`만 고치게 한다. 오케스트레이터가 직접 phrase를 고치지 않는다. 수정 후 다시 빌드한다. 경고가 3건 이하이고 두 번 돌려도 남으면 그대로 두고 사용자에게 보고한다.

### 5. critic-loop (레이아웃 점검)

```bash
python3 -c "
import fitz, os, sys
os.makedirs(sys.argv[2], exist_ok=True)
for i, p in enumerate(fitz.open(sys.argv[1])):
    p.get_pixmap(dpi=110).save(f'{sys.argv[2]}/p{i:02d}.png')
" WORK/PAPER_review.pdf WORK/critic
```

PNG를 보며 확인한다.

- [ ] 카드가 잘리지 않고 8pt 근처 크기로 읽히는가
- [ ] 하이라이트가 정확한 구절 위에 있는가
- [ ] 페이지당 카드 5개 이하인가. 넘으면 에이전트 A에게 normal 카드를 줄이게 한다
- [ ] 표지·점수표·VENUE 리뷰 페이지에 겹침이나 빈 칸이 없는가

**내용은 고치지 않는다.** critic-loop은 레이아웃만 본다. 점수나 판정이 이상해 보여도 오케스트레이터가 바꾸지 않는다. 두 평가의 독립성이 이 스킬의 핵심이다.

### 6. 보고

사용자에게 다음을 짧게 알린다.

- PDF 절대경로
- A 총점과 가장 낮은 기준 2개
- B의 VENUE, 한 줄 판정, fatal 개수
- 남은 경고가 있으면 그 내용

## 카드 색 (빌드 스크립트가 자동 적용)

| 색 | 그룹 | 기준 |
|----|------|------|
| 파랑 | 논리·구조 | C1 논리성, C2 두괄식, C8 절 내부 흐름 |
| 빨강 | 질문 회수 | C9 질문 회수, C10 기여–결과 대응 |
| 노랑 | 읽힘 | C3 비전문가 접근성, C4 단어 선택, C6 압축도, C7 연결성 |
| 보라 | AI 문체 | C5 AI 문체 |

우선순위 뱃지: ★ 최우선(글 전체 이해를 막음) · ▲ 중요(해당 절 이해를 막음) · 없음(다듬으면 좋음)

## 트러블슈팅

| 증상 | 해결 |
|------|------|
| `phrase not found` | Workflow 4단계 |
| `scores must cover ids 1-10` | 에이전트 A에게 빠진 기준을 채우게 한다 |
| 카드 잘림 | 페이지당 카드 수를 줄이거나 rewrite를 150자 이내로 줄이게 한다 |
| 한글 깨짐 | `--fontfile`로 CJK TTF 지정 (기본 `~/.fonts/NanumGothic.ttf`, 없으면 자동 다운로드) |
| HTML 페이지에 색 블록이 번짐 | CSS에 `background-color`를 넣지 말 것 (fitz.Story가 모든 페이지에 다시 칠함) |

## 파일

- `agents/readability.md`: 에이전트 A 지시문 (10개 기준, 점수 구간, 카드 규칙, JSON 스키마)
- `agents/quality.md`: 에이전트 B 지시문 (VENUE 프로필, 리뷰 5개 항목, JSON 스키마)
- `build_review_pdf.py`: 두 JSON + 원고 → 리뷰 PDF
- `example_readability.json`, `example_quality.json`: 스키마 예시

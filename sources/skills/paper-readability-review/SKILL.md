---
name: paper-readability-review
description: 논문 PDF에 가독성·근거 피드백을 내용·구조·문장·근거 네 층위로 진단해, 본문 위에 색상 하이라이트 + 마진 카드(진단 + 대안 방향) + 우선순위 로드맵이 있는 리뷰 PDF를 생성한다. critic-loop으로 자체 점검·반복 개선한다. 사용자가 자기 논문이나 학생/동료의 원고를 첨부하고 "가독성 봐줘", "리뷰 PDF 만들어줘", "피드백 달아줘", "박스 코멘트로 정리해줘", "구조 점검해줘", "문장 다듬을 곳 짚어줘" 같은 요청을 할 때 사용한다. MANDATORY TRIGGERS - 가독성 리뷰, 논문 피드백, readability review, 박스 코멘트, 마진 코멘트, annotated review, paper feedback, 진단 PDF, 코멘트 PDF, paper critique, 원고 점검, 글 다듬기, 구조·문장·내용 피드백, 주장-근거 점검, 과장 표현 점검
---

# Paper Readability Review

논문 PDF를 읽고 **내용 / 구조 / 문장 / 근거** 네 층위로 진단해, 본문 위에 색상 하이라이트와 마진 카드를 붙인 리뷰 PDF를 만든다. 카드는 각각 [진단] + [→ 대안 방향]으로 구성되고, 마지막 페이지에는 우선순위 순서로 정리된 수정 로드맵이 붙는다.

## Workflow

```
[입력: 원고 PDF]
      ↓
[1] 논문 전체 읽기 (모든 섹션, 부록 포함)
      ↓
[2] 4 층위 진단 (각 항목별로 본문에서 정확한 phrase 추출)
    - 내용 (content):  통찰·기여·stake 누락
    - 구조 (structure): 순서·배치 — architecture-first, 갑툭튀, 분산
    - 문장 (sentence):  verbosity·문체 — 수식 침투, 삽입구, 수동태
    - 근거 (rigor):     주장이 근거를 넘어섬 — 과장, 인과 비약, 누수, 불확실성 누락
      ↓
[3] 우선순위 부여 (★ 최우선 / ▲ 중요 / 일반)
      ↓
[4] annotations.json 작성 후 build_review_pdf.py 실행
      ↓
[5] critic-loop: 페이지를 PNG으로 렌더링 → 자체 검토 → 재생성
```

## Phase 1: 논문 읽기

PDF 텍스트를 모두 추출해 섹션 구조를 파악한다. Read 도구로 PDF를 직접 읽거나, 보조 스크립트로 텍스트 추출:

```bash
python3 -c "
import pypdf
r = pypdf.PdfReader('PAPER.pdf')
for i, p in enumerate(r.pages):
    print(f'--- Page {i+1} ---')
    print(p.extract_text())
" > paper_text.txt
```

**섹션별 완전 커버리지**: Abstract부터 부록까지 모든 섹션을 빠짐없이 읽는다. 마진 카드는 본문에서 구절 위치를 정확히 찾아야 하기 때문에 어느 섹션 어느 단락인지 추적이 필수다.

## Phase 2: 4 층위 진단

### 내용 (content) — 무엇이 substantively 빠졌는가

대표 패턴:
- **통찰(insight) 누락**: 결과·방법은 있지만 "남들이 놓친 것"이 명시되지 않음
- **기여(contribution) 추상화**: "측정 가능하다", "재현 가능하다" 류 학계 표현만, 구체적 후속 활용이 없음
- **Stake 부재**: 문제의 손실/위협이 명시되지 않아 독자가 "그래서 어떡하라고?"
- **다리(bridge) 약함**: 기존 한계 나열 → 본 연구 점프, 대응 매핑 없음
- **결과의 함의 closure 부재**: 결과 직후 "이게 무슨 뜻인지" 한 줄이 없음
- **숫자 중복**: 표에 있는 수치를 본문이 그대로 복사

### 구조 (structure) — 순서·배치 문제

대표 패턴:
- **Architecture-first**: '직교 구조', '두 층' 같은 결과 형식부터 던지고 동기는 사후
- **갑툭튀(out of nowhere)**: 모티베이션이 두 섹션 뒤에 있는 디자인 결정
- **분산(scattering)**: 같은 도구의 명명·역할·공식이 여러 섹션에 쪼개짐
- **반복(redundant definition)**: 같은 정의가 Abstract / §1 / §3에 세 번 등장
- **순서 역전**: 핵심 통찰이 본문 중반에 묻혀 있음
- **챕터 경계 어색**: 본질상 같은 설계 결정인데 §4, §5로 분리

### 문장 (sentence) — verbosity·문체

대표 패턴:
- **수식·기호의 산문 침투**: 변수가 한 문단에 6개 이상 박혀 호흡 끊김
- **삽입구(em-dash) 남용**: 한 문장에 부연 두 개 이상
- **수동태**: "측정된다, 귀속된다, 확인된다" 행위자 흐려짐
- **명사화**: 동사 없이 명사구만 쌓이는 문장
- **삼중 병렬**: 트라이콜론이 한 문단에 두 번 이상
- **가정문 도입**: 첫 문장이 "If ..." 로 시작해 stake 약화
- **약어 폭발**: 한 페이지에 12개 이상 약어 등장

### 근거 (rigor) — 주장이 근거를 넘어서는가

다른 세 층위와 똑같이 **문장 단위**로 카드를 단다. phrase는 근거를 넘어선 *주장이 적힌 그 문장*에서 뽑는다. 내용 층위가 "빠진 통찰"을 짚는다면, 근거 층위는 "적힌 주장이 본문 근거보다 크다"를 짚는다.

대표 패턴:
- **과장·일반화**: "consistently", "significantly", "state-of-the-art", "generalizes" — 실험 범위(데이터셋·모델·seed 수)가 그만큼을 받치지 못함
- **인과 비약**: 상관·probing·attribution 결과를 "X가 Y를 일으킨다", "모델이 Y를 이해한다"로 서술
- **불확실성 누락**: 단일 run 수치, seed·분산·신뢰구간 없는 비교, 표준편차 범위 안의 차이를 "향상"으로 서술
- **"차이 없음"의 오독**: 유의하지 않은 결과를 "효과 없음"·"동등"으로 서술
- **누수(leakage) 의심**: train/tuning/test 분리, 전처리 시점, test set으로 한 hyperparameter 선택이 불분명
- **비교 공정성**: baseline의 튜닝 예산·버전·compute가 제안 방법과 다르거나 명시 없음
- **사후(post hoc) 분석 미표기**: 결과를 본 뒤 고른 subset·metric·layer를 사전 설계처럼 서술
- **재현 정보 누락**: 핵심 결과에 필요한 하이퍼파라미터·seed·코드/데이터 가용성이 본문·부록 어디에도 없음
- **새로움 주장 과대**: "최초로", "기존 연구는 모두" — 인용된 선행연구 범위보다 넓음
- **섹션 간 수치 불일치**: 같은 수치가 Abstract·본문·표에서 다름

근거 카드 작성 규칙:
- **[진단]**에 근거 위치를 함께 적는다: "표 2는 단일 seed 결과인데…", "§4.2 기준 데이터셋 2개뿐인데…". 본문에서 근거를 찾지 못하면 "본문·부록에서 찾지 못함"이라고 쓴다. 근거 위치나 수치를 지어내지 않는다.
- **[→ 대안]**은 가장 작은 처방부터 낸다: 표현 좁히기 → 불확실성·조건 명시 → 탐색적(exploratory) 분석이라고 표기 → 이미 있는 분석 추가 보고 → (꼭 필요할 때만) 새 실험. 핵심 주장을 받치는 데 꼭 필요하지 않은 새 실험은 요구하지 않는다.
- 판정하지 않는다: "이 연구는 틀렸다", "reject감" 대신 무엇이 어디서 어긋나는지만 적는다.

> 근거 층위의 체크 항목은 K-Dense `peer-review` 스킬(MIT)의 claim–evidence alignment, effect estimates, multiplicity, prediction/ML, reproducibility 항목을 ML 논문용으로 줄여 옮겼다. 기밀 원고를 공식 리뷰어로 심사할 때는 `peer-review`를 쓴다.

## Phase 3: 우선순위

| 우선순위 | 기준 |
|---------|------|
| **★ 최우선 (highest)** | 글의 *핵심 통찰* 자체와 직결. 한 자리만 고쳐도 가독성이 한 단계 위로 |
| **▲ 중요 (high)** | 문제 인과 사슬의 핵심 노드. 함께 고쳐야 효과 |
| (일반 normal) | 다듬으면 좋음 정도 |

★ 최우선은 보통 1-3건이면 충분. 너무 많으면 우선순위가 희석된다.

## Phase 4: annotations.json 작성

JSON 스키마:

```json
{
  "schema": "paper-readability-review-v1",
  "title": "Optional title for cover",
  "subtitle": "Optional subtitle",
  "one_line_diagnosis": "Optional one-line diagnosis for cover box",
  "fontfile": "Optional path to CJK TTF (default: ~/.fonts/NanumGothic.ttf)",
  "annotations": [
    {
      "page": 1,
      "phrase": "정확히 PDF에서 매칭되는 본문 구절",
      "category": "content | structure | sentence | rigor",
      "priority": "highest | high | normal",
      "diagnosis": "1-3문장 진단",
      "alt": "1-2문장 대안 방향"
    }
  ]
}
```

**중요 — phrase 매칭 규칙**:
- PDF의 줄바꿈 때문에 phrase가 끊길 수 있다. 짧고 유일한 phrase로 (보통 30-60자)
- 인라인 수식 뒤에는 PyMuPDF가 매칭 못 할 수 있다 — 수식 직전 또는 직후의 텍스트를 골라라
- 같은 phrase가 여러 번 나오면 첫 번째 매칭이 사용된다

빌드:

```bash
python3 build_review_pdf.py \
  --input PAPER.pdf \
  --annotations annotations.json \
  --output PAPER_review.pdf
```

## Phase 5: critic-loop

PDF 생성 후 *반드시* 자체 점검:

```bash
python3 -c "
import fitz, os
os.makedirs('critic', exist_ok=True)
doc = fitz.open('PAPER_review.pdf')
for i in range(len(doc)):
    doc[i].get_pixmap(dpi=140).save(f'critic/p{i:02d}.png')
"
```

생성된 PNG를 페이지별로 확인하며 체크리스트:

- [ ] 모든 카드가 페이지 안에 들어가고 잘리지 않는가?
- [ ] 카드 텍스트가 작아도 읽히는가? (폰트 8.0pt 이상 권장)
- [ ] 본문 highlight가 정확한 구절 위에 있는가?
- [ ] 핵심 통찰(★ 최우선)이 prominent하게 보이는가?
- [ ] 카테고리 분포가 균형있는가?
- [ ] 페이지당 카드 5개 이하인가?
- [ ] 우선순위 로드맵 페이지에 ★ 최우선이 맨 위에 있는가?

문제 발견 시 annotations.json 수정 후 build 재실행. 보통 2-3회 루프면 안정된다.

## 색상·우선순위 시스템 (build script가 자동 적용)

| 카테고리 | 본문 highlight | 카드 라벨 |
|---------|---------------|-----------|
| content   | 빨강 | 내용 |
| structure | 파랑 | 구조 |
| sentence  | 노랑 | 문장 |
| rigor     | 초록 | 근거 |

| 우선순위 | 뱃지 |
|---------|------|
| highest | 빨강 ★ 최우선 |
| high    | 주황 ▲ 중요 |
| normal  | (뱃지 없음) |

## 페이지 레이아웃 (자동)

- 원본 페이지 우측에 340pt 마진 추가 (612 → 952pt)
- 각 페이지의 카드는 TOP=56, BOTTOM=770 사이를 카드 수로 균등 분할
- 슬롯에 안 맞으면 폰트 자동 축소 (8.0 → 7.5 → 7.0 → 6.5pt)
- 본문 highlight ↔ 카드 사이를 가는 회색 선으로 연결
- 표지 페이지 (앞) + 우선순위 로드맵 (뒤) 자동 추가

## 한국어 폰트

기본값은 `~/.fonts/NanumGothic.ttf`. 없으면 build script가 자동 다운로드한다.

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `[WARN] 'X' not found` | phrase가 PDF 텍스트와 정확히 매칭 안 됨 | phrase를 더 짧게, 수식 직전/직후로 |
| 카드 잘림 (overflow) | 카드 수 또는 텍스트 너무 김 | 카드 수 5개 이하, 진단/대안 각 100자 이내 권장 |
| 한글 깨짐 (??? 표시) | 폰트 파일 미존재 | NanumGothic 자동 다운로드 또는 fontfile 지정 |
| 우선순위 로드맵에 일부만 표시 | 카드가 많아 한 페이지 초과 | build script가 자동으로 페이지 추가 |

## 영감의 한 줄

> "글의 가독성 문제는 보통 한 군데에서 흘러나온다. 모든 설계 결정의 출발점인 한 문장이 본문에 또렷이 적혀있지 않을 때 — 이 빈자리에서 (1) 기여 불분명, (2) 논리 점프, (3) verbosity의 세 증상이 동시에 파생된다. ★ 최우선으로 잡아야 할 곳은 거의 항상 *그 한 문장* 이다."

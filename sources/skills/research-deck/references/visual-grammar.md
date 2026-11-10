# 시각 문법 (kit/lib.js)

기준 덱: `~/Downloads/261104-AI5102-SelfImprovingAI-35min.pptx.pdf` (89장/35분). 16:9 (13.333 × 7.5 in), 흰 바탕, Lato,
강조색 하나(금색 A87712), 회색 595959, 지난 단계 44546A. 템플릿이 있으면 색·글꼴은 `theme.json`이 바꾼다.

## 모든 장에 붙는 것 (`add(spec)`)

| spec | 의미 |
|---|---|
| `title` | 주장 한 문장. ≤52자 30pt, ≤62자 26pt, 그 이상 24pt |
| `crumb: ["Q2", "Huginn"]` | 오른쪽 위 `Q2 · Huginn · k/n` (k/n 자동) |
| `cite` | 왼쪽 아래 출처, 그림·절 번호까지. 150자 넘으면 10pt |
| `id` | 제목 없는 장의 대본 key (`"title"`, `"guiding-question"`, `"conclusion"`) |
| `notes` | 대본이 없을 때 노트 (짧은 사실 메모, writer가 근거로 쓴다) |
| `session` | 세션 덮어쓰기 (토론 장 = `"Discussion"`, 시간 예산 밖) |
| `number: false` | 쪽 번호 숨김 |

## 헬퍼

- `figSeq({crumb, cite, title, titles?, fig, layout: "side"|"top", items: [{label, body?, box?}], remark?, notes?: [], figBox?, textBox?, veil?})`
  그림 하나를 단계별로. 단계마다 build 하나, `box`는 그림 비율 `[x0,y0,x1,y1]` 하나나 여러 개(흐림 구멍 + 강조 박스).
  `side`: 왼쪽 그림, 오른쪽 번호 목록이 쌓인다 (지난 단계는 제목만). `top`: 넓은 그림 위, 아래에 현재 단계만. `remark`가 있으면 마지막 build.
  `box` 없이 두면 그림 전체가 보이는 단계 (전체 설명용).
- `image(slide, name, box, align)` → 그린 사각형. `spotlight(slide, r, boxes, {veil})` — 흐림 + 강조 박스 (`veil:false`면 박스만).
- `steps`, `remark(slide, text, box)` — 기울임 `Remark:` 한 문장.
- `bars(slide, box, {bars:[{label, value, color}], max, reveal, current, title, fmt, labelSize})` — 도형 막대, `reveal`개까지 공개.
- `linePlot(slide, box, {xs, ys, yMin, yMax, reveal, highlight, xLabel, yLabel, fmt})` → `{X, Y}` (주석 위치 계산용).
- `table(slide, box, header, rows, {reveal, current, colW, size})` — 행 단위 공개, 현재 행 옅은 강조색.
- `text(slide, runsOrString, box, opts)`, `ledger(slide, QS, {answered, current})`.
- `common.js`: `cover("Q2", notes)` 큰 질문 표지 + 원장, `answer("Q2", {short, evidence: [{t, src, kind:"but"?}]})`.

## 규칙

- 공개 순서 = 말하는 순서. 같은 그림 build는 같은 제목 (`titles`로 단계별 제목을 줄 수 있다).
- 강조 박스 좌표는 렌더를 보고 맞춘다. 박스가 다른 막대·글자를 반쯤 자르면 다시 잡는다.
- 표·막대·선 그래프는 그림 캡처보다 도형으로 다시 그린다 (값을 강조하고 단계 공개하기 위해). 수치는 다이제스트 그대로, 자릿수 유지(`fmt`).
- 우리 해석은 회색 상자 `[ours]`. 증거 약점은 `Remark:`나 `But` 줄에 화면에 적는다.
- 콜백: 앞에서 쓴 그림·그래프를 뒤 절에서 다시 그릴 때는 함수로 빼서 두 곳에서 부른다 (기준 사례 `ouroMMLU`).
- 질문 절마다: 표지 → 근거 장들 → `Answer to Qn` (✓ 줄 + But 줄, 다음 질문으로 넘기는 But).
- 세션이 나뉘면 앞 세션 끝에 hand-off 장 (남은 질문 → 다음 세션 Q).

---
name: research-deck
description: 논문 여러 편으로 연구 발표 덱(.pptx)을 만든다. 배경→Gap→질문(RQ)→절마다 질문 회수→Q/A 종합→결론·토론의 논문식 서사, 한 슬라이드 한 아이디어, 그림 위 편집 가능한 강조 도형(흐림+강조 박스, 단계별 공개), 발표 시간 예산에 맞춘 build 수와 슬라이드별 발표 대본(노트), 사용자 템플릿(.pptx/.potx) 적용. 트리거 — 연구 발표 PPT, 논문 발표 슬라이드, 세미나 발표 덱, 저널 클럽, 발표 대본 써줘, 슬라이드 노트, research talk deck, research-deck.
---

# research-deck

논문을 근거로 한 연구 발표 덱을 **코드로** 만든다 (pptxgenjs, `kit/`). 내용은 `build/*.js`, 대본은 `build/script/<lang>/*.md`,
시간 예산은 `build/talk.js`에 두고, pptx는 매번 다시 빌드한다. pptx를 직접 고치지 않는다.

산출물: `build/out/deck.pptx` (모든 도형 편집 가능, 노트 = 대본 + `[⏱ 초 · 누적 / 예산]`), `build/out/timing.md`, `build/out/manifest.json`, 렌더 QA 시트.

기준 사례: `~/Workspace/looped-transformer-talk/` (AGI26F, 2×30분, 149 build). 막히면 그 `build/`를 먼저 본다.

## 절대 규칙

1. **서사는 질문 원장이다.** 배경 → 선행연구 종합 → Gap → 질문(Q1…Qn) → 절마다 질문 하나에 답 → `Answer to Qn` → Q/A 종합 → 결론·토론. 질문은 표지·답 슬라이드의 원장 칩으로 추적한다.
2. **한 슬라이드 한 아이디어** (종합 슬라이드만 예외). 제목은 주장 한 문장. 글자는 적게, 그림은 크게.
3. **그림마다 어디를 볼지 보여 준다.** `figSeq`의 흐림+강조 박스, 한 단계 = 한 build, 끝은 `Remark:` 한 문장. 강조는 모두 PPT 도형(이미지에 굽지 않는다).
4. **사실은 `sources/*.md` 다이제스트에서만.** 다이제스트에 없는 수치·주장은 슬라이드와 대본에 넣지 않는다. 우리 해석은 `[ours]`로 표시한다.
5. **시간 예산이 build 수를 정한다.** 스토리라인 단계에서 절별 분을 정하고, 대본을 쓴 뒤 `timing.md`로 확인한다. 넘치면 cut list 순서로 뺀다 (`references/timing.md`).
6. **렌더해서 눈으로 본다.** 겹침·잘림·강조 위치는 코드로 안 보인다. `qa.sh` 시트를 매 수정 뒤 확인한다.
7. 사용자의 노트 vault 등 원자료 폴더는 읽기만 한다. 외부 업로드(Google Slides 등)는 사용자가 한다.

## Phase 0 — 입력 (한 번에 묻기, 이미 주어진 것은 건너뛴다)

- 주제, 논문 목록·위치(PDF, arXiv id, 노트 vault)
- 발표 형식: 총 시간, 세션·발표자 수와 분, 토론 시간, 날짜, 슬라이드 언어, 청중 수준
- **템플릿**: `.pptx`/`.potx` 경로가 있으면 Phase 3에서 적용, 없으면 기본 스타일(기준 덱 문법, `references/visual-grammar.md`)
- **대본**: 언어, 말투(ditto-writer 프로필 이름 또는 없음), build마다 쓸지 핵심 장만 쓸지 (기본: build마다)

## Phase 1 — 근거

- 논문별 `sources/<paper>.md`: 서지, 핵심 주장, 표·그림 번호와 수치(원문 재확인), 한계·주의. 그래프 판독값은 `[plot]`.
- 쓸 그림을 `figures/<paper>-figN.png`로 자른다 (PDF → `pdftoppm -r 200`, PIL crop). 그림 하나에 강조할 영역이 2–5개면 좋은 그림이다.

## Phase 2 — 스토리라인 + 시간 예산 (승인 받기)

`storyline.md`에:
1. 질문 원장 표 (ID, 질문, 답하는 절, 답 요지) + guiding question + 최종 답 한 문장.
2. 절별 슬라이드 표 (주장 제목, 시각 자료와 build 수, 출처).
3. **시간 예산** (`references/timing.md`): 절별 목표 분, build 수 상한, 세션 경계, **cut list**(넘칠 때 먼저 뺄 장 순서).
4. 콜백·세션 연결 장치(앞 그림을 뒤에서 다시 쓰기, 세션 끝 hand-off 슬라이드).

승인 뒤 `build/talk.js`에 sessions·sections(분)·questions를 옮긴다.

## Phase 3 — 빌드

```bash
K=~/.claude/skills/research-deck/kit; cd <talk>; mkdir -p build/out figures sources
cp $K/{lib.js,common.js,build.js,count.js,talk.js,qa.sh} build/
npm i pptxgenjs@3.12.0                       # 폰트: 기본 Lato (brew install --cask font-lato)
python3 $K/template.py <template.potx> build # 템플릿이 있을 때만 → build/theme.json, build/template/
```
- 절마다 `build/<section>.js` (`module.exports = function () { … }`), 헬퍼는 `references/visual-grammar.md`.
  제목 없는 장(제목 슬라이드·표지)은 `id`를 준다 (`id: "title"`, `cover()`는 자동). 대본 key가 여기서 나온다.
- `node build/build.js` → `zsh build/qa.sh build/out/deck.pptx` → `deck-qa/sheetN.png`을 Read로 보고 고친다. 반복.
- 템플릿을 썼으면 `references/template.md`의 점검표로 본다 (제목 띠와 본문 겹침, 장식과 그림 겹침, 강조색 대비).

## Phase 4 — 발표 대본 (슬라이드 노트)

`references/script.md`를 따른다. 요약:
1. `node build/build.js` 로 `out/manifest.json` 생성 (build별 key, 화면 글자, 기존 notes).
2. `build/script/BRIEF.<lang>.md` 작성: 말투(프로필을 발표 구어로 옮긴 규칙), 사실 규칙, 길이(절별 목표 → 단위), 형식, 자체 점검.
   말투 프로필이 있으면 ditto-writer `profiles/<name>/profile.md`를 writer가 직접 읽게 한다.
3. writer 서브에이전트를 절 묶음별로 **병렬** (같은 BRIEF, 각자 `node build/count.js <section>`만 실행, build.js 금지).
4. 관문: `python3 $K/check_script.py build` (누락·출처 없는 숫자·금지 표현) → `node build/build.js` → `timing.md`가 세션 예산 안인지.
   넘치면 대본을 줄이기 전에 cut list를 먼저 본다 (말을 빨리 하는 것으로 해결하지 않는다).
5. 말투를 더 다듬으려면 ditto-writer 블라인드 리뷰 라운드를 대본 평문으로 돌린다 (선택, 사용자가 원할 때).

## Phase 5 — 납품 보고

경로, build 수와 아이디어 수, 세션별 예상 시간(`timing.md`) vs 예산, 남은 cut 후보, 대본에서 사용자가 확인할 곳(우리 해석·결론·토론),
QA에서 고친 것, 남은 확인(Google Slides 업로드 시 반투명 흐림 유지, 폰트 대체), 다시 빌드하는 명령.

## 파일

- `kit/lib.js` — 시각 문법(`figSeq`, `spotlight`, `bars`, `linePlot`, `table`, `ledger`…), 렌더, 대본 로드, 시간 계산, 템플릿 마스터.
- `kit/common.js` — 질문 원장 장치: `cover(id)`, `answer(id, {short, evidence})`.
- `kit/build.js`, `kit/talk.js` — 빌드 진입점과 발표 설정(세션·절별 분·질문).
- `kit/count.js` — 절 하나의 대본 시간 vs 목표 (writer용). `kit/check_script.py` — 대본 관문.
- `kit/template.py` — .pptx/.potx → `theme.json`(색·폰트·제목 위치) + 마스터 배경·장식. 16:9만.
- `kit/qa.sh` — LibreOffice 렌더 → PNG + 12장 시트.
- `references/visual-grammar.md`, `timing.md`, `script.md`, `template.md`.

필요: node, pptxgenjs 3.12.0, LibreOffice, poppler(`pdftoppm`), python3 + Pillow.

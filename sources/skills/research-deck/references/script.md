# 발표 대본 (슬라이드 노트)

대본은 `build/script/<lang>/<section>.md`에 두고 빌드 때 노트로 들어간다. pptx 노트를 직접 고치지 않는다.

## 형식

```markdown
# s2_q1

## s2_q1/universal-transformers-reuse-one-block-again-and#1
말할 문장. build당 1–2문단, 목록·굵게 없음.

## s2_q1/universal-transformers-reuse-one-block-again-and#2
…
```
- key = `<section>/<id 또는 제목 slug>#<같은 slug의 n번째 build>`. 다른 곳에 장을 넣어도 key는 안 밀린다.
  같은 제목 묶음 안에 build를 넣거나 빼면 그 묶음의 `#n`은 밀리므로 대본도 같이 옮긴다.
- `<!-- -->` 주석은 무시된다. 빌드 출력의 `script keys with no slide`는 주인 잃은 대본이다.

## 절차

1. `node build/build.js` → `out/manifest.json` (build별 key, title, onSlide, notes, cite).
2. BRIEF 작성: `build/script/BRIEF.<lang>.md`. 아래 뼈대를 채운다.
3. writer 서브에이전트: 절 1–2개씩 병렬, 같은 BRIEF. 지시문 뼈대:
   - 작업 폴더, 맡은 절과 파일 경로, 읽을 순서(BRIEF → 말투 프로필 → storyline.md → manifest의 자기 절과 앞뒤 절 첫·끝 build → 해당 sources).
   - 목표 시간과 확인 명령 `node build/count.js <section>`, build.js 실행 금지(병렬 충돌), 다른 파일 수정 금지.
   - 마지막 답(150단어 이하): count 결과, 자체 점검 결과, 근거가 모자랐던 장, 두 해석 사이에서 고른 장.
4. 관문: `python3 ~/.claude/skills/research-deck/kit/check_script.py build` → 고칠 것은 해당 writer에게 다시 보낸다(SendMessage로 맥락 유지).
5. `node build/build.js` → `timing.md` 확인 → QA 렌더는 노트가 안 보이므로 생략 가능, 노트 확인은 manifest의 `script`.
6. 말투 점검 (말투 프로필을 쓸 때): ditto-writer 블라인드 리뷰어 두 명(Anthropic 서브에이전트 + `codex exec`)에게 대본 평문만 준다.
   평문은 manifest에서 `[슬라이드 n]` + 대본으로 만들고(key·BRIEF·프로필은 주지 않는다), 문단 점수 대신 **부별 점수**와 의심 구간 최대 10개,
   반복 패턴을 묻는다. 두 리뷰어가 함께 짚은 곳과 패턴만 writer 한 명이 고친다 (전 절 대상, heading 고정, 시간 범위 유지). 보통 1–2라운드.
   한계: 블라인드 독자는 질문 회수 장치(절 끝에서 다음 질문 열기, Answer 장의 되짚기)를 기계적 패턴으로 읽는다. 기준 사례에서 r1 60/68% → r2 60/70%로
   더 내려가지 않았다. 장치를 없애지 말고 말투만 다양하게 한다 (넘기는 문장은 절 끝에만, 형태를 매번 다르게). 고친 라운드에서 점수가 내려가지 않으면 두 리뷰어가 연속으로 짚은 build만 한 번 더 고치고 멈춘다.
7. 사용자 확인이 필요한 곳을 보고: `[ours]` 해석, 결론·토론 대본, writer가 짚은 근거 부족 장.

## BRIEF 뼈대

- 무엇을 쓰나: build마다 발표자가 소리 내어 말할 문장. 발표자, 청중 수준, 나중에 다른 언어로 옮기는지.
- 입력: manifest, storyline.md, sources/*.md, 말투 프로필 경로(있으면).
- 말투: 프로필을 **발표 구어**로 옮기는 규칙. 한국어면 합니다체 기본(-요체·반말 없음), 1인칭 `저희는`, 단문 위치, 문장 길이,
  프로필의 Never 목록 + 발표판 금지(자문자답 뒤 단답, 예고 후 나열, 같은 문장 틀 반복, 화면 문장 그대로 읽기, `금색 박스를 보시면` 반복).
  첫 라운드부터 넣을 것 (기준 사례 r1에서 두 리뷰어가 공통으로 잡은 것, AI 인상 60–68%, 결론부 70–88%):
  근거를 네 절·두 절 평행으로 맞춘 종합문, 교차 대구, 개념 정의로 끝맺는 격언풍 결론, 증거 끝마다 `다만` 단서(덱 전체 6회 이하),
  `X이지 Y가 아닙니다`(3회 이하), 묻지 않은 오해 부정, 질문 행선지 안내(`Q3가 받습니다`), Answer 장마다 같은 틀, 일반 명사 표기 혼용(루프/loop).
  프로필의 강점 규칙을 덱 구조에 연결 (질문 재설정 = 표지→비교 설계→Answer, 기준 먼저 = 비교 슬라이드).
- 사실: 수치·이름은 onSlide·notes·sources만, 화면과 같은 자릿수. 고유명·지표명은 화면 표기 그대로. `[ours]`는 말로도 밝힌다.
- 길이: 단위 정의, 절 목표 −10% ~ +3%, build 종류별 가이드(그림 단계 40–90 단위, Remark 40–80, 표·막대 50–110,
  아이디어 100–220, 표지 80–150, Answer 150–250, 토론 60–120; 한국어 단위 기준).
- 형식과 자체 점검(count.js, 금지 표현 grep, 숫자 출처, 연속 3 build 같은 시작).

기준 사례 BRIEF: `~/Workspace/looped-transformer-talk/build/script/BRIEF.ko.md`.

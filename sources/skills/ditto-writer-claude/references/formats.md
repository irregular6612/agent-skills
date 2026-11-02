# 작업 폴더 · 파일 형식 (Phase 2–3)

프로필 폴더 형식은 `profile_schema.md`.

## 길이 상한 (단일 기준표)

스킬이 저장·누적하는 모든 파일은 이 표를 따른다. 단어 = 공백으로 나눈 토큰 (영어 단어, 한국어 어절).
검사: `python3 scripts/check_lengths.py --profile <프로필폴더>` / `--work <작업폴더>` / `<파일...>` (넘으면 종료 코드 1).

| 파일 | 상한 | 넘을 때 먼저 뺄 것 | 상한의 이유 |
|---|---|---|---|
| `profiles/<이름>/profile.md` | 700단어 (anchor 포함) | 신뢰도 낮은 O 등급 → 장르 전이 세부 → 설명 문장 | writer 가 매 라운드 읽는다. 길면 비용이 늘고 핵심 지시가 묻힌다 |
| `profiles/<이름>/evidence.md` | 1,200단어 | 중복 인용 → 버린 trait 목록 → run 간 비교 서술 | profile.md 의 근거 보관용. 재분석·감사 때만 읽는다 |
| `profiles/<이름>/meta.yaml` | 25줄 | 주석 | 목록 화면에서 읽는 요약 |
| `profiles/<이름>/sample.md` · `counts.json` | 없음 | — | 원본과 기계 출력 |
| 분석 중 `_work/stage{1,2}_run*.md` | 각 1,500단어 | O 등급 항목 → 인용 3개째 → 설명 | 병합 입력 크기 제한. 조립 뒤 `_work/` 통째로 삭제 |
| 분석 중 `_work/stage1.md` (병합) | 1,200단어 | 버린 trait 설명 → 중복 인용 | 같음 (조립 뒤 삭제) |
| 작업 폴더 `BRIEF.md` | 900단어 | 반복된 금지 패턴 설명 → 예시 | 규칙이 바뀌면 **덮어써서** 갱신 (덧붙이지 않는다). 이력이 필요할 때만 `BRIEF_vN.md` 로 옛 판 보관 (같은 상한) |
| `CHANGELOG.md` | 한 행(버전·리뷰 하나) ≤ 200자 | 메모 칸 | 라운드가 쌓여도 한 화면 |
| `writer_rN.md` | 600단어 | 동의한 지적의 이유 → 점검 출력 원문(요약만 남김) | 매 라운드 누적 |
| `blind_rN_<provider>.md` | 600단어 | 낮은(low) 의심 구간 → 사람 같은 구간 설명 | 매 라운드 누적, writer 입력 |
| `logs/*.txt` (codex 마지막 메시지) | 300단어 | — | 프롬프트가 "마지막 답은 3줄 이하" 를 요구 |
| `prompts/*.md` (보낸 프롬프트 사본) | 1,000단어 | — | 템플릿 자체가 이보다 짧다 |
| 원문에서 나온 것 (`v0_context.md`, `vN.*`, `external_reports.md`) | 없음 | — | 원문 길이를 따른다 (vN 은 ±15% 규칙) |

**절차**: 파일을 쓴 쪽이 상한 안에서 쓴다 (모든 템플릿에 상한 문장이 있다). 오케스트레이터는 쓰기 직후
`check_lengths.py` 를 돌리고, 넘으면 **같은 작성자에게 한 번** "N단어 이하로 줄여라, 우선순위 낮은 항목부터" 를 요청한다.
그래도 넘으면 그대로 진행하고 CHANGELOG 메모와 최종 보고에 "길이 초과" 를 적는다.

## 작업 폴더

```
<원본폴더>/ditto_<YYYYMMDD>/      (또는 scratchpad/ditto_<YYYYMMDD>/)
├── v0_original.<ext>      원본 복사본. 스크립트는 이것만 읽는다. 원본 파일은 끝까지 안 건드린다.
├── PROFILE                쓰는 프로필 이름 한 줄 (예: juhyeon-en-academic)
├── v0.json | v0.md        고쳐 쓸 대상 (docx면 extract_docx.py 출력)
├── v0_context.md          전체 문서 + 표지 (FIXED / USER SAMPLE / TARGET / EQUATION / HEADING)
├── v0_meta.json           (docx) 대상·샘플·수식 도입부 인덱스, 단어 수
├── BRIEF.md               writer 용 규칙 (아래 템플릿). 블라인드 리뷰어에게는 주지 않는다.
├── vN.json | vN.md        writer 버전 N
├── vN.docx, render/vN.pdf (docx) apply_docx.py · render_check.py 결과
├── writer_rN.md           writer 라운드 N: 블라인드 지적 판정 + 변경 기록 + L2 흔적 목록 + 점검 출력
├── blind_rN_anthropic.md  vN 에 대한 블라인드 판독 (Anthropic 새 인스턴스)
├── blind_rN_openai.md     vN 에 대한 블라인드 판독 (OpenAI 새 인스턴스)   ※ r0 = 원문 v0 기준선
├── prompts/               실제로 보낸 프롬프트 전문
├── logs/                  codex -o 마지막 메시지, 실패 로그
├── final/                 최종 docx/pdf
└── CHANGELOG.md           버전·라운드별 기록 + 점수표
```

블라인드 폴더는 작업 폴더 **밖** (scratchpad/`ditto_blind_<무작위>/`), 라운드·리뷰어마다 새로 만든다.
안에는 `document.pdf`(또는 `document.md`)와 `document.txt` 만. 파일 이름·문서 속성에 버전·ditto 같은 말이 없어야 한다.

## BRIEF.md 템플릿 (writer 전용, ≤ 900단어)

오케스트레이터가 쓴다. 규칙이 바뀌면 이 파일을 **덮어써서** 바뀐 규칙으로 교체한다 ("추가 규칙" 절을 덧붙이지 않는다).
이력이 꼭 필요하면 덮어쓰기 전 판을 `BRIEF_vN.md` 로 복사해 둔다.

```markdown
# Brief — <문서 이름> 재작성 (writer 전용)

## 과제
`v0_context.md` 는 <문서 설명>. `(TARGET)` 단위를 다시 써서
1. 프로필 <profile-name> 의 사람이 쓴 것처럼 들리게 하고,
2. 처음 보는 독자가 사람이 쓴 글, 한 사람이 쓴 글로 읽게 한다.
판정은 매 라운드 이력 없는 새 리뷰어 둘(Anthropic·OpenAI)이 렌더된 결과물만 보고 한다.

## 절대 제약
- 고정: USER SAMPLE, HEADING, EQUATION, FIXED 단위는 한 글자도 안 바꾼다.
- Content ledger (매 버전에 모두 남아야 한다. 더 거칠게·짧게·다른 문장에 접어 넣는 건 된다):
  1. ...
- 수식 도입부: [a], [b] 는 바로 뒤 수식을 이끄는 끝맺음 유지.
- 길이: 대상 전체 <W>단어 ±15% (<lo>–<hi>). 쪽수: 원본과 같은 <n>쪽.
- 본문 기호: 날 유니코드(p̂, lⱼ, ₋₁) 금지 → `$...$` 인라인 수식 또는 말로.
- L2 흔적: <on|off> (profile §3).

## 프로필
`<프로필 경로>/profile.md` + anchors (§7). 장르 전이: <같음 | 프로필 §6 의 adapt/drop 적용>.

## 작성 원칙
필수 읽기: `<스킬 절대경로>/references/principles.md`.
적용 범위: <문서 장르와 이번 작업에 적용할 항목; CogSci 전용 항목은 해당 원고에만 적용>.
사용자의 현재 요청과 고정 범위를 우선한다. 원칙은 writer에게만 전달하고 블라인드 입력에는 넣지 않는다.

## 멈춤 규칙
두 블라인드 리뷰어 모두: 대상 부분 점수 ≤ <30>%, 대상 안 high 0개, "한 사람이 쓴 글" = 예. 최대 <6> 라운드.

## 출력
`vN.json`(v0.json 과 같은 키) 또는 `vN.md`, 그리고 `writer_rN.md`.
```

## writer_rN.md 구성 (≤ 600단어)

1. **블라인드 지적 판정** (N≥2, 또는 r0 기준선이 있으면 N=1 에도): 두 보고서의 항목마다
   `| 출처(a/o) | 지적(인용) | 판정 동의/부분/반대 | 이유 (BRIEF·프로필 근거) | 이번에 한 일 |`.
   두 리뷰어가 같이 짚은 항목은 표시한다.
2. **변경 기록**: 단위별로 무엇을 왜 (구조 변경인지 단어 교체인지). 안 바꾼 단위는 "그대로".
3. **의도적 L2 흔적 목록**: `[단위] "인용" — profile §3 의 어떤 유형` (정의·변수·수식 도입부 밖인지 확인).
4. **Content ledger 위치표**: 항목 번호 → 단위·인용.
5. **점검 출력**: check_version.py, stage1_counts.py --ref 결과의 요약 몇 줄 (FAIL·벗어난 지표만. 원문 전체를 붙이지 않는다).
6. **자기 점검**: 아직 이 사람처럼 안 들리는 문장. (자기 점수는 선택. 멈춤 판정에 쓰지 않는다.)

## 블라인드 보고서 (`blind_rN_<provider>.md`, ≤ 600단어)

prompts.md §3 의 6개 항목 + 마지막 줄:
```
BLIND_JSON: {"overall": 40, "paragraphs": [["Does an LLM try harder to", 25], ...], "high_spans": ["..."], "one_person": false}
```
오케스트레이터가 `blind_score.py` 로 대상 문단에 맞춰 집계한다:
```bash
python3 $S/blind_score.py --targets "$WD/vN.json" "$WD/blind_rN_anthropic.md" "$WD/blind_rN_openai.md" --threshold 30
# md: --md "$WD/vN.md" --fixed <고정 블록 번호>
```
- 대상 부분 점수 = 대상 문단 점수의 단어 수 가중 평균, 대상 최고점도 같이 기록.
- high 는 대상 안/밖을 나눠 센다 (밖 = 사용자 고정 부분 등. 멈춤 판정에는 대상 안만).
- 종료 코드 0 = 두 리뷰어 모두 PASS = 멈춤.

## CHANGELOG.md 형식 (버전·리뷰당 한 행, 행 ≤ 200자)

헤더(원본·프로필·모델·멈춤 규칙)는 처음 한 번만 쓰고, 이후에는 행만 덧붙인다. 메모 칸은 한 구절.

```markdown
# Version log — <문서 이름>

원본: `<원본 절대경로>` (수정 안 함, 복사본 `v0_original.<ext>`)
프로필: <profile-name> (샘플 <N>단어, 신뢰도 <low/...>) · L2 흔적 <on/off>
writer: <모델> (<Codex|Agent>) — 본문 수정은 writer만
블라인드 리뷰어: Anthropic <모델> / OpenAI <모델> — 매 라운드 새 인스턴스, 결과물만 봄
멈춤 규칙: 두 리뷰어 모두 대상 ≤ <30>%, 대상 high 0, 한 사람 = 예 / 최대 <6> 라운드

| 라운드 | 버전 | 길이 | A 전체 | A 대상(최고) | A high | A 한 사람 | O 전체 | O 대상(최고) | O high | O 한 사람 | 판정 | 메모 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r0 | v0 | 406 | 60 | 70 (75) | 2 | 아니오 | ... | | | | 기준선 | 온도 차이 지적 |
| r1 | v1 | 435 (+7.1%) | | | | | | | | | REVISE | |
| final | vK | | | | | | | | | | | final/<이름>.docx, 원본과 같은 2쪽 |
```

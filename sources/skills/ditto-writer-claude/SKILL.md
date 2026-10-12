---
name: ditto-writer
description: 내가 직접 쓴 글로 만든 문체·저자 프로필로, 사람이 쓴 것처럼 글을 다시 쓰는 루프(writer 1 + 매 라운드 새 블라인드 리뷰어 Anthropic·OpenAI). 트리거 — 내 말투로 바꿔줘, 사람이 쓴 것처럼, 내 문체 프로필, ditto-writer.
---

# ditto-writer

글 하나를 (1) 사용자 본인이 쓴 것처럼, (2) 처음 보는 독자가 사람이 쓴 한 사람의 글로 읽게 다시 쓴다.
사용자의 글 샘플로 만든 **프로필**(습관 + 저자 모델 + 원문 anchor)을 바탕으로 **writer 모델 하나**가 고치고,
매 라운드 **이력 없는 새 블라인드 리뷰어 둘**(Anthropic 하나, OpenAI 하나)이 렌더된 결과물만 읽고 판독한다.

너(Claude Code 본 세션)는 **오케스트레이터**다. 본문은 직접 고치지 않는다. 파일 준비, 모델 호출, 기계 검사,
점수 집계, CHANGELOG, 사용자 보고만 한다.

## 이렇게 생긴 이유 — 1회차에서 배운 것

- 문체만 보는 리뷰로 PASS 가 난 버전을 외부 독자 둘은 **AI 인상 60%** 로 봤다. 사용자 문단(거칢)과 나머지(정돈됨)의
  **온도 차이**가 가장 큰 단서였다.
- 두 모델이 리뷰어 겸 판독기로 매 라운드 서로의 파일을 읽자 점수가 30% 로 **수렴**했다. 그런데 같은 글을 이력 없는
  블라인드 독자들은 전체 35–55%, 고쳐 쓴 부분 45–65% 로 봤다. 루프 안 리뷰어는 서로에게 **닻이 내려간다.**
  → 그래서 리뷰어를 **매 라운드 새 인스턴스, 결과물만, 블라인드**로 바꿨다.
- 본문에 붙여 넣은 유니코드 기호(p̂, lⱼ₋₁)는 "챗봇 답변 복사" 신호였다 → Word 인라인 수식으로.
- 리서치(`references/stage1_low_level.md` 근거 표기): 예시만 주는 few-shot 은 generic 톤으로 수렴하고, 프로필만 주면
  judge 점수만 오른다. **프로필 + 원문 anchor** 를 같이 주고, 짧은 샘플에서는 **"절대 안 하는 것"** 목록이 가장 믿을 만하다.

## 절대 규칙

1. **본인 글만.** 프로필은 사용자 본인이 AI 도움 없이 쓴 글로만 만든다. 남의 글로 프로필을 만들지 않는다.
2. **원본은 읽기만.** 작업 폴더에 복사본을 만들고, 납품은 새 이름으로. 덮어쓰지 않는다.
3. **본문은 writer 만 고친다.** 리뷰어·오케스트레이터는 안 고친다.
4. **리뷰어는 매 라운드 새로, 블라인드로.** 결과물(PDF/텍스트)만 있는 별도 폴더. BRIEF·샘플·프로필·이력·목표 점수·
   어디를 고쳤는지를 주지 않는다. 같은 인스턴스를 다시 쓰지 않는다.
5. **writer 는 블라인드 지적을 항목별로 판정한다** (동의 / 부분 동의 / 반대 + 이유). 고정 범위·내용을 깨는 제안은 거절한다.
6. **의미 손실 금지.** content ledger 와 기계 검사(check_version.py)는 매 라운드 관문이다.
7. **프로필 저장·덮어쓰기는 사용자 확인 후에만.**
8. **길이 상한을 지킨다.** 저장·누적되는 파일(프로필, evidence, meta, BRIEF, CHANGELOG, writer·블라인드 노트, 로그)은
   `references/formats.md` 의 **"길이 상한"** 표가 기준이다. 템플릿마다 상한 문장이 있고, 오케스트레이터는 쓰기 직후
   `check_lengths.py` 를 돌려 넘으면 작성자에게 **한 번** 줄이기를 요청한다 (그래도 넘으면 기록하고 진행).

## 인자

`/ditto-writer profile=juhyeon-en-academic writer=gpt-6-astra rev-anthropic=fable rev-openai=gpt-6-astra rounds=6 threshold=30 slips=on baseline=on`

| 인자 | 값 | 기본 |
|---|---|---|
| `profile=` | `profiles/` 안의 이름, 또는 `new` | 본인 기본 프로필(언어·장르 맞으면 제안) |
| `writer=` | `fable`/`opus`/`sonnet`/`haiku` → Agent, 그 밖 → Codex 모델 id | `~/.codex/config.toml` 의 `model` |
| `rev-anthropic=` | `fable`/`opus`/`sonnet`/`haiku` | `fable` |
| `rev-openai=` | Codex 모델 id | config 의 `model` |
| `rounds=` / `threshold=` | 최대 라운드 / 대상 부분 AI 인상 상한 % | 6 / 30 |
| `slips=` | `on`/`off` — 프로필의 L2 흔적 재현 여부 | 질문 (제출용이면 off 고려) |
| `baseline=` | `on`/`off` — 원문 v0 를 먼저 블라인드 판독(r0) | `on` |

---

## Phase 0 — 입력 확보 (항상 먼저)

시작 줄: `ditto-writer / 프로필: <이름> / writer: <모델> / 리뷰어: <A 모델> + <O 모델> / 작업 폴더: <경로>`

1. **프로필 확인 (가장 먼저).** `ls ~/.claude/skills/ditto-writer/profiles/*/meta.yaml` 을 읽는다.
   - 인자로 이름을 받았거나, `owner: self` 이면서 언어·장르가 맞는 프로필이 있으면: "기존 프로필 <이름> (샘플 <N>단어,
     <장르>, 신뢰도 <..>) 을 쓸까요, 새 샘플로 만들까요?" → 쓰면 **Phase 1 을 건너뛴다.**
   - 기본 기대는 "내 말투" 다. 본인 기본 프로필(`default: true`)이 있으면 그것을 먼저 제안한다.
   - 대상 언어가 프로필 언어와 다르면 새 샘플을 권한다. 장르만 다르면 프로필 §6 장르 전이를 쓰겠다고 알린다.
   - 프로필이 없거나 새로 만들기로 하면: **본인이 직접 쓴 글 샘플**을 요청한다 ("AI·교정 없이 직접 쓴 글, 가능하면
     같은 언어·장르, 300단어/800자 이상이면 좋음"). 샘플 없이는 진행하지 않는다.
2. **확인할 것 (한 번에).** 대상 텍스트/파일 (docx, md, txt, 붙여 넣기), 고정할 부분 (사용자가 쓴 부분, 제목, 수식,
   양식 칸, 인용), 언어, 쪽수 제한, `slips` on/off.
3. **모델.** 인자로 받았으면 그대로. 아니면 AskUserQuestion 한 번에 세 질문: writer 모델, Anthropic 리뷰어, OpenAI 리뷰어.
   기본: writer = config 의 OpenAI 모델, 리뷰어 = 같은 OpenAI 모델 + fable. `which codex` 가 없으면 알리고 멈춘다.
4. **작업 폴더.** 기본 `<원본폴더>/ditto_<YYYYMMDD>/`. 원본이 Obsidian vault 의 공개 폴더 안이면 scratchpad 를 기본으로
   제안한다. 폴더가 이미 있고 CHANGELOG.md 가 있으면 **이어하기** (마지막 라운드부터).
5. **준비** (형식은 `references/formats.md`):
   ```bash
   WD=<작업폴더>; S=~/.claude/skills/ditto-writer/scripts
   mkdir -p "$WD"/{prompts,logs,final,render}
   cp "<원본>" "$WD/v0_original.docx"                       # 원본은 다시 안 건드린다
   python3 $S/extract_docx.py "$WD/v0_original.docx" "$WD"                         # 번호 확인용
   python3 $S/extract_docx.py "$WD/v0_original.docx" "$WD" --sample 2 --fixed 0,22  # 확정
   # md/txt: v0.md 로 복사하고 v0_context.md 를 직접 만든다 (블록마다 [번호] (FIXED/USER SAMPLE/TARGET/EQUATION))
   ```
   `v0_context.md` 의 표지를 보여 주고 고정/대상 범위를 확인받는다.

## Phase 1 — 문체·저자 분석 (프로필이 없거나 새로 만들 때만)

결과는 스킬 안 `profiles/<profile-name>/` 에 재사용 가능한 프로필로 남는다 (`references/profile_schema.md`).
단계마다 지시문 전문이 references 에 있다. 서브에이전트에게 그대로 채워 보낸다.

1. **Stage 0 — 샘플 위생** (오케스트레이터): 본인 글인지·교정 여부 확인, 장르·언어·L1 메타, 인용·수식·코드 제거,
   `stage1_counts.py sample.md --json counts.json`, AI 신호가 잡히면 교정 전 원본을 묻는다,
   300단어 이상이면 A/B 분할. 분석 중간 파일은 프로필 폴더의 `_work/` 에 둔다.
2. **Stage 1 — Low-level mimic** (`references/stage1_low_level.md`): 글에 보이는 습관.
   계량은 스크립트, 해석은 서브에이전트 **독립 3회** (Anthropic·OpenAI·Anthropic 섞어서) → 병합 서브에이전트가
   **3회 중 2회 이상 + 원문 인용 확인** 필터. 결과: H/T/O/N 등급 습관 표(빈도 상한 포함), L2 흔적 유형·비율·재현 정책,
   Never 목록.
3. **Stage 2 — High-level mimic** (`references/stage2_author_model.md`): 글을 통해 **저자**를 본다.
   서브에이전트 **독립 2회** → 조립 서브에이전트가 `profile.md`(≤ 700단어, writer 가 읽음)와
   `evidence.md`(≤ 1,200단어, 근거 보관)를 만든다. `check_lengths.py --profile` 통과 뒤 `_work/` 를 지운다
   (run 파일은 남기지 않는다). 역할 태그 시퀀스 → 장르 move →
   저자 배경·전문성, 추론·논증 방식, 개념 도입 방식, 예시·비유·질문, 입장·확신, 독자 → 행동 서술 persona.
   모든 판단에 Stage 1 근거 ID 또는 인용. 형용사 persona·민감 속성 금지. 장르 전이 표, anchor 2–3개(원문 그대로).
4. **사용자 보고 + 저장 확인**: 8–12줄 요약 (stage2_author_model.md "사용자 보고"). 확인 후 `meta.yaml`(≤ 25줄)을 쓰고 저장.
   같은 이름이 있으면 덮어쓸지 따로 묻는다.

## Phase 2 — writer 1 + 블라인드 리뷰어 2 루프

**r0 기준선** (`baseline=on`): v0 를 렌더해 아래 2.3–2.4 를 한 번 돌린다. writer 가 실제 외부 독자 반응에서 출발한다.

라운드 N = 1, 2, … 최대 `rounds`:

### 2.1 writer (prompts.md §1 / §2)
- 입력: BRIEF.md, `profile.md`(anchors 포함), `sample.md`, v0, 직전 버전, 직전 라운드 블라인드 보고서 2건.
- 산출: `vN.json`(또는 `vN.md`) + `writer_rN.md` (블라인드 지적 판정표 → 변경 기록 → L2 흔적 목록 → ledger 위치표 → 점검 출력).
- BRIEF.md (≤ 900단어) 는 Phase 0–1 이 끝나면 formats.md 템플릿으로 오케스트레이터가 쓴다 (content ledger 포함, 사용자 확인).
  규칙이 바뀌면 **덮어써서** 갱신한다 (절을 덧붙이지 않는다). 옛 판이 필요하면 `BRIEF_vN.md` 로 복사.

### 2.2 기계 관문 (오케스트레이터)
```bash
python3 $S/check_version.py "$WD/v0.json" "$WD/vN.json" --sample "$PROFILE/sample.md"
python3 $S/apply_docx.py "$WD/v0_original.docx" "$WD/vN.json" "$WD/vN.docx"          # docx
python3 $S/render_check.py "$WD/render" "$WD/v0_original.docx" "$WD/vN.docx"         # PDF + 쪽수
```
FAIL(키·길이·날 유니코드·`$` 짝·고정 문단 변경·쪽수)이면 리뷰어로 넘기지 않고 writer 를 같은 라운드로 다시 부른다.
`python3 $S/check_lengths.py "$WD/writer_rN.md"` 가 넘으면 writer 에게 한 번 줄이기 요청 (블라인드 보고서도 저장 직후 같은 검사).
md 는 고정 블록이 글자 그대로인지 직접 비교한다.

### 2.3 블라인드 리뷰어 2명 (prompts.md §3, 병렬, 매번 새 인스턴스)
```bash
for p in a o; do B=<scratchpad>/ditto_blind_$RANDOM$RANDOM; mkdir -p "$B"
  cp "$WD/render/vN.pdf" "$B/document.pdf"
  python3 $S/extract_docx.py "$WD/vN.docx" --text-out "$B/document.txt"; echo "$p $B"; done
```
- OpenAI: `codex exec -m <rev-openai> --skip-git-repo-check --ephemeral -s read-only -C "<B_o>" -o "$WD/blind_rN_openai.md" - < "$WD/prompts/blind.md"`
  (Bash `run_in_background: true`, `timeout: 3600000` — 10분을 넘기는 일이 흔하다. 완료 알림을 기다린다.)
- Anthropic: Agent(`general-purpose`, `model: <rev-anthropic>`), 블라인드 문안 + `<B_a>` 경로만. 답을 `$WD/blind_rN_anthropic.md` 로 저장.
- 둘을 한 메시지에서 동시에 띄운다. 결과를 미리 짐작해 쓰지 않는다.

### 2.4 집계와 멈춤
```bash
python3 $S/blind_score.py --targets "$WD/vN.json" "$WD/blind_rN_anthropic.md" "$WD/blind_rN_openai.md" --threshold 30
```
- **멈춤**: 두 리뷰어 모두 대상 부분 점수 ≤ threshold, 대상 안 high 0, "한 사람이 쓴 글" = 예 (종료 코드 0) → Phase 3.
- 아니면 N+1 (writer 가 두 보고서를 판정하고 고친다). 최대 라운드에 닿으면 멈추고, 두 리뷰어 대상 점수 중 큰 값이
  가장 낮은 버전(동점이면 high 적은 것, 그다음 나중 것)을 최종 후보로 넘기며 "수렴 안 됨" 을 보고한다.
- `CHANGELOG.md` 점수표에 한 행 (≤ 200자, formats.md). 라운드 끝에 `check_lengths.py --work "$WD"`. 사용자에게 라운드마다 한 줄:
  `r3: v3 448단어(+10%) | A 대상 35 (최고 45) high 0 한 사람 예 | O 대상 30 (최고 40) high 1 아니오 | REVISE`
- 못 맞춘 대상 문단(`unmatched_targets`)이 있으면 보고서를 열어 직접 맞춘다.
- 사용자가 외부 판독 결과를 붙여 주면 `external_reports.md` 로 저장하고 다음 writer 입력에 넣는다.

### 2.5 교훈 (BRIEF 와 writer 프롬프트에 들어 있다)
- **온도를 맞춘다.** 고정된 사용자 부분이 있으면 나머지를 그 수준으로 내린다. 첫 제목에서 수준이 뛰면 잡힌다.
- **L2 흔적은 프로필에 있는 유형만, 관찰 비율 이하로.** 정의·변수·수식 도입부 안 금지, 개수 할당·희화화 금지.
  "결함 더하기" 보다 "AI 기본값 빼기"(Never 목록)가 안전하다.
- **피할 패턴**: 자문자답 + "Not always.", 슬로건 한 줄 결론, 고른 문장 길이, 예고 후 나열, 완벽한 3·4항 체크리스트,
  방어적 헤지의 깔끔한 독립 문장, 샘플보다 높은 어휘, 샘플에 없는 em-dash, 본문 날 유니코드 수식.
- **구조로 고친다.** 단어 교체로 안 내려가는 문단은 개념 도입 방식·정보 순서를 바꾼다. 공식처럼 반복하지 않는다.
- **범위를 좁힌다.** 라운드 2부터 기준을 넘거나 지목된 대상 문단만 고친다.
- **점수는 인상이다.** 블라인드 리뷰어도 측정기가 아니다. 몇 점 차이는 잡음, 두 리뷰어가 함께 짚은 곳이 신호다.

## Phase 3 — 납품

1. 최종 버전 복사: `final/<원본stem>_ditto_vN.docx` 와 `render/vN.pdf` → `final/`. md/txt 는 `final/<이름>.md`.
   쪽수는 2.2 에서 이미 같은 렌더러로 확인했다 (Word 에서의 쪽 넘김은 보장 안 됨).
2. **보고 (한국어)**:
   - 최종 파일 경로, 작업 폴더, 쓴 프로필 (샘플 길이·신뢰도)
   - 라운드 수, 수렴 여부
   - 점수표: r0 → 마지막 라운드, 리뷰어별 전체 % · 대상 % (최고) · 대상 high · 한 사람 여부
   - 마지막 라운드의 두 리뷰어가 가장 의심한 구간 (남아 있다면)
   - 남겨 둔 의도적 L2 흔적 목록 (최종 writer_rN.md 그대로)
   - 제출 전 확인: Word 에서 쪽 넘김·수식 확인, 의미가 바뀐 곳이 없는지 본인이 한 번 읽기, 양식 칸 채우기,
     제출처가 AI 사용 고지를 요구하면 사실대로 적기, 블라인드 점수는 판독기 결과가 아니라는 점.

## 파일

- `scripts/extract_docx.py` — docx → `v0.json` / `v0_context.md` / `v0_meta.json` (`--sample/--fixed/--target`), 또는 `--text-out` 블라인드용 평문.
- `scripts/apply_docx.py` — 원본 복제본에 문단 교체, `$...$` → Word 인라인 수식. 고정 문단 수정·원본 덮어쓰기 차단, 저장 뒤 고정 문단 XML 검증.
- `scripts/check_version.py` — 길이 ±15%, 키, 수식 도입부, 날 유니코드, `$` 짝, 대시, 문장 길이 분포 (json/md).
- `scripts/render_check.py` — LibreOffice PDF 렌더 + 원본 대비 쪽수 (다르면 종료 코드 1).
- `scripts/stage1_counts.py` — 결정적 계량 (en/ko 자동), `--ref counts.json` 으로 생성 글을 프로필과 비교.
- `scripts/blind_score.py` — 블라인드 보고서 BLIND_JSON → 대상 부분 점수·high·한 사람 여부·멈춤 판정.
- `scripts/check_lengths.py` — 길이 상한 검사 (`--profile` 은 중간 파일 잔존·인용 원문 대조까지, `--work`, 파일 지정).
- `references/stage1_low_level.md`, `references/stage2_author_model.md` — Phase 1 서브에이전트 지시문과 절차.
- `references/profile_schema.md` — 프로필 폴더·`meta.yaml`·`profile.md`·`evidence.md` 스키마(섹션별 단어 예산), writer 에게 주는 방식.
- `references/prompts.md` — writer r1 / rN, 블라인드 리뷰어 템플릿.
- `references/formats.md` — **길이 상한 표**, 작업 폴더, BRIEF 템플릿, writer_rN 구성, 블라인드 보고서, CHANGELOG 점수표.
- `profiles/<name>/` — 저장된 프로필 (meta.yaml · profile.md · evidence.md · sample.md · counts.json).
  현재: `juhyeon-en-academic` (영어 학술 과제, 135단어, 신뢰도 low) ·
  `juhyeon-ko-academic` (한국어 연구 요약문, 551어절 + holdout 119어절, 신뢰도 medium).

필요: `python-docx`, `lxml`, Codex CLI, LibreOffice (docx 렌더).

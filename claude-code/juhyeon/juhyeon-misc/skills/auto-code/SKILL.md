---
name: auto-code
description: >-
  아이디어에서 구현 계획까지 잇는 4단계 파이프라인. grilling 문답으로 설계를 캐내
  설계문서로 굳히고, 브릿지 서브에이전트가 그 문서를 superpowers spec으로 변환하고,
  writing-plans로 실행 계획을 만든 뒤, 다음 세션에 붙여넣을 hand-off 프롬프트까지 남긴다.
  TRIGGERS - 이거 만들고 싶어, 기능 하나 설계부터 계획까지, auto-code, 파이프라인으로
  계획 세워줘, 아이디어부터 plan까지, grilling부터 시작해서 계획까지.
  구현(SDD) 실행은 포함하지 않는다 — handoff까지가 종점.
  이미 spec이 있으면 곧바로 /superpowers:writing-plans.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Agent
  - Skill
  - AskUserQuestion
---

# auto-code

grilling + domain-modeling(설계 문답) → 설계문서 어댑터 → spec-bridge(형식 변환)
→ writing-plans(실행 계획) → handoff(다음 세션 프롬프트)를 잇는 오케스트레이터.

**이 스킬은 어떤 문답도 직접 하지 않는다.** 순서, 게이트, 실패 복구만 담당한다.
설계 질문은 grilling이, 계획 수립은 writing-plans가 한다. 다만 grilling은 파일을
쓰지 않으므로, 그 대화를 설계문서로 굳히는 어댑터(Stage 1-b)만은 오케스트레이터가
직접 수행한다 — 이것이 유일한 예외다.

## 불변 규칙

- 기존 스킬 파일을 수정하지 않는다.
- 게이트 판정은 `scripts/gate.sh`에만 있다. 이 파일에 grep 패턴을 복사하지 않는다.
- 게이트 실패 시 브릿지/재작성 재디스패치는 단계당 최대 1회. 재디스패치 후에도
  같은 이유로 게이트가 또 실패하면(총 2회째) **자동 재디스패치를 STOP**하고,
  오케스트레이터가 사용자에게 직접 물어 채우는 수동 복구로 전환한다 — 이는
  세 번째 재시도가 아니라 복구 경로이므로 실패 횟수에 포함하지 않는다.
- **설계 문답을 두 번 시키지 않는다.** 어떤 실패 경로에서도 금지.
  GATE1 실패는 문서 교정으로 푼다.
- 산출물은 전부 git에 커밋한다.
- `$DESIGN_DOC` `$SPEC` `$PLAN` `$TOPIC_SLUG` `$TOPIC_TITLE` `$REPO` 표기는 셸 변수가 아니라
  자리표시자다. Bash 도구 호출마다 새 셸이 열려 이전 호출의 변수는 사라지므로,
  값을 확보하는 즉시 절대경로 리터럴로 이후 모든 명령에 직접 적어 넣는다.
  저장소 루트가 필요한 커밋 블록은 매번 `cd "$(git rev-parse --show-toplevel)"`로
  그 호출 안에서 다시 구한다.

## Stage 0 — 사전 점검과 재개 스캔

```bash
git rev-parse --show-toplevel 2>/dev/null || echo "NOT_A_REPO"
```

`NOT_A_REPO`이면 즉시 중단하고 사유를 알린다. 산출물을 커밋할 곳이 없다.

```bash
REPO=$(git rev-parse --show-toplevel)
echo "REPO=$REPO"
ls -t "$REPO/docs/superpowers/designs"/*-grill.md 2>/dev/null | head -5
ls -t "$REPO/docs/superpowers/specs"/*-design.md 2>/dev/null | head -5
ls -t "$REPO/docs/superpowers/plans"/*.md 2>/dev/null | head -5
ls -t "$REPO/docs/superpowers/handoffs"/*-handoff.md 2>/dev/null | head -5
```

### 0-a. 주제 확정이 먼저다

**mtime 순서만 보고 최신 파일을 채택하지 않는다.** 이 목록에는 다른 주제의
산출물이 섞여 있다. 저장소 하나에 여러 주제의 파이프라인이 누적되므로, 최신
파일이 지금 하려는 주제라는 보장이 없다. 그걸 그대로 브릿지에 넘기면 엉뚱한
주제의 파이프라인이 돌아간다.

따라서 사용자에게 **어떤 주제를 이어서 할지** 먼저 AskUserQuestion으로 묻고,
고른 산출물의 파일명/제목에서 `TOPIC_SLUG`와 날짜를 확정한다. 새 주제면
Stage 1로 간다. 확정한 뒤 나머지 아티팩트는 그 슬러그로 좁혀 다시 찾는다.

```bash
REPO=$(git rev-parse --show-toplevel)
ls -t "$REPO/docs/superpowers/designs"/*-<TOPIC_SLUG>-grill.md 2>/dev/null | head -1
ls -t "$REPO/docs/superpowers/specs"/*-<TOPIC_SLUG>-design.md 2>/dev/null | head -1
ls -t "$REPO/docs/superpowers/plans"/*-<TOPIC_SLUG>.md 2>/dev/null | head -1
ls -t "$REPO/docs/superpowers/handoffs"/*-<TOPIC_SLUG>-handoff.md 2>/dev/null | head -1
```

슬러그로 좁혀 아무것도 안 나오면 그 단계는 미완이다. 넓은 목록의 파일을
"비슷해 보이니까" 끌어오지 않는다.

### 0-b. 진입 지점 판정

| 슬러그로 확인된 최신 아티팩트 | 진입 |
|---|---|
| 없음 | Stage 1 |
| 설계문서만 | Stage 2 |
| spec까지 | Stage 3 |
| plan까지 | Stage 4 |
| handoff까지 | 완료 상태 — 새로 시작할지 묻는다 |

아티팩트가 있으면 AskUserQuestion으로 경로를 보여주고
"여기서 이어서 / 처음부터"를 묻는다. 임의로 판단하지 않는다.

진입 전에 `DESIGN_DOC` / `SPEC` / `PLAN` / `TOPIC_SLUG` / `TOPIC_TITLE`을 위 목록에서
확정해 둔다 — 경로는 절대경로 리터럴로. 이후 단계는 이 값들을 그대로 쓴다.
재개는 Stage 1을 건너뛰므로 `TOPIC_TITLE`(→ handoff의 `{{TOPIC}}`)이 비어 있게 되기 쉽다.
발견한 spec이나 설계문서의 H1에서 사람이 읽는 제목을 여기서 뽑아 둔다.

`FILLED:`는 Stage 2 브릿지의 반환값이므로 **여기서 확정할 수 없다.** Stage 3이나
Stage 4로 재개 진입하면 브릿지가 돌지 않아 값이 존재하지 않는다. 그 경우
`FILLED:`를 `해당 없음(브릿지 미실행)`으로 고정해 두고 Stage 4 보고에 그대로 적는다.
비어 있는 채로 두거나 spec을 보고 지어내지 않는다 — 이 항목은 "브릿지가 지어낸
구간"을 가리키는 것이라, 추정으로 채우면 정확히 반대 의미가 된다.

### 0-c. 재개 진입 시 상류 게이트를 반드시 통과시킨다

GATE 1/2/3은 각각 그 산출물을 **만드는** 단계 안에 있다. 그래서 재개는 자기
게이트의 하류로 들어오고, 검증되지 않은 입력이 다음 소비자에게 그대로 넘어간다.
Stage 1을 건너뛰면 GATE1이, Stage 2를 건너뛰면 GATE2가 통째로 생략된다.
이를 막기 위해 **진입 직전에 이미 존재하는 아티팩트의 게이트를 직접 돌린다.**

| 진입 | 진입 전에 돌릴 게이트 |
|---|---|
| Stage 2 | `gate.sh 1 "$DESIGN_DOC"` |
| Stage 3 | `gate.sh 2 "$SPEC"` |
| Stage 4 | `gate.sh 3 "$PLAN"` |

```bash
bash ~/.claude/skills/auto-code/scripts/gate.sh <게이트번호> "<아티팩트 절대경로>"
```

실패하면 진입하지 않는다. 실패 사유를 그대로 보여주되, **처리는 그 게이트를
소유한 단계의 실패 분기를 그대로 따른다.** 여기에 별도 정책을 두지 않는다 —
같은 아티팩트의 같은 실패가 진입 경로에 따라 다르게 처리되면 안 된다.

| 실패한 게이트 | 따를 분기 |
|---|---|
| GATE1 | Stage 1-b의 "실패 시" 목록 (`Status: APPROVED 아님` → 승인 재요청 / 필수 섹션 누락 → 어댑터가 직접 보강) |
| GATE2 | Stage 2의 원인별 분기 (`[추론]` 잔존 → 해소 후 재게이트 / 블록 결함 → 브릿지 1회 재디스패치) |
| GATE3 | Stage 3의 "실패 시" 목록 (`파일 없음` → 경로 재조립 / 헤더 누락 → 직접 Edit 보강 후 보고 / `### Task N:` 부재 → 중단·보고) |

**grilling 재실행은 어떤 경우에도 선택지에 넣지 않는다.** GATE1 실패는
"문답을 다시 하라"는 뜻이 아니다 — 설계문서는 이미 파일로 있고, 승인 미완료면
승인만 다시 받으면 되며, 섹션 누락은 어댑터가 그 문서를 Edit해 메운다.
불변 규칙("설계 문답을 두 번 시키지 않는다")과 Stage 1의 "재시도하지 않는다"
규칙이 여기에도 똑같이 적용된다.

분기가 사용자 선택을 요구하면 AskUserQuestion으로 묻는다. 어느 경우에도 임의로
통과시키거나 검증되지 않은 아티팩트를 하류로 밀지 않는다.

이 사전 게이트는 해당 단계의 재시도 예산과 무관하다 — 재개 검증이지
재디스패치가 아니다.

## Stage 1 — grilling + domain-modeling, 그리고 설계문서 어댑터

이 단계는 두 부분이다. 1-a는 문답이고, 1-b는 그 결과를 파일로 굳히는 어댑터다.
**1-b를 건너뛰면 파이프라인이 끊긴다** — 아래 "왜 어댑터가 필요한가" 참조.

### 1-a. 문답

Skill 도구로 `mattpocock-skills:grilling`을 호출한다. 사용자와 grilling 사이에
끼어들지 않는다.

이어서 Skill 도구로 `mattpocock-skills:domain-modeling`을 호출한다. 이 둘의 조합이
mattpocock의 `grill-with-docs`가 하는 일 전부다(그 스킬 본문은 "Skill 도구를
grilling과 domain-modeling에 대해 두 번 불러라" 한 줄이다). `grill-with-docs`와
`grill-me`는 `disable-model-invocation: true`라 Skill 도구로 도달할 수 없으므로
실체인 두 스킬을 직접 부른다.

두 스킬은 `mattpocock-skills` **플러그인**이 제공한다(`~/.claude/skills/` 아래에
사본을 두지 않는다 — 중복되면 플러그인 업데이트와 갈라진다). 플러그인 스킬은
`plugin:skill` 형태로 부른다. 세션의 스킬 목록에 이 이름이 안 보이면 플러그인이
비활성 상태이므로, 문답을 흉내내지 말고 **중단하고** 사용자에게 알린다:

> `mattpocock-skills` 플러그인이 활성화돼 있지 않습니다.
> `/plugin`으로 설치·활성화한 뒤 `/auto-code`를 다시 불러주세요.

`grilling`은 설계트리의 프론티어를 라운드 단위로 질문하고, 프론티어가 비면
끝난다. **`grilling`은 파일을 하나도 쓰지 않는다.** 산출물은 대화 그 자체다.
`domain-modeling`은 그 과정에서 `CONTEXT.md`(용어집)와 `docs/adr/NNNN-*.md`를
남길 수 있다 — 남길 수도, 안 남길 수도 있다. ADR은 세 조건(되돌리기 어려움 +
의외성 + 실제 트레이드오프)을 모두 만족할 때만 쓰이므로 0건이 정상일 수 있다.

문답이 끝나면 `TOPIC_TITLE`과 `TOPIC_SLUG`를 확정한다. grilling은 제목을 정해
주지 않으므로, 대화에서 드러난 주제로 오케스트레이터가 제안하고 사용자에게
AskUserQuestion으로 확인받는다.

| 값 | 형태 | 쓰이는 곳 |
|---|---|---|
| `TOPIC_TITLE` | 사람이 읽는 제목 그대로 (예: `실시간 로그 수집기`) | handoff의 `{{TOPIC}}`, 사용자 보고 |
| `TOPIC_SLUG` | 제목을 kebab-case로 변환 (예: `realtime-log-collector`) | 파일명, 커밋 메시지, 브릿지 프롬프트 |

두 값은 확정한 뒤 모든 단계에서 같은 문자열을 재사용한다. **섞어 쓰지 않는다** —
`{{TOPIC}}`에 슬러그를 넣으면 handoff 문서의 H1이 kebab-case로 렌더된다.

### 1-b. 어댑터 — 설계문서를 쓴다

#### 왜 어댑터가 필요한가

Stage 2의 `spec-bridge`는 **서브에이전트**다. 별도 컨텍스트에서 돌기 때문에
grilling 대화를 볼 수 없고, 받는 것은 문서 경로 하나뿐이다. 대화를 파일로
굳히지 않으면 브릿지에 넘길 입력이 존재하지 않는다. 브릿지 계약이 요구하는
근거 표기 `[출처: 설계문서 §<섹션>]`도 참조할 문서가 있어야 성립한다.

그러므로 오케스트레이터가 **직접** 다음 문서를 Write한다. 이 일을
서브에이전트에 위임하지 않는다 — 위임하면 같은 문제가 한 겹 뒤로 밀릴 뿐이다.

#### 스키마

경로: `<repo>/docs/superpowers/designs/<TODAY>-<TOPIC_SLUG>-grill.md`

```
# Design: <TOPIC_TITLE>

**Date:** YYYY-MM-DD
**Status:** APPROVED
**Source:** grilling session (auto-code Stage 1)

## Problem Statement
## Constraints
## Approaches Considered
## Recommended Approach
## Success Criteria
## Open Questions
## Domain Notes
```

`Status:` 줄은 처음에 `DRAFT`로 쓴다. 사용자 승인 뒤에만 `APPROVED`로 고친다.
GATE1이 `^Status: APPROVED`를 요구하므로, 승인 없이 APPROVED로 쓰면 게이트가
승인 확인 장치로서 무의미해진다.

각 섹션에 무엇을 넣는지:

| 섹션 | 출처 | 규칙 |
|---|---|---|
| Problem Statement | grilling 1라운드에서 확정된 문제 정의 | 사용자가 답한 내용만. 문제를 새로 정의하지 않는다 |
| Constraints | 문답에서 사용자가 못박은 제약 + `docs/adr/`의 "constraints not visible in code" 항목 | 한 줄에 하나. 산문으로 뭉치지 않는다 |
| Approaches Considered | 문답에서 검토하고 **탈락시킨** 선택지 + 관련 ADR의 Considered Options | 왜 탈락했는지 한 줄 붙인다 |
| Recommended Approach | 문답에서 채택된 방향 | 브릿지가 Architecture의 시드로 쓴다 |
| Success Criteria | 문답에서 합의된 완료 조건 | 검증 가능한 형태로. 없으면 사용자에게 묻는다 |
| Open Questions | 프론티어가 비기 전에 "나중에"로 미뤄진 항목 | 없으면 `없음`이라고 쓴다 |
| Domain Notes | `CONTEXT.md`와 `docs/adr/NNNN-*.md`의 **경로 목록** | 내용을 복사하지 않는다. 브릿지가 경로를 따라가 읽는다 |

#### 철칙

- **대화에 없는 것을 쓰지 않는다.** 이 문서는 회의록이지 설계가 아니다.
  어댑터가 설계를 보태면 브릿지의 `[추론]` 승격 장치를 우회하게 된다.
- 필수 섹션(`Problem Statement` / `Constraints` / `Recommended Approach` /
  `Success Criteria`)에 넣을 내용이 대화에 없으면 **지어내지 말고
  AskUserQuestion으로 사용자에게 묻는다.** GATE1이 이 넷을 요구한다.
- `Domain Notes`는 경로만 적는다. ADR이 0건이면 `ADR 없음`이라고 쓴다.

#### 승인

문서를 쓴 뒤 경로를 보여주고 AskUserQuestion으로 승인을 받는다:

> 설계문서를 `<경로>`에 정리했습니다. 이대로 spec 변환에 넘길까요?
> A) 승인 — 다음 단계로  B) 고칠 곳이 있다 (무엇을 고칠지 말해주세요)

B면 지시받은 대로 Edit하고 다시 묻는다. **이 왕복은 재시도 예산에 넣지 않는다** —
문답 재실행이 아니라 문서 교정이다. A면 `Status:` 줄을 `APPROVED`로 고친다.

#### 게이트

```bash
bash ~/.claude/skills/auto-code/scripts/gate.sh 1 "$DESIGN_DOC"
```

실패 시:
- `Status: APPROVED 아님` → 승인 단계를 건너뛰었거나 Edit이 누락됐다.
  승인을 받고 `Status:` 줄을 고친 뒤 게이트를 다시 부른다.
  **문답을 다시 시키지 않는다.**
- 필수 섹션 누락 → 어댑터가 그 섹션을 직접 Edit로 채운다. 대화에 근거가
  없으면 AskUserQuestion으로 묻는다. 채운 뒤 게이트를 다시 부른다.

두 경우 다 정상 복구 경로이므로 재시도 횟수에 포함하지 않는다.

```bash
cd "$(git rev-parse --show-toplevel)" && git add docs/superpowers/designs/ CONTEXT.md docs/adr/ 2>/dev/null; git commit -m "docs: <topic> 설계문서 (auto-code grilling)"
```

`CONTEXT.md`와 `docs/adr/`는 domain-modeling이 만들었을 때만 존재한다.
없으면 `git add`가 조용히 넘어가도록 위 형태를 그대로 쓴다.

## Stage 2 — spec-bridge

Agent 도구로 `spec-bridge`를 **동기 디스패치**한다 — `run_in_background: false`.

이 하네스의 서브에이전트는 기본이 백그라운드다. 기본값으로 띄우면 오케스트레이터가
브릿지 반환을 기다리지 않고 그대로 진행해, 아직 존재하지 않는 spec에 대고
`gate.sh 2`를 불러 `GATE2 FAIL: 파일 없음`을 맞는다. 이 단계에 그 실패 분기는
없다. **브릿지가 반환하기 전에는 다음 줄로 넘어가지 않는다.** 반환값(`SPEC_PATH`,
`FILLED`, `OPEN_QUESTIONS`)을 손에 쥔 뒤에야 게이트를 부른다.

프롬프트에 다음 4개만 넣는다:

```
DESIGN_DOC: <절대경로>
REPO_ROOT: <절대경로>
TOPIC_SLUG: <kebab-case>
TODAY: <YYYY-MM-DD>

~/.claude/skills/auto-code/references/bridge-contract.md 의 계약을 따라
spec을 작성하고 계약의 반환 형식대로 반환해라.
```

grilling 대화 내용을 프롬프트에 붙여넣지 않는다. 문서 경로만 준다.

반환의 `SPEC_PATH`가 `BLOCKED`이면 하네스가 서브에이전트 Write를 막은 것이다.
반환된 본문을 오케스트레이터가 직접 Write한다. 쓸 경로는 브릿지가 쓰려던 것과
동일해야 한다:

```
<repo-root>/docs/superpowers/specs/<TODAY>-<TOPIC_SLUG>-design.md
```

정상 반환이면 `SPEC_PATH` 값을 그대로 SPEC으로 기록해 이후 모든 명령에
절대경로 리터럴로 적어 넣는다. 어느 경로든 `FILLED:` 값은 Stage 4 보고에
쓰이므로 함께 보관한다.

**OPEN_QUESTIONS 처리 — 게이트를 부르기 전에, spec을 쓴 직후 즉시 진행한다.**
bridge-contract.md에 따라 브릿지는 미확정 항목에 `[추론]` 태그를 남긴 채
반환한다. 이 태그가 남아 있으면 gate.sh 2는 설계상 반드시 실패하므로, 게이트를
부르기 전에 먼저 해소해야 재시도 예산을 낭비하지 않는다. AskUserQuestion으로
최대 6개까지 묻는다 — 이 도구는 한 호출에 담을 수 있는 질문 수에 상한이 있으므로
**필요하면 2회로 나눠 묻는다.** 7개 이상이면 상위 6개만 묻고 나머지는 spec의
`## Open Questions`로 이월한 뒤 **이월했다고 명시한다.** 답변을 spec에 Edit로
반영해 `[추론]` 태그를 없앤다.

```bash
bash ~/.claude/skills/auto-code/scripts/gate.sh 2 "$SPEC"
```

실패 시 원인별로 분기한다:
- 미해소 `[추론]` 태그 때문에 실패 → 위 OPEN_QUESTIONS 처리가 빠졌거나
  불완전했다는 뜻이다. 그 단계로 돌아가 마저 해소한 뒤 게이트를 다시 부른다.
  이는 정상 흐름이므로 **재시도 횟수에 포함하지 않는다.**
- 블록 누락·본문 비어있음 등 브릿지가 채워야 할 결함 때문에 실패 → 빈 블록
  이름을 명시해 브릿지를 1회 재디스패치한다. 이것이 이 단계의 재시도 1회다.
  재디스패치 후에도 같은 이유로 또 실패하면(총 2회째) 자동 재디스패치를
  STOP하고, 오케스트레이터가 사용자에게 직접 물어 채우는 수동 복구로 전환한다.

```bash
cd "$(git rev-parse --show-toplevel)" && git add docs/superpowers/specs/ && git commit -m "docs: <topic> spec (auto-code bridge)"
```

## Stage 3 — writing-plans

먼저 모델 체급을 확인한다. 스킬이 세션 모델을 조회할 API는 없으므로,
**오케스트레이터가 자기 컨텍스트의 모델 ID를 자가 보고해 비교한다.**
Opus급이 아니면 AskUserQuestion으로 알린다:

> 지금 세션 모델은 <모델>입니다. plan 작성은 아키텍처 판단이라 Opus급을 권장합니다.
> A) /model로 올리고 다시 부르기  B) 이대로 진행

강제하지 않는다. 사용자가 B를 고르면 그대로 진행한다.

Skill 도구로 `superpowers:writing-plans`를 호출하며 브릿지 spec 경로를 넘긴다.
writing-plans의 Execution Handoff 질문(Subagent-Driven / Inline 선택)이 나오면
**답하지 않고 Stage 4로 넘어간다.** 실행 방식은 handoff 파일이 지정한다.

**writing-plans는 절대경로를 내지 않는다.** 완료 문구는
``Plan complete and saved to `docs/superpowers/plans/<filename>.md`.`` 형태로
**저장소 상대경로**다. 그대로 게이트에 넘기면 cwd가 저장소 루트가 아닐 때
`GATE3 FAIL: 파일 없음`이 난다. 상대경로를 받아 저장소 루트를 앞에 붙여
PLAN을 만든다.

```bash
cd "$(git rev-parse --show-toplevel)" && R=$(git rev-parse --show-toplevel) && \
  if [ -f "docs/superpowers/plans/<filename>.md" ]; then echo "PLAN=$R/docs/superpowers/plans/<filename>.md"; else echo "PLAN_UNRESOLVED"; ls -t "$R/docs/superpowers/plans"/*.md 2>/dev/null | head -3; fi
```

출력된 절대경로를 PLAN으로 기록한다. writing-plans가 예외적으로 절대경로를
냈다면(`/`로 시작) 앞에 붙이지 말고 그대로 쓴다.

**`PLAN=` 줄을 손에 쥐기 전에는 게이트를 부르지 않는다.** `PLAN_UNRESOLVED`가
나왔다면 아래 "경로 미해결" 분기로 곧장 간다 — 빈 값을 게이트에 넘기면
`gate.sh 3 ""`가 되어 `usage()` 종료코드 2와 사용법 문구가 나오지,
`파일 없음` 문구가 나오지 않는다.

```bash
bash ~/.claude/skills/auto-code/scripts/gate.sh 3 "$PLAN"
```

실패 시. **문구가 아니라 조건으로 분기한다** — 종료코드 2(사용법 오류)와
`GATE3 FAIL: 파일 없음`은 문구가 다르지만 원인이 같다:

- **경로 미해결** — 위 블록이 `PLAN_UNRESOLVED`를 냈거나, 게이트가 종료코드 2를
  냈거나(= PLAN이 비었다), `파일 없음`으로 실패했다. 셋 다 게이트가 아니라
  **경로 조립이 틀린 것**이고 plan은 멀쩡히 존재할 수 있다. 위 블록이 함께 출력한
  실제 파일 목록에서 파일명을 바로잡아 절대경로를 다시 만든 뒤 게이트를 다시 부른다.
  **이는 재시도 횟수에 포함하지 않는다** — plan 품질 문제가 아니라 경로 문제다.
  목록도 비어 있으면 writing-plans가 저장에 실패한 것이므로 중단하고 보고한다.
- 헤더 수준 누락(`## Global Constraints` 등) → 오케스트레이터가 plan을 직접 Edit로
  보강하고 **무엇을 보강했는지 사용자에게 보고**한다.
- `### Task N:` 자체가 없음 → 재작성 사안이므로 중단하고 보고한다.

```bash
cd "$(git rev-parse --show-toplevel)" && git add docs/superpowers/plans/ && git commit -m "docs: <topic> implementation plan"
```

## Stage 4 — handoff

`~/.claude/skills/auto-code/references/handoff-template.md`를 읽고 치환한다.

| 자리표시자 | 값 |
|---|---|
| `{{TOPIC}}` | `TOPIC_TITLE` — 사람이 읽는 제목. **슬러그를 넣지 않는다** (H1이 kebab-case로 렌더된다) |
| `{{DATE}}` | 오늘 날짜 YYYY-MM-DD |
| `{{PLAN_PATH}}` | plan 절대경로 |
| `{{SPEC_PATH}}` | spec 절대경로 |
| `{{DESIGN_DOC}}` | 설계문서 절대경로 |
| `{{GLOBAL_CONSTRAINTS}}` | plan의 `## Global Constraints` 본문 그대로 |
| `{{OPEN_RISKS}}` | spec의 `## Open Questions` 잔여 항목 + 게이트 보강 내역 |

`<repo>/docs/superpowers/handoffs/YYYY-MM-DD-<TOPIC_SLUG>-handoff.md`에 쓴다
(파일명은 슬러그, 본문 H1은 `TOPIC_TITLE`).

쓴 파일에 `{{`가 하나도 남아 있지 않은지 확인한다 — 남아 있으면 치환 누락이므로
커밋 전에 바로잡는다.

```bash
cd "$(git rev-parse --show-toplevel)" && git add docs/superpowers/handoffs/ && git commit -m "docs: <topic> 구현 hand-off"
```

마지막으로 아래를 요약해 보고하고 종료한다. SDD를 호출하지 않는다.

- 산출물 3개 경로 (spec / plan / handoff)와 통과한 게이트
- **브릿지가 새로 채운 섹션** — Stage 2 반환의 `FILLED:` 값을 그대로 나열한다.
  이 목록은 "설계문서에 없던 내용을 브릿지가 지어낸 구간"이라는 뜻이므로,
  사용자가 구현 전에 우선 검토할 곳을 가리킨다. 삼켜서는 안 되는 정보다.
  Stage 3/4로 재개 진입해 브릿지가 돌지 않았으면 `FILLED:`는 존재하지 않는다.
  0-b가 정한 대로 **`해당 없음(브릿지 미실행)`이라고 적는다** — 생략하거나
  spec을 보고 추정해 채우지 않는다.
- 이월된 Open Questions와 게이트 보강 내역 (handoff의 `{{OPEN_RISKS}}`와 동일)

## 자체 검증

```bash
for t in ~/.claude/skills/auto-code/tests/*.sh; do bash "$t"; done
```

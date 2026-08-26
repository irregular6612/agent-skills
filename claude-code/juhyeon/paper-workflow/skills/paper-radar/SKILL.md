---
name: paper-radar
description: >-
  개인 관심 트랙 기반 논문 발굴·선별 레이더. 반복 실행(daily/weekly)해 여러 트랙에서 후보를 모으고, 이전 radar state와 기존 Wiki에 대해 중복 제거한 뒤 학습 가치로 랭킹해 비공개 digest를 남긴다. TRIGGERS - 오늘의 논문, 논문 레이더, paper radar, 새 논문 추천해줘, 이번 주 뭐 나왔어, 관심 분야 논문 훑어줘, mech interp 새 논문, lab watch, Anthropic 새 논문, 논문 뭐 읽을지 골라줘, radar 피드백, 3 드릴.  논문 1편의 근거추적 프리리드 노트는 /paper-driller.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - WebSearch
  - WebFetch
  - mcp__mcpsemanticscholar__paper-search-advanced
  - mcp__mcpsemanticscholar__search-paper-title
  - mcp__mcpsemanticscholar__get-paper-abstract
  - mcp__paper-search-mcp-openai-v2__search_arxiv
  - mcp__paper-search-mcp-openai-v2__search_semantic
  - mcp__paper-search-mcp-openai-v2__search_google_scholar
---

# Paper Radar — 개인 논문 레이더

## 스킬 경계 (먼저 읽는다)

세 스킬은 역할이 다르다. 라우팅을 혼동하지 않는다.

| 스킬 | 입력 | 산출물 | 성격 |
|---|---|---|---|
| **`paper-radar`** (이 스킬) | 관심 프로파일 + 날짜 | `_wiki/radar/daily/YYYY-MM-DD.md` **비공개** digest, 카드 6–8장 | 반복 실행, 다중 트랙 추천·선별. abstract/metadata 수준 카드 |
| `/paper-driller` | 선택된 논문 1편 | `Public/.../{제목}.md` canonical preread 노트 | 근거 추적 가능한 정식 노트 |

**`paper-radar`는 canonical paper 노트를 만들지 않는다.** 읽기로 결정된 논문은 반드시 `/paper-driller`로 넘긴다. `paper-radar`가 `Public/` 아래에 파일을 쓰는 경우는 없다.

## 무엇을 하는가

1. 관심 트랙별로 후보 논문을 모은다 (frontier / curriculum / graph 3개 pool).
2. 이전 radar state와 기존 Wiki에 대해 중복을 제거한다.
3. 학습 가치 기준으로 랭킹한다 (freshness 단독 지배 금지).
4. 비공개 daily digest에 카드 6장(기본, 최대 8장)을 쓴다.
5. 사용자 피드백(`드릴 / 공부 / 보류 / 제외`)을 받아 state·feedback에 반영하고 다음 스킬로 handoff한다.

## 호출 형태

```text
/paper-radar                      # daily, 오늘 날짜
/paper-radar --mode weekly        # 주간 롤업
/paper-radar --date 2026-08-01    # 특정 날짜 digest (재생성 아님, 없을 때만 생성)
/paper-radar --tracks mech-interp,alt-arch
/paper-radar --n 8                # 카드 수 (최대 8)
/paper-radar --init               # radar 상태 파일 초기화만 수행
/paper-radar --dry-run            # 파일 쓰기 없이 카드 후보만 보고
/paper-radar 3 드릴                # 직전 digest의 3번 카드에 대한 후속 액션
```

`--n`의 hard limit은 8이다. 9 이상 요청받으면 8로 잘라내고 잘랐다는 사실을 보고한다.

## vault_root 해결 순서

1. 사용자가 명시한 경로
2. 환경변수 `PAPER_RADAR_VAULT`
3. 알려진 현재 vault: `/Users/bagjuhyeon/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes`
4. CWD에 `_wiki/SCHEMA.md`와 `Public/`이 **둘 다** 있으면 CWD
5. 위 어느 것도 성립하지 않으면 사용자에게 묻는다 (추측해서 쓰지 않는다)

결정한 vault_root와 그 판정 근거(몇 번 규칙인지)를 보고에 남긴다.

## 상태 파일 (전부 vault_root 상대 경로, 전부 비공개)

```text
_wiki/radar/config.yaml            # 관심 프로파일 (사용자가 직접 편집)
_wiki/radar/state.json             # 본 후보 · 추천 이력 · 액션 결과
_wiki/radar/feedback.yaml          # 좋아함/싫어함 학습 신호
_wiki/radar/daily/YYYY-MM-DD.md    # 일일 digest
_wiki/radar/weekly/YYYY-Www.md     # 주간 롤업
```

`_wiki/`는 vault의 **비공개 운영 계층**이며 `Public/` 밖이라 블로그로 게시되지 않고 `build_catalog.py`/`lint.py`의 노트 스캔 대상도 아니다 (`wikilib` SKIP 목록에 `_wiki` 포함). 따라서 radar 파일에는 `type: paper` 같은 canonical 노트 계약을 붙이지 않는다. `_wiki/SCHEMA.md`와 `Public/WIKI-GUIDE.md`가 이 vault의 정본이며, 일반적인 llm-wiki 폴더 관례가 이를 덮어쓰지 않는다.

---

# Phase 0 — 초기화 · 설정 로드

1. vault_root를 위 순서대로 결정한다.
2. `_wiki/radar/`가 없으면 디렉터리와 `config.yaml`·`state.json`·`feedback.yaml`을 생성한다. `config.yaml`은 `references/interest-profile-template.yaml`을 그대로 복사한다.
3. `config.yaml`을 읽어 활성 트랙·가중치·lab watch 목록·차단어를 로드한다.
4. `state.json`, `feedback.yaml`을 읽는다. 파싱 실패 시 덮어쓰지 말고 사용자에게 보고한 뒤 중단한다.

**초기화 시 `Public/` 아래 어떤 파일도 만들거나 수정하지 않는다.**

완료 기준:
- [ ] vault_root와 판정 근거가 확정됐다
- [ ] 5개 상태 경로가 존재하거나(digest는 이번 실행에서 생성 예정) 생성됐다
- [ ] `config.yaml`의 활성 트랙 목록을 나열할 수 있다
- [ ] `Public/` 하위 변경 0건

## 기본 관심 프로파일

`config.yaml`의 초기값은 `references/interest-profile-template.yaml`에 있다. 트랙은 6개다.

| track id | 범위 |
|---|---|
| `transformer-mech` | attention, MLP/FFN, residual stream, normalization, positional representation, KV cache, in-context learning, induction heads |
| `alt-theory` | associative memory / modern Hopfield, energy-based view, dynamical systems·fixed points, optimization view, kernel view, Bayesian / information-theoretic / program-execution view |
| `brain-analogy` | predictive coding, working memory, associative·episodic memory, cortical hierarchy, global workspace, brain-model alignment |
| `alt-arch` | SSM/Mamba, RWKV, Hyena, RetNet, linear·recurrent attention, looped·recurrent transformer, memory-augmented model, diffusion language model |
| `mech-interp` | SAE, dictionary learning, transcoder·crosscoder, ICA, superposition, feature splitting·absorption, logit·tuned·backward lens, activation·path patching, causal tracing, attribution graph, circuit, steering·persona vector, interpretability evaluation·failure mode |
| `lab-watch` | Anthropic, OpenAI, Meta FAIR, Google DeepMind (사용자가 편집 가능) |

`brain-analogy` 트랙에는 추가 규칙이 있다. 뇌 비유의 **깊이**를 카드에 반드시 기록한다.

```text
mapping_depth: metaphorical | mathematical | representational | functional | empirically-tested
```

`metaphorical`은 감점한다. 용어만 빌려온 표면적 생물학 비유는 카드로 올리지 않는다.

**미해결 seed:** `config.yaml`의 `unresolved_seeds`에 `J-Lens`가 들어 있다. 이 이름이 무엇을 가리키는지 확정하지 않는다. URL 또는 canonical name(논문 제목·저자·arXiv ID 중 하나)을 사용자가 제공하기 전에는 정확 추적 대상으로 삼지 않으며, 추측으로 매칭한 후보를 카드로 올리지 않는다. 매 실행 시 미해결 seed가 있다는 사실만 보고 말미에 1줄로 알린다.

---

# Phase 1 — 후보 수집

## 세 개의 pool

| pool | 목적 | 목표 비중 |
|---|---|---|
| `frontier` | 최근 논문 | 약 절반 |
| `curriculum` | 이해를 메우는 과거 논문 (classic, 교과서적 논문, 전제 논문) | 약 1/3 |
| `graph` | 사용자가 이미 고른 논문의 reference / citation / related work 확장 | 나머지 |

`graph` pool의 seed는 `state.json`의 `selected` 이력(액션이 `드릴` 또는 `공부`였던 항목)이다. seed가 없으면 이 pool은 비운다.

## source 우선순위

1. **공식 lab research/publication 페이지** — lab attribution의 1차 근거
2. **arXiv, OpenReview, Semantic Scholar 또는 설정된 paper-search MCP** — 식별자·초록·인용수
3. **2차 웹 소스(뉴스·블로그·소셜)** — 발견 hint로만 사용. **attribution 근거로 절대 쓰지 않는다.**

MCP 도구는 호출 시점에 실제 스키마를 확인한다. 사용 불가하면 그 사실을 보고하고 남은 소스로 진행한다. 도구가 없는데 있는 척하지 않는다.

## company affiliation 규칙

confidence를 다음 순서로만 부여한다.

| confidence | 근거 |
|---|---|
| `high` | 해당 lab의 공식 publication 페이지에 등재 |
| `medium` | 논문 본문/메타에 소속이 명시됨 |
| `low` | 2차 소스 언급뿐 |

- **제목 키워드만으로 lab을 추정하지 않는다.** ("Claude"가 제목에 있다고 Anthropic 논문이 아니다.)
- 근거를 못 찾으면 `affiliation: unverified`로 두고 카드에 그렇게 쓴다. 빈칸을 채우려고 지어내지 않는다.
- `attribution_source`에 실제로 확인한 URL 또는 "논문 메타"를 남긴다.

완료 기준:
- [ ] 활성 트랙마다 pool 라벨이 붙은 raw 후보가 1건 이상 수집됐다 (0건이면 그 사실을 기록)
- [ ] 모든 후보에 source URL이 있다
- [ ] lab-watch 후보마다 affiliation confidence와 attribution_source가 채워졌다
- [ ] 2차 소스만 근거인 항목은 `low` 또는 `unverified`로 표시됐다

---

# Phase 2 — 중복 제거

다음 순서로 정규화 키를 만든다.

1. `arXiv-ID` (버전 접미사 `v\d+` 제거, 소문자)
2. `DOI` (소문자, `https://doi.org/` prefix 제거)
3. 정규화 URL (scheme·`www.`·query string·trailing slash 제거)
4. 정규화 제목 (소문자, 구두점 제거, 공백 1칸 정규화)

이 키로 두 곳을 조회한다.

- **이전 radar state**: `state.json`의 `seen` 맵
- **기존 Wiki**: `Public/**/*.md`의 frontmatter `arXiv-ID` / `DOI` / `URL`, 그리고 파일명·제목. `_wiki/catalog/*.md`를 먼저 훑으면 전체 스캔보다 싸다.

중복 판정 결과는 버리지 않고 라벨을 붙인다.

| relation | 의미 | 카드 처리 |
|---|---|---|
| `new` | 어디에도 없음 | 정상 추천 |
| `existing` | Wiki에 canonical 노트가 있음 | **신규 추천으로 세지 않는다.** 카드로 올리려면 "기존 노트 갱신" 목적으로만 |
| `update` | 같은 논문의 새 버전·확장판 | "기존 노트 갱신" 카드 |
| `follow-up` | 기존 노트의 후속·반박·재현 | 명시적으로 후속임을 밝히고 추천 가능 |
| `radar-seen` | 이전 digest에 이미 올렸고 액션 미결 | 재추천 대신 "미결 항목" 섹션에 한 줄로 |

`radar_id`는 실행 간 안정적이어야 하므로 위 정규화 키에서 결정론적으로 만든다.

```bash
printf '%s' "$canonical_key" | shasum -a 1 | cut -c1-8   # radar_id = "R-" + 이 8자리
```

같은 논문은 몇 번을 다시 만나도 같은 `radar_id`를 갖는다. digest 안에서 사용자가 부르는 번호(`3 드릴`의 `3`)는 그 digest 안에서만 유효한 카드 순번이며, `radar_id`와 함께 기록한다.

완료 기준:
- [ ] 모든 후보에 정규화 키와 `radar_id`가 있다
- [ ] 모든 후보에 relation 라벨이 붙었다
- [ ] `existing`/`radar-seen`이 신규 추천 슬롯을 차지하지 않았다
- [ ] Wiki 조회를 실제로 수행했다 (조회한 catalog/glob 경로를 보고에 남긴다)

---

# Phase 3 — 랭킹

8개 축으로 평가한다. 축 정의·0–5 anchor·가중치·tie-break는 **`references/ranking-rubric.md`**에 있다. 점수를 매기기 전에 그 파일을 읽는다.

| 축 | 한 줄 |
|---|---|
| interest fit | 활성 트랙과 얼마나 맞는가 |
| pedagogical value | 읽고 나면 이해가 실제로 늘어나는가 |
| novelty vs Wiki | 기존 노트가 이미 덮지 못한 부분인가 |
| evidence quality | 주장 대비 근거가 있는가 (초록 수준에서 판단 가능한 만큼만) |
| bridge value | 기존 노트 2개 이상을 연결해 주는가 |
| availability | 전문·코드·데이터에 접근 가능한가 |
| freshness | 최신성 |
| risk / overclaim | 과장·검증 불가 주장에 대한 **감점** |

**freshness는 단일 지배 요인이 될 수 없다.** rubric의 가중치 상한을 지키고, 상위 카드가 전부 최근 30일 논문이면 curriculum pool에서 최소 1장을 강제로 끌어올린다.

완료 기준:
- [ ] 최종 후보마다 8축 점수 또는 명시적 `n/a` 사유가 있다
- [ ] 총점 산식이 rubric과 일치한다
- [ ] freshness 상한 규칙을 위반하지 않았다
- [ ] 감점(risk) 항목이 실제로 적용됐다

---

# Phase 4 — 카드 구성

## 다양성 슬롯

기본 6장. 다음 6개 슬롯을 각각 최소 1장씩 채운다.

1. transformer mechanism / theory
2. alternative / hybrid architecture
3. mechanistic interpretability — representation 계열
4. mechanistic interpretability — causal / evaluation / control 계열
5. lab watch
6. **exploratory 슬롯** — Wiki gap, classic, rebuttal, wildcard 중 하나

`--n 7|8`이면 총점 상위에서 채운다. 슬롯을 채울 후보가 없으면 **빈칸으로 두고 왜 비었는지 쓴다.** 억지로 다른 트랙 논문을 끼워 넣지 않는다.

**6번 exploratory 슬롯은 어떤 경우에도 생략하지 않는다.** 개인화가 filter bubble로 붕괴하는 것을 막는 유일한 장치다. 피드백 학습이 이 슬롯의 후보를 걸러내지 못하게 한다.

## 카드 필수 필드

카드 markdown 형식은 **`references/daily-radar-template.md`**를 따른다. 필드는 다음과 같다.

```text
radar_id, title, authors, date/year, source_url,
arxiv_id|doi (있을 때), track, pool,
claim_one_line   — 출처 범위 안에서만 쓴 한 문장
why_you          — 이 사용자에게 추천하는 이유
learning_payoff  — 읽고 나면 무엇을 할 수 있게 되는가
wiki_relation    — new|existing|update|follow-up + 관련 노트 링크
coverage_warning — 근거 범위 경고 (기본값은 abstract-only)
affiliation + attribution_source + affiliation_confidence (해당 시)
mapping_depth    — brain-analogy 트랙일 때 필수
action           — drill | skim | park
```

## 지어내지 않기

- 초록만 봤으면 **초록만 본 것이다.** 방법 세부, 실험 설정, 수치, 비교 대상, ablation 결과를 추론해서 쓰지 않는다.
- 메타데이터(저자·연도·venue·식별자)를 기억으로 채우지 않는다. 조회 결과에 없으면 `N/A`.
- 원문 위치(Section/Table/Figure)는 실제로 확인한 경우에만 쓴다. radar 단계에서는 보통 확인 불가이므로 쓰지 않는 것이 기본이다.
- `claim_one_line`은 초록이 실제로 말한 것만 담는다. 초록의 주장은 저자의 주장이지 검증된 사실이 아니며, 카드에서 `저자 주장`으로 표시한다.

완료 기준:
- [ ] 카드 수가 6–8이고 `--n` 요청과 일치한다 (8 초과 요청은 잘라내고 보고)
- [ ] 6개 슬롯이 채워졌거나 빈 사유가 명시됐다
- [ ] exploratory 슬롯이 존재한다
- [ ] 모든 카드에 필수 필드가 있고 미상은 `N/A`다
- [ ] 모든 카드에 coverage 경고가 있다
- [ ] brain-analogy 카드에 `mapping_depth`가 있다

---

# Phase 5 — digest 쓰기

1. `_wiki/radar/daily/YYYY-MM-DD.md`를 `references/daily-radar-template.md` 형식으로 쓴다.
   - 이미 존재하면 덮어쓰지 않는다. 읽어서 `## 추가 (HH:MM)` 블록으로 append한다.
2. `--mode weekly`면 그 주의 daily digest들을 읽어 `_wiki/radar/weekly/YYYY-Www.md`로 롤업한다. 롤업은 새 후보를 발굴하지 않고 기존 카드의 액션 현황과 미결 항목만 정리한다.
3. `state.json`을 갱신한다: 이번에 본 `seen` 키, 이번 digest에 올린 `recommended`, 각 항목의 `first_seen` / `last_seen` / `times_shown`.
4. `--dry-run`이면 1–3을 수행하지 않고 카드 후보만 화면에 보고한다.

완료 기준:
- [ ] digest 파일 경로가 실제로 존재한다
- [ ] `state.json`이 유효한 JSON이고 이번 카드의 `radar_id`가 전부 들어 있다
- [ ] `Public/` 하위 변경 0건
- [ ] 기존 digest를 덮어쓰지 않았다

---

# Phase 6 — 피드백 · handoff

## 후속 명령

digest를 보고 사용자가 카드 번호로 지시한다.

| 입력 | 의미 |
|---|---|
| `3 드릴` | 3번 카드를 정식 노트로 만든다 |
| `3 공부` | 3번 카드를 튜터링 세션으로 공부한다 |
| `3 보류` | 지금은 아니지만 나중에 다시 보기 |
| `3 제외 — causal intervention 쪽이 더 궁금함` | 제외 + 이유 학습 |

이유가 붙은 `제외`는 `feedback.yaml`에 이유 문자열 그대로 기록한다. 이유를 요약·해석해서 왜곡하지 않는다.

## handoff 계약

기계 판독 handoff 페이로드의 스키마는 **`references/handoff-schema.yaml`**이다. 최소 필드:

```text
radar_id, arxiv_id, doi, source_url, title,
vault_root, candidate_rationale, selected_action
```

## 액션별 경로

```text
드릴  → /paper-driller <source_url 또는 arXiv-ID> --mode preread
        paper-radar는 canonical 노트를 직접 쓰지 않는다.
        driller가 끝나면 state.json에 노트 경로를 기록한다.

공부  → canonical preread 노트가 있는가?
          없음 → 먼저 /paper-driller ... --mode preread
          있음 → /paper-understand <노트 경로>
        radar 카드(초록 수준)를 전문 소스로 넘기지 않는다.

보류  → state.json의 항목 상태만 parked로. feedback.yaml에 약한 신호.
제외  → state.json에 excluded, feedback.yaml에 이유. 파일 생성 없음.
```

완료 기준:
- [ ] 액션이 `state.json`에 반영됐다
- [ ] `제외`의 이유가 `feedback.yaml`에 원문 그대로 있다
- [ ] `드릴`/`공부`는 handoff 스키마를 채워 다음 스킬을 호출했다 (또는 호출 명령을 사용자에게 제시했다)
- [ ] `보류`/`제외`는 어떤 노트 파일도 만들거나 고치지 않았다

---

# 안전 · 노이즈 제약

- **abstract-only는 abstract-only다.** 방법·결과 세부를 추론해 카드에 쓰지 않는다.
- **`Public/AI/Papers/`에 파일을 대량 생성하지 않는다.** radar는 그 폴더에 쓰지 않는다.
- **canonical 노트를 자동 수정하지 않는다.** `Reading-Status` 변경 포함, 사용자 확인 없이는 손대지 않는다.
- **freshness가 curriculum 가치를 지배하지 못하게 한다.**
- **exploratory 슬롯을 최소 1개 유지한다.**
- 메타데이터·주장·수치·원문 위치·소속을 지어내지 않는다. 모르면 `N/A` 또는 `unverified`.
- 같은 논문을 이유 없이 반복 추천하지 않는다. `times_shown ≥ 3`이고 액션이 없으면 자동으로 `parked`로 내린다.

## 이럴 때 멈춘다

| 상황 | 행동 |
|---|---|
| vault_root를 확정 못 함 | 사용자에게 묻는다. 추측 경로에 쓰지 않는다 |
| `state.json` 파싱 실패 | 보고하고 중단. 덮어쓰지 않는다 |
| 모든 검색 소스 실패 | 0건 보고. 기억으로 논문 목록을 만들지 않는다 |
| 슬롯을 채울 후보 없음 | 빈칸 + 사유. 트랙 밖 논문으로 채우지 않는다 |
| `J-Lens` 같은 미해결 seed | 추측 매칭 금지. URL/canonical name 요청 |

# References

- `references/ranking-rubric.md` — 8축 정의, 0–5 anchor, 가중치, tie-break, freshness 상한
- `references/daily-radar-template.md` — digest 파일 · 카드 markdown 형식
- `references/interest-profile-template.yaml` — `config.yaml` 초기값 (6트랙 + unresolved seeds)
- `references/handoff-schema.yaml` — `/paper-driller`·`/paper-understand` handoff 페이로드 계약
- `scripts/validate-radar.sh` — 스킬 파일 정적 계약 검증

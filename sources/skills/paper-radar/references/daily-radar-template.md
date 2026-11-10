# Paper Radar — Daily Digest Template

저장 위치: `{vault_root}/_wiki/radar/daily/YYYY-MM-DD.md` (비공개, `Public/` 밖)

`_wiki/`는 catalog·lint의 노트 스캔 대상이 아니다. 따라서 이 파일에 `type: paper` 등 canonical 노트 계약을 붙이지 않는다. 아래 frontmatter는 radar 전용이다.

---

## 1. 파일 전체 구조

````markdown
---
radar-kind: daily
radar-date: 2026-08-02
vault-root-rule: 3
tracks-active: [transformer-mech, alt-theory, brain-analogy, alt-arch, mech-interp, lab-watch]
cards: 6
pools: {frontier: 3, curriculum: 2, graph: 1}
sources-used: [semantic-scholar, arxiv, anthropic-research-page]
sources-failed: []
unresolved-seeds: [J-Lens]
---

# Radar — 2026-08-02

> [!warning] 근거 범위
> 이 digest의 카드는 **초록과 메타데이터 수준**이다. 방법·수치·실험 조건은 확인되지 않았다.
> 정식 노트는 `/paper-driller`, 학습 세션은 `/paper-understand`로 진행한다.

## 오늘의 카드

### 1. {제목}
...카드 블록 (아래 §2)...

### 2. {제목}
...

## 미결 항목

이전 digest에 올렸으나 액션이 없는 항목. 재추천 슬롯을 차지하지 않는다.

| # | radar_id | 제목 | 처음 본 날 | 노출 횟수 |
|---|---|---|---|---|
| — | R-a1b2c3d4 | ... | 2026-07-28 | 2 |

## 슬롯 현황

| 슬롯 | 채움 | 카드 |
|---|---|---|
| transformer mechanism/theory | ✅ | 1 |
| alternative/hybrid | ✅ | 2 |
| mech-interp — representation | ✅ | 3 |
| mech-interp — causal/eval/control | ✅ | 4 |
| lab watch | ✅ | 5 |
| exploratory (gap/classic/rebuttal/wildcard) | ✅ | 6 |

빈 슬롯이 있으면 `❌ — {사유}`로 적는다. 다른 트랙 논문으로 메우지 않는다.

## 다음 행동

```text
N 드릴   → /paper-driller ... --mode preread
N 공부   → preread 노트 확인 후 /paper-understand
N 보류   → state만 갱신
N 제외 — 이유
```

## 실행 메모

- 후보 수집: raw {R} → dedup {D} → 랭킹 대상 {K} → 카드 {N}
- 제외 사유별: Wiki 중복 {a}, radar 재노출 {b}, 트랙 무관 {c}, 초록 확보 실패 {d}
- 검색 실패 소스: {목록 또는 없음}
- 미해결 seed: `J-Lens` — URL 또는 canonical name이 필요하다
````

---

## 2. 카드 블록 형식

카드 1장은 아래 형식을 그대로 따른다. 값이 없는 필드는 지우지 말고 `N/A`로 남긴다.

````markdown
### {N}. {논문 제목 (원문 그대로)}

| 항목 | 값 |
|---|---|
| radar_id | `R-a1b2c3d4` |
| 저자 | First Author et al. (전체 저자 미확인 시 그대로 표기) |
| 연도/날짜 | 2026-07-30 |
| source URL | https://arxiv.org/abs/XXXX.XXXXX |
| arXiv-ID / DOI | 2607.01234 / N/A |
| track | `mech-interp` (+ `alt-theory`) |
| pool | `frontier` |
| Wiki 관계 | `new` — 연결 대상 없음 |
| 소속 | Anthropic · `high` · https://www.anthropic.com/research (공식 publication 페이지) |
| mapping_depth | N/A (brain-analogy 트랙일 때만 필수) |
| 추천 액션 | **drill** |
| 점수 | 78.4 (interest 5 / peda 4 / novelty 3 / evidence n/a / bridge 3 / avail 3 / fresh 5 / risk 1) |

**저자 주장 (초록 범위):** {초록이 실제로 말한 것 한 문장. 저자의 주장이지 검증된 사실이 아니다.}

**왜 당신에게:** {활성 트랙·기존 노트·최근 관심과의 연결을 근거로 한 이유}

**학습 payoff:** {읽고 나면 무엇을 새로 할 수 있게 되는가}

**근거 경고:** 초록만 확인. 방법·수치·실험 조건 미확인.
````

### 필드 규칙

| 필드 | 규칙 |
|---|---|
| `radar_id` | 정규화 키의 sha1 앞 8자리. 실행 간 안정적 |
| 제목 | 원문 그대로. 번역하지 않는다 |
| 저자 | 확인된 만큼만. 미확인이면 확인된 범위를 그대로 쓴다 |
| 연도/날짜 | 확인된 것만. 추정 금지 |
| source URL | 필수. 없으면 카드로 올리지 않는다 |
| arXiv-ID / DOI | 없으면 `N/A`. 형식을 지어내지 않는다 |
| Wiki 관계 | `new` / `existing` / `update` / `follow-up` 중 하나 + 관련 노트 `[[링크]]` |
| 소속 | `{lab} · {high\|medium\|low\|unverified} · {attribution_source}` |
| mapping_depth | `metaphorical` / `mathematical` / `representational` / `functional` / `empirically-tested` |
| 추천 액션 | `drill` / `skim` / `park` |
| 저자 주장 | 초록 범위 밖의 문장을 쓰지 않는다. `저자 주장` 레이블을 지우지 않는다 |
| 근거 경고 | 모든 카드에 필수. 전문을 확인했으면 그렇게 고쳐 쓴다 |

### 금지

- 초록에 없는 수치·비교 대상·ablation·데이터셋 규모를 쓰지 않는다.
- Section/Table/Figure 번호는 실제 확인했을 때만 쓴다. radar 단계 기본은 미기재다.
- 제목 키워드로 lab을 추정해 `소속`을 채우지 않는다.
- 카드 안에 "이 요약으로 논문을 다 파악했다"는 인상을 주는 문장을 쓰지 않는다.

---

## 3. 재실행 시 append 블록

같은 날 다시 실행하면 파일을 덮어쓰지 않고 아래를 append한다.

```markdown
## 추가 (HH:MM)

- 신규 카드: {번호는 기존 마지막 번호 + 1부터}
- 재노출 없음 / 있으면 사유
```

frontmatter의 `cards`와 `pools`는 누적 값으로 갱신한다.

---

## 4. Weekly 롤업

저장 위치: `{vault_root}/_wiki/radar/weekly/YYYY-Www.md`

```markdown
---
radar-kind: weekly
radar-week: 2026-W31
days-covered: [2026-07-27, ..., 2026-08-02]
---

# Radar Weekly — 2026-W31

## 액션 현황
| 액션 | 건수 | 항목 |
|---|---:|---|
| 드릴 | 2 | ... |
| 공부 | 1 | ... |
| 보류 | 3 | ... |
| 제외 | 4 | ... |

## 미결 (3회 이상 노출, 액션 없음)
...자동 park 대상...

## 트랙 편중
| track | 카드 수 | 선택 수 |
|---|---:|---:|

## 이번 주 관찰
- {피드백에서 드러난 관심 이동. 근거가 되는 제외 사유를 함께 인용한다}
```

**weekly는 새 후보를 발굴하지 않는다.** 그 주 daily digest들만 읽어 정리한다.

# 프로필 폴더 형식 — `profiles/<profile-name>/`

길이 상한은 `formats.md` 의 "길이 상한" 표가 기준이다. 검사: `python3 scripts/check_lengths.py --profile profiles/<이름>`
(길이 + 중간 파일 잔존 + 인용 원문 대조).

```
profiles/<profile-name>/
├── meta.yaml       ≤ 25줄   누구·무엇·언제
├── profile.md      ≤ 700단어 writer 가 매 라운드 읽는 지시 (anchor 포함)
├── evidence.md     ≤ 1,200단어 profile.md 각 항목의 근거 (인용·횟수). 재분석·감사용
├── sample.md       상한 없음  분석에 쓴 샘플 원문 (사용자가 직접 쓴 글, 글자 그대로)
└── counts.json     상한 없음  stage1_counts.py 출력 (writer self-check 의 --ref)
```
분석 중에만 `_work/` (run 파일, stage1.md) 가 생기고, 조립·검사가 끝나면 통째로 지운다.

이름 규칙: `<사람>-<언어>-<장르>` (예: `juhyeon-en-academic`). 같은 사람의 다른 장르는 다른 프로필로 둔다.

**인용 표기**: `백틱` 은 sample.md 원문 인용 전용이다 (오타·띄어쓰기 누락·곡선 따옴표까지 그대로). ID(L1-H01),
파일 이름, 옵션은 백틱에 넣지 않는다. anchor 는 `> ` 인용 블록. 검사 스크립트가 둘 다 원문과 대조한다.

## meta.yaml (≤ 25줄)

```yaml
profile_name: juhyeon-en-academic
owner: self                 # 스킬 사용자 본인. 본인 것만 만든다
default: true               # 언어·장르가 맞으면 먼저 제안
created: 2026-10-02
updated: 2026-10-02
sample:
  source: <원본 경로 또는 "붙여 넣기">
  genre: English academic homework
  language: en
  writer_l1: ko             # 사용자가 밝힌 것만
  words: 135                # stage1_counts.py 기준
  sentences: 14
  paragraphs: 1
  edited_or_ai_assisted: no # no / suspected / yes / unknown
  holdout: none             # 300단어 미만 → 검증 불가
analysis: "stage1 fable·astra·opus → 병합 fable / stage2 opus·astra → 조립 fable"
reliability: low            # low(<300w) / medium(300–800w) / high(>800w)
notes: "<한두 줄>"
```

## profile.md (≤ 700단어, 섹션별 대략 예산)

```markdown
# Voice profile — <name>
> 샘플 <N>단어, <장르>, 신뢰도 <..>. 양의 지시는 상한 이하로만. Never 가 가장 믿을 만함.   (~40)

## 1. Never (이 사람이 안 하는 것)                                                         (~110)
- 항목 — 한 구절 근거 (샘플 0회 / 계량값)

## 2. 습관 (등급 · 빈도 상한)                                                              (~170)
| id | 지시 | 등급 | 상한 |          ← H 우선, T 는 자리가 남으면. O 는 넣지 않는다

## 3. L2 흔적 정책 (slips=on 일 때)                                                        (~90)
- 재현 가능: 유형 — 상한 / 재현 금지: 유형들 / 공통: 정의·변수·수식 도입부 금지, 새 유형 금지

## 4. Persona (행동 서술 3–5줄, 근거 ID 붙임)                                             (~90)

## 5. Anchors (원문 그대로, 문체용 — 내용 재사용 금지)                                      (~120, 샘플에 따라)
- A1 (S1–S3, 39w): 담긴 trait ID 몇 개
> 원문

## 6. 장르 전이 · writer 함정 (각 2–3줄)                                                    (~60)

## 7. Self-check (stage1_counts.py --ref counts.json 허용 범위 한 줄)                        (~20)
```

## evidence.md (≤ 1,200단어)

```markdown
# Evidence — <name>
## 계량 요약 (counts.json 핵심 값)
## 항목별 근거 | profile id | 횟수/기회 | 인용 1–2개 | 지지 run |
## L2 흔적 표 | 유형 | 인용 | 기회 | 비율 | 조건 |
## Stage 2 판단 근거 (태그 시퀀스, move 매핑, H-01–H-07 한 줄씩, 갈린 판단은 "약함")
## 버린 것 (개수와 대표 사유 3줄)
```

## writer 에게 주는 방식 (Phase 2)
- `profile.md` 전체 (anchor 포함) + `sample.md`. evidence.md 는 주지 않는다 (writer 입력을 짧게 유지).
- 사용자가 직접 쓴 첫 문장이나 메모가 있으면 그것을 seed 로 쓴다 (사람이 쓴 텍스트로 시작시키기가 사람다움에 가장 크게 기여).
- 목표 장르가 프로필 장르와 다르면 §6 장르 전이를 따르고, 보고에 "장르 전이" 를 적는다.

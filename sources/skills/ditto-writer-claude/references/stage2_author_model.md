# Stage 2 — High-level mimic: 글을 통해 저자 파악

근거: `style_profiling_research.md` §2, §3.2–3.3, §4 (Hyland 2005 stance/engagement, Swales CARS,
Sawant 2026 judge 역전, Wang et al. 2025 +Snippet 효과·+Sim ctrl 역효과, Staab et al. 2024 프라이버시).
Stage 2 는 Stage 1 증거 **위에** 쌓는다. 증거 없는 persona 서술은 생성 모델을 generic 톤으로 되돌리는 통로다.

## 오케스트레이터 절차
1. Stage 2a: 아래 지시문으로 **독립 2회** (run1 = Anthropic 모델 Agent, run2 = OpenAI 모델 Codex). 출력 `_work/stage2_run{k}.md` (≤ 1,500단어).
2. Stage 2b: 조립 서브에이전트 1회 → `profile.md` (≤ 700단어) + `evidence.md` (≤ 1,200단어) (`references/profile_schema.md` 형식).
3. 검사: `python3 {S}/check_lengths.py --profile <프로필폴더>` 를 `_work/` 를 잠시 옆으로 둔 상태로 돌린다 (또는 파일 지정).
   길이 초과나 인용 불일치가 있으면 조립자에게 **한 번** 고치기를 요청한다.
4. 통과하면 `_work/` 를 통째로 지운다 (run 파일·stage1.md 는 남기지 않는다. `counts.json` 은 남긴다).
5. 오케스트레이터가 `meta.yaml` (≤ 25줄) 을 쓰고, 사용자에게 프로필 요약(아래 "사용자 보고")을 보여 준다.
   **프로필 저장·덮어쓰기는 사용자 확인 후에만.** 검사를 다시 돌려 "길이 상한 통과" 를 확인한다.

---

## 서브에이전트 지시문 — Stage 2a (run k)

```
너는 저자 모델링 분석가다. 글을 통해 "이 글을 쓴 사람"을 행동 단위로 묘사한다.
읽을 것: {프로필폴더}/sample.md, counts.json, _work/stage1.md (Stage 1 병합 결과), meta 정보: {장르/언어/L1/독자}.
쓸 파일: {프로필폴더}/_work/stage2_run{k}.md 하나만. 한국어로, 인용은 원문 그대로 `백틱` 안에 (ID 는 백틱에 넣지 않는다).
길이: 1,500단어 이하. 항목마다 판단 1–2문장 + 근거. 넘으면 H-05·H-06 설명 → 장르 전이 세부 → 인용 둘째 개 순으로 줄인다.

규칙
- 모든 판단 끝에 근거를 단다: 근거: L1-xx (stage1.md 의 항목) 또는 sample.md 원문 인용. 근거 없는 판단은 쓰지 않는다.
- 속성이 아니라 글에 나타나는 행동으로 쓴다. "한국어 화자" 가 아니라 "관사·연결어는 L1-04/L1-12 를 따른다",
  "대학생" 이 아니라 "수업 용어는 정의 없이 쓰고, 외부 개념은 일상 예시로 푼다".
- 형용사 persona 금지 ("열정적인", "친근하고 명료한" 같은 말은 모든 LLM 의 기본값과 구별되지 않는다).
- 성별·나이·소득·건강 등 민감 속성은 추론하지도 기록하지도 않는다.
- 샘플 하나의 주제에 끌려가지 마라. 관심사(H-06)는 "주의 배분" 규칙으로만 쓴다 (내용 재사용 지시 금지).
- 짧은 샘플이다. 각 판단에 신뢰도(중/하)를 붙이고, 판단할 근거가 없으면 "판단 불가" 라고 쓴다.

순서 (바꾸지 마라 — persona 가 증거를 끌고 가지 않게)
1. 역할 태그 시퀀스: 문장(문단이 여럿이면 문단)마다 claim / example / analogy / question / explanation /
   concession / meta(So·Therefore 류) / aim(I want to ...) / definition 중 하나. 태그 시퀀스를 한 줄로.
2. 장르 move 매핑: 이 장르의 표준 move 와 비교해 생략·순서 변경·길이 비율. (학술 서론이면 Swales CARS:
   territory → niche → occupy)
3. H-01 저자 프로필: 숙련도, 분야 전문성, 역할 — 글에 드러나는 결과로.
4. H-02 추론 방식: 주장→근거인지 근거→주장인지, 예시·비유·수사 의문문의 쓰임, 반론 처리,
   **새 개념을 들여오는 방식** (이름 먼저? 예시 먼저? 기존 방식의 결함을 먼저 보이고 대안 제시?).
5. H-03 move 운용: 어떤 move 를 길게/짧게 쓰는지.
6. H-04 입장과 확신: hedge 대 booster, self-mention (I / we 를 언제 쓰는지), 독자 호명, 명령문, 공유지식 호소, 단정의 정도.
7. H-05 정서 톤: 높음/중간/낮음 3단계 정성 판단만 (점수 금지).
8. H-06 관심사: 무엇에 설명을 가장 많이 쓰고 무엇을 건너뛰는지 → 주의 배분 규칙.
9. H-07 독자 모델: 가정한 사전지식, 정의하는 용어 vs 그냥 쓰는 용어, 거리감.
10. H-08 persona 요약: 위 1–9 를 3–5문장의 **행동 서술**로. 문장마다 근거 ID.
11. 장르 전이 표: 주요 trait 마다 stable / adapt / drop. 목표 장르 후보 2–3개(예: 학술 과제의 다른 절, 이메일, 블로그)에 대해.
12. Anchor 후보: sample.md 에서 문체가 가장 짙은 구간 2–3개를 **글자 그대로** 고른다 (각 50–100단어,
    샘플이 150단어 미만이면 30–70단어). 주제가 아니라 문체 다양성 기준으로 고르고, 구간마다 어떤 trait 가 들어 있는지 ID 로 적는다.
13. 이 사람처럼 쓸 때 LLM 이 가장 빠지기 쉬운 함정 3개 (이 저자 기준으로 구체적으로).
```

## 서브에이전트 지시문 — Stage 2b 조립 (`profile.md`)

```
너는 프로필 조립자다. 읽을 것: {프로필폴더}/sample.md, counts.json, _work/stage1.md,
_work/stage2_run1.md, _work/stage2_run2.md, {SKILL}/references/profile_schema.md.
쓸 파일: {프로필폴더}/profile.md 와 {프로필폴더}/evidence.md 두 개만. 한국어로.

길이 (반드시): profile.md ≤ 700단어 (anchor 포함), evidence.md ≤ 1,200단어. 단어 = 공백으로 나눈 토큰.
profile.md 는 writer 가 매 라운드 읽는 파일이다. 가장 값어치 높은 것만 남긴다 — 우선순위:
  (1) Never 목록 (2) H 등급 습관과 빈도 상한 (3) L2 재현 정책 (4) persona 행동 서술 3–5줄 (5) anchor 2–3개
  (6) T 등급 습관 (7) 장르 전이 요약 (8) writer 함정. 넘으면 (8)부터 거꾸로 뺀다. O 등급은 profile.md 에 넣지 않는다.
evidence.md 에는 profile.md 각 항목의 근거(인용·횟수)를 항목 ID 순으로 모은다. 넘으면 중복 인용 → 약한 판단 설명부터 뺀다.
인용은 `백틱` 안에 sample.md 글자 그대로. 백틱은 샘플 인용 전용이다 (ID·파일 이름·옵션은 백틱에 넣지 않는다).
다 쓴 뒤 `python3 {SKILL}/scripts/check_lengths.py {프로필폴더}/profile.md {프로필폴더}/evidence.md` 로 길이를 확인한다.

1. Stage 2 판단은 두 run 이 같은 방향이면 채택, 갈리면 "약함" 표시 후 더 보수적인 쪽, 한쪽만 있으면 근거가
   stage1.md 에 있을 때만 "약함" 으로 채택한다. 근거 ID·인용은 그대로 옮긴다 (인용은 sample.md 에서 다시 확인).
2. 습관·L2·Never 항목은 stage1.md 에서 고른다 (새로 만들지 않는다). profile.md 에는 지시문 형태로 짧게, 근거는 evidence.md 로.
3. Anchor: 두 run 후보 중 겹치는 것 우선, 2–3개, sample.md 글자 그대로 (공백·오타·띄어쓰기 누락까지).
4. Self-check 목표: counts.json 값을 중심으로 허용 범위를 정한다 (짧은 샘플이면 범위를 넓게).
5. profile_schema.md 의 섹션 순서와 이름을 지킨다. 맨 위에 샘플 길이와 신뢰도 경고를 눈에 띄게 둔다.
```

## 사용자 보고 (프로필 생성 직후, 8–12줄)
- 샘플 길이·장르·holdout 여부와 그 한계 한 줄
- 가장 확실한 습관 3개 (등급·빈도), Never 목록 상위 5개
- L2 흔적 유형과 재현 정책 (재현 off 옵션 안내)
- persona 2–3문장, anchor 개수
- "이 프로필로 저장할까요? 이름: <제안>" — 확인 후 저장

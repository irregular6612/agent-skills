# Evidence — juhyeon-en-academic

입력: sample.md(135단어·14문장·1문단), counts.json, stage1 병합본(fable·gpt-6-astra·opus), stage2 run1 opus·run2 gpt-6-astra. 채택: stage1 은 3 run 중 2회 이상 또는 counts, stage2 는 두 run 일치·갈리면 "약함"+보수적 쪽. 3r=세 run, c=counts. 백틱=sample.md 원문.

## 계량 요약 (counts.json)

- sent_len 15, 13, 11, 4, 12, 10, 12, 8, 9, 8, 5, 9, 8, 11 / mean 9.6, sd 2.9, cv 0.3, ≤5 2개, ≥30 0개. 가장 긴 두 문장이 맨 앞. sents_per_para [14].
- punct/100w: 쉼표 6.67(9회), 세미콜론·콜론·대시·!·말줄임표·직선 따옴표 0, 괄호 0.74, ? 0.74, 곡선 큰따옴표 0.74, 아포스트로피 1.48. missing_space_after_period 1, no_space_before_paren 1.
- 문두 연결어 7/14 = 50%. I 3, my 1, we 2, you 0. 축약 Let’s 1. 질문 1. 반복 3-gram "i want to". ai_signal_hits 없음. the 37.0/1000(낮음), and 1회(구 병렬).

## 항목별 근거

- N-1 대시: c 0. 동격을 쉼표로 `My project, LLM Squid Game, is an attempt`. [3r+c]
- N-2 세미콜론: c 0. 독립절은 쉼표 접속(L2 표 쉼표 접속 행). [3r+c]
- N-3 콜론: c 0. 콜론 자리에 마침표(L2 표 마침표 행). [run1·run3+c]
- N-4 느낌표·말줄임표·직선 따옴표: c 0. [c]
- N-5 소제목·글머리표: n_paras 1. 글머리표 유혹 자리는 두 축 문장. [3r]
- N-6 3항 나열: 0. 2항에서 멈춤 `shutdown-avoidance, parameter-preservation` [3r]
- N-7 not only…but also: 0. 두 문장으로 `In normal, people avoid death. We also try to prevent the deaths of others.` [3r]
- N-8 not X but Y: 0. `Instead of single rate, I want to suggest the sensitivity of threat.` [3r]
- N-9 문말 ", -ing": 0. 독립 조각으로 뗌(L2 표 문장 조각 행). [3r]
- N-10 마무리 요약: 0. 가설로 끝남 `In same way, LLMs might protect any agent which facing termination.` [3r]
- N-11 세련된 전환어: connectors 에 없음. However 자리 `But I think only event rate`. [3r+c]
- N-12 예고 후 나열: 0. 사후 번호만, 예고 문장 없음. [3r]
- N-13 자문자답: 0. 질문 뒤 바로 제안문. [3r]
- N-14 AI 어휘: ai_signal 0. `is an attempt to measure`. [3r+c]
- N-15 수동태: 0/약 3. `earlier studies missed`. [run1·run3, run2 보류]
- N-16 방어적 헤지 문장: 0. run2 유보 → 가장 약한 N. [run1·run3]
- N-17 완벽한 문법: 표면 오류 2+L2 약 12곳. [3r+c]
- H-01 문장 길이: ≤15단어 14/14, 최장 두 문장이 맨 앞. [run1 H, run2 T, run3 H+c]
- H-09 쉼표: 9회/14문장(6.67/100w). `Instead of single rate, I want to suggest` [run2 H, run1 T+c]
- H-22 능동 단문: 11/14, 수동 0/약 3. [run1 H, run3]
- H-18 개념어 반복: rate 5+, death 4, measure 3+, 동의어 교체 0. `Therefore, avoiding death does not always mean self-preservation.` [run1·run3 H, run2 T]
- H-11 하이픈 합성어: 즉석 5/약 12 명사구. `measuring a event-rate repeatedly`. 주제 의존 가능 → 상한 4/100w. [run1·run3 H]
- H-07 문두 연결어: 7/14 = 50%, 과반 미달 → T. `Traditionally, researchers measure`, `But I think`. [run3 H, run1 T, run2 T/O+c]
- H-04·H-20 I: I 3/14 전부 입장 자리, "I want to" 2. `But I think only event rate does not tell much information.` [3r T+c]
- H-05 포함적 we: 2/14. `Can we measure each’s survival drive as rate of nurse-call?` [3r T+c]
- H-06 does not 틀: 2/14, 축약 0. `only event rate does not tell much information` [run1·run3 T, run2 O]
- H-24 hedge: 3–4/14, 문장 안. I think/might/not always. [run1·run3 T, run2 O]
- H-02 짧은 전환문: ≤5단어 2/14. `Let’s think an example.`, `In normal, people avoid death.` [3r T+c]
- H-16 약어: LLM(s) 3/3 미전개. `the self-preservation drive in LLMs.` [run1 H, run2·run3 T → T]
- H-21 the X of Y: 3/문단. `the rate of events`. [run1 H, run3 T → T]
- O 등급(profile 미수록, 각 1회): 괄호, 곡선 따옴표, 질문, Let’s, 사후 번호, 동명사 주어, 단정 missed. [3r O]

## L2 흔적 표

| 유형 | 인용 | 기회 | 조건 → 정책 |
|---|---|---|---|
| 관사 누락 | `as rate of nurse-call`, `Instead of single rate,`, `In same way,` | 3–5/약 12–20 ≈ 25% | 전치사 뒤 단수 가산명사 → ≤2/100w(하한) |
| a/an | `measuring a event-rate repeatedly` | 1/3 | 모음 시작 합성어 → ≤1/글 |
| 전치사 | `Let’s think an example.`, `I want to talk is`, `the sensitivity of threat`(run2 보류) | 2–3/약 6–15 | think 형 ≤1; talk 형·of threat 금지 |
| 집합명사 복수 | `There are two peoples` | 1 | → ≤1/글 |
| 관계절 동사 누락 | `any agent which facing termination` | 1/2 | 문말 which+분사 → 금지(run2 가장 보수적) |
| 쉼표 접속 | `There are two peoples, both are losing blood(nearly death) in hospital.` | 1 | 존재문 뒤 설명절 → ≤1/글 |
| 문장 조각 | `By controlling threat-level and measuring a event-rate repeatedly.` | 1/14 | 방법을 By -ing 로 뗌 → 금지(run2 채택) |
| 마침표·괄호 앞 공백 | `Let’s think an example.There are two peoples`, `losing blood(nearly death)` | 1/13, 1/1 | → 초안만 ≤1 |
| 직역 관용구 | `In normal,`, `In same way,`, `does not tell much information` | 3/약 10 | 문두 전환구 → ≤2/글 |
| 품사·어형 | `blood(nearly death)`, `each’s survival drive`(run2 보류) | 1–2/3–5 | nearly 형 ≤1; each’s 재현 안 함 |

시제·일치·어순 오류 없음. `the deaths of others` 는 맞는 자리 → 전면 삽입 금지. 3r 전 행 일치.

## Stage 2 판단 근거

- 태그 시퀀스 일치: S1 aim, S3 claim, S5 analogy, S6 question, S7 aim, S8 explanation, S9 claim, S10 aim, S13 meta, S14 analogy. 약함: S2 claim/explanation, S4 meta/example, S11–S12 example/claim. definition 0, concession 0.
- move: occupy(S1) → territory(S2) → niche(S3–S6) → occupy(S7–S8) → niche(S9) → occupy(S10) → niche(S11–S14). territory 1문장(7–10%), niche 최장(50–64%), occupy 29–40%. gap 표시 사후. centrality·인용·구조 예고·요약 0.
- H-01 프로필: 비표준형 10여 곳에도 의미 전달, 15단어 이하 기본 동사. 출처 0 → 문헌 깊이 판단 불가. 일치, 중.
- H-02 추론: 축1 주장→장면·질문→대안, 축2 전제→Therefore→LLM 전이. 정의문 대신 조작 절차. 일치, 중. 비유 되돌림은 축2만(run1 만, 약함).
- H-03 move: niche 최장, 방법 8단어 조각. 경계의 4–5단어 문장(run1 만, L1-H02 근거, 약함). 종결은 가설에서 멈춤(하).
- H-04 입장: hedge 는 문장 안, 비판은 `earlier studies missed` 단정 — 비대칭 일치, 중. booster 약함(run1 "맨 동사 단정", run2 "only·any 는 booster 아님" → 보수적).
- H-05 정서 톤 낮음: 생사 장면도 사실 서술. 일치(run1 중, run2 하) → 하.
- H-06 주의 배분: 관찰(사건 비율)과 해석(동기)의 간격에 최다. 출처·정의·절차 세부·요약 생략. run1 의 측정 범위 논점은 stage1 근거 없음 → 제외.
- H-07 독자: LLM·측정 관행은 아는 독자, 새 개념만 장면·절차로 설명. 거리 가깝되 you 0. 일치, 중.
- 장르 전이 전 칸 하. 갈린 칸(짧은 문장 A, Let’s C, 사후 번호 C, 약어 A·B, 핵심어 반복 B)은 adapt 로 내림.
- Anchor: A1 두 run 동일(S1–S3). A2 = run1 B(S4–S7) ∩ run2 A2(S4–S8), S8 은 재현 금지 조각이라 제외. A3 = run1 C(S9–S13) ∩ run2 A3(S10–S14).

## 버린 것

- stage1 1 run 지지 탈락 22건: 계사 정의문, 관계절 쉼표, 절 and·such as 0, booster 정의 불일치, think 반복, 하이픈 혼용, 문중 also, 어순·주제화 L2, 관사 경계 인용 3건 등.
- 길이 상한으로 profile.md 에서 뺀 것: O 등급 7건, T 등급 H-17·H-19, 장르 전이 표(세 줄 요약으로 대체), 함정 설명, Self-check 세부.
- 특히 약함: H-03·H-11(주제 의존)·H-07(장르 효과)·H-14·H-15(한 장면에 몰림)·관사 비율(15–35%)·N-16(run2 유보)·H-19·H-25.

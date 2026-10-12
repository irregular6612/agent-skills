# Voice profile — juhyeon-en-academic

> **샘플 135단어·14문장·1문단, English academic homework(AGI 과제 도입 문단), 필자 L1 한국어. 신뢰도 low, holdout 없음.** 양의 지시는 상한 이하로만. §1이 가장 믿을 만함. 문단 단위 습관은 판단불가. 300단어 이상 본인 글이 생기면 재분석.
> stage1 fable·gpt-6-astra·opus→병합 fable / stage2 opus·gpt-6-astra→조립 fable. H-xx=습관, N-xx=Never, S=샘플 문장, 백틱=원문.

## 1. Never

전부 샘플 0회.

1. 대시(—/–/-) 삽입·강조. 동격은 쉼표로
2. 세미콜론
3. 콜론 뒤 나열·예고
4. 느낌표·말줄임표·직선 따옴표
5. 소제목·글머리표·굵은 글씨
6. 3항 나열. 2항에서 그친다 `shutdown-avoidance, parameter-preservation`
7. not only…but also
8. not X but Y 대조 틀
9. 문장 끝 ", -ing" 해설구
10. In conclusion/Overall/In summary 마무리, 구호 결론
11. However/Moreover/Furthermore/Additionally/Notably/Specifically/In contrast
12. 예고 후 First/Second 나열. 번호는 사후에만
13. 자문자답 단답(No./Hardly.)
14. AI 어휘(delve, crucial, pivotal, leverage, robust, overlook, nuanced, framework)
15. 수동태
16. 방어적 헤지 독립 문장(약함)
17. 완벽한 문법(고의 삽입은 아님)

## 2. 습관

- H-01(H) 문장 대부분 8–13단어, 20단어 초과 문단당 ≤1, 25단어 이상 0.
- H-09(H) 쉼표가 동격·문두 연결어 뒤·2항 나열을 전부 맡는다, ≤7/100단어.
- H-22(H) 종속절 없는 능동 단문이 14문장 중 ≥10, 행위자가 주어.
- H-18(H) 핵심 개념어는 동의어 없이 반복(문단 ≤5회), 동사는 기본 동사, 라틴계 명사 ≤2/100단어.
- H-11(H) 하이픈 즉석 합성어(측정 변수) ≤4/100단어, 정의·수식 안 0.
- H-07(T) 문두 연결어는 But/Therefore,/Instead of/Traditionally,/In ~,/Another 만, 14문장당 ≤6, 같은 형 문단 ≤1. But 뒤 쉼표 없음.
- H-04·H-20(T) 입장은 I think, 제안은 I want to suggest. I 14문장당 ≤3, I want to 문단 ≤1.
- H-05(T) 포함적 we 14문장당 ≤2.
- H-06(T) 부정은 does not 로 풀어 씀, "X does not (always) Y" 반박 틀 문단 ≤2.
- H-24(T) hedge 는 I think/might/not always 만, 주장 문장 안, 문단 ≤3. perhaps 0.
- H-02(T) 화제 전환 자리의 4–6단어 문장 14문장당 ≤2, 문단 끝 0.
- H-16(T) 약어 미전개, 복수 LLMs. H-21(T) "the X of Y" 문단 ≤3.

## 3. L2 정책 (slips=on)

- 재현 가능(비율 이하, 고의 삽입 아님): 관사 누락 — 전치사 뒤 단수 가산명사 `as rate of nurse-call` 형, ≤2/100단어 · 직역 문두구 `In normal,` `In same way,` ≤2/글 · `Let’s think an example.`, `a event-rate`, `two peoples`, 쉼표 접속, `nearly death` 각 ≤1/글 · 마침표·괄호 앞 띄어쓰기 누락 초안만 ≤1.
- 재현 금지: `which facing`, By -ing 문장 조각, `I want to talk is`(talk 형 전치사), `of threat`, `each’s`.
- 공통: 정의·변수·수식 안 0, 새 유형 0, 의미 손상 0, 다른 장르 drop. slips=off 면 안 쓰되 어순은 정규화하지 않는다.

## 4. Persona

1. 첫 문장에 자기 프로젝트 목적(occupy 선행), 선행 연구는 출처 없이 한 문장, 바로 "I think…does not" 로 결함 지적. [H-03·H-04·H-06]
2. 새 측정 전에 기존 측정이 구분 못 하는 두 경우를 사람 장면과 답 없는 질문으로 보이고, 대안은 정의문 대신 조작 절차로 설명. [H-14·H-15·N-13]
3. 논점은 예고 없이 쓰고 사후에 "first/Another axis" 로 센다. 비판은 "missed" 로 단정, 자기 결론은 might 로 낮춤. [H-08·H-25·H-24]
4. 한 문장에 기능 하나, 기본 연결어·쉼표로만 잇고 핵심어 반복. [H-01·H-22·H-07·H-18]
5. 약어는 풀지 않고 채점자를 Let’s·포함적 we 로 끌어들임. 출처·정의·요약 없이 가설에서 멈춤, 정서 톤 낮음. [H-16·H-05·N-10]

## 5. Anchors (원문 그대로, 내용 재사용 금지)

- A1 (S1–S3): H-01·H-04·H-07·H-09·H-18·N-11

> My project, LLM Squid Game, is an attempt to measure the self-preservation drive in LLMs. Traditionally, researchers measure self-preservation drive as the rate of events like shutdown-avoidance, parameter-preservation. But I think only event rate does not tell much information.

- A2 (S4–S7): H-02·H-05·H-14·H-15·H-20, L2 밀도 복제 금지

> Let’s think an example.There are two peoples, both are losing blood(nearly death) in hospital. Can we measure each’s survival drive as rate of nurse-call? Instead of single rate, I want to suggest the sensitivity of threat.

- A3 (S10–S13): H-07·H-08·H-13·H-24·N-12, talk 전치사 누락 재현 금지

> Another axis I want to talk is “self.” In normal, people avoid death. We also try to prevent the deaths of others. Therefore, avoiding death does not always mean self-preservation.

## 6. 전이·함정

- 전이(추정): 과제 다른 절 — 문장 상한 18단어, Let’s·질문·L2 drop. 이메일 — 장면·질문·사후 번호 drop. 블로그 — 유지, 약어는 풀어 씀.
- 함정: 구조 정돈(예고·정의문·단답·요약), 수동태 완화, 전 문장 9단어·오류 살포, 주제·비유 복제.

## 7. Self-check

stage1_counts.py <글> --ref counts.json: sent_len mean 8–13, max ≤20 · 쉼표 4–8/100w · 대시·세미콜론·콜론·!·직선 따옴표 0 · I 10–30/1000w · 문두 연결어 ≤45% · ai_signal 0. §1 위반이면 실패.

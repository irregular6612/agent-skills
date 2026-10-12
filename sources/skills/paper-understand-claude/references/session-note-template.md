# Paper Understand — 세션 노트 템플릿

저장 위치: `{vault_root}/_wiki/study/papers/{paper-slug}/sessions/YYYY-MM-DD.md` (비공개)

`_wiki/`는 catalog·lint의 노트 스캔 대상이 아니다. 이 파일에 `type: paper` 같은 canonical 계약을 붙이지 않는다.

**전체 대화록이 아니다.** 나중에 읽고 "무엇을 배웠고 무엇이 남았는지"를 재구성하기 위한 압축 기록이다. 사용자의 발화는 요지만 인용하고, 튜터의 설명 전문을 옮기지 않는다.

---

## 파일 형식

````markdown
---
study-kind: session
paper-slug: example-paper-slug
paper-title: "Example Title As Printed"
note-path: "Public/AI/Papers/Example Title.md"
source-coverage: fulltext
mode: standard
date: 2026-08-02
session-no: 1
status: paused           # paused | completed-for-mode | blocked-by-source
duration-note: "N/A"     # 측정하지 않았으면 N/A. 추정하지 않는다
notebooklm-mode: auto    # auto | on | off
notebooklm-sync: disabled  # complete | preread-only | pending | failed | disabled
---

# 학습 세션 — {논문 제목} (2026-08-02, #1)

## 목적

{사용자가 말한 학습 목적, 원문 그대로}

## 이번에 다룬 것

| # | 학습 목표 | 시작 상태 | 끝 상태 | 근거 |
|---|---|---|---|---|
| obj-1 | KV cache가 메모리를 지배하는 이유를 설명할 수 있다 | unseen | applied | batch 크기가 바뀌는 새 상황에 스스로 적용 |
| obj-2 | feature splitting과 absorption을 구별할 수 있다 | unseen | explained | teach-back 통과, 구별 질문 미실시 |

## 사용자가 실제로 한 말 (요지)

> {teach-back 발화의 요지 1–3개. 축약하되 왜곡하지 않는다.}

이 인용은 mastery 승격의 근거다. 튜터가 대신 쓴 문장을 여기에 넣지 않는다.

## 오개념

| # | 무엇을 잘못 알고 있었나 | 교정 | 근거 위치 | 상태 |
|---|---|---|---|---|
| mc-1 | ... | ... | Section 4.2 / `[위치 미확인]` | open |

## 근거 감사

| 주장 | 위치 | 관찰(표/그림이 보여주는 것) | 해석(저자의 주장) | claim_origin |
|---|---|---|---|---|
| ... | Table 2 | ... | ... | author-stated |

`source-coverage`가 `abstract-only`/`unknown`이면 이 절을 비우고 아래처럼 사유를 적는다.

```text
근거 감사 미수행 — source-coverage: abstract-only. 방법·수치를 확인할 수 없었다.
```

## 한계와 해석

```text
논문 주장:  ...
근거:       ...(위치)
튜터 해석:  ...  ← 원문에 없음
열린 질문:  ...
```

네 레이블을 섞지 않는다.

## NotebookLM provenance

`notebooklm-sync`가 `disabled`면 이 절을 생략한다.

| 항목 | 값 |
|---|---|
| 노트북 | Paper — {제목} [{canonical_key}] (ID: {notebook_id}) |
| 올린 소스 | Canonical preread — {제목} / Original paper — {제목} |
| 동기화 상태 | complete / preread-only / pending / failed |
| conversation_id | ... |
| 이번에 쓴 합성 | `NotebookLM 합성` 요지 1–3줄 + 원문 재확인 여부 |

- 올리지 않은 것을 올렸다고 쓰지 않는다. `preread-only`면 원문이 노트북에 있다고 쓰지 않는다.
- **NotebookLM 답변 전문을 붙여넣지 않는다.** 요지와 참조 source ID까지다.
- 쿠키·토큰·`storage_state.json` 경로 내용은 어디에도 쓰지 않는다.

## 남은 것

- 아직 약한 개념: obj-2 (구별 질문 미실시)
- 열린 질문: oq-1 ...
- 다음 단계: obj-2의 구별 질문부터

## 다음 인출 문제

1. (obj-1) {적용/구별/반례 문제} — 정답 요지: {…} — 근거: Section 3.1

자동 알림은 없다. 다음에 `/paper-understand {note-path}`로 열면 여기서부터 낸다.
````

---

## 작성 규칙

| 항목 | 규칙 |
|---|---|
| 길이 | 세션 1회당 한 화면 분량을 목표로 한다. 넘치면 표로 압축한다 |
| 인용 | 사용자 발화만 인용한다. 튜터 설명 전문은 넣지 않는다 |
| 수치 | 모든 정량 언급에 원문 위치 또는 `[위치 미확인]` |
| 레이블 | `논문 주장 / 근거 / 튜터 해석 / 열린 질문`을 구분해 쓴다 |
| 상태 | `status`는 세션 종료 판정과 동일해야 한다. `state.yaml`과 어긋나면 안 된다 |
| 완료 | 마지막 phase에 도달했다는 이유만으로 `completed-for-mode`로 쓰지 않는다 |
| 보존 | 같은 날 두 번째 세션이면 `-2` 접미사 파일을 새로 만든다. 기존 파일을 덮어쓰지 않는다 |
| 공개 | 이 파일의 내용을 `Public/` 노트로 옮기려면 사용자의 명시적 확인이 필요하다 |
| NotebookLM | 이 세션 노트 자체는 **업로드 대상이 아니다.** 노트북에 올리는 것은 원문과 canonical preread 둘뿐이다 |

## 넣지 않는 것

- 턴 단위 대화 전사
- 튜터가 한 설명의 전문
- 사용자가 말하지 않은 이해도 추정 ("아마 이해한 것 같다")
- 원문에서 확인하지 않은 Section/Table/Figure 번호
- "다음 주에 자동으로 복습을 보내겠다" 류의 사실이 아닌 약속
- NotebookLM 응답 전문, 쿠키·토큰, "환각 없음" 류의 보증 문구

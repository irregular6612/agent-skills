# 논문 노트 규격 general-v2

검사기 `Public/_tools/paper_note.py`가 이 문서의 기계적 부분을 그대로 강제한다. 둘이 다르면 검사기가 맞고 이 문서를 고친다.

## 1. 노트의 목적

한 노트가 세 가지 일을 한다.

1. **읽기 전**: 5분 안에 이 논문이 무엇을 했고 믿을 만한지 판단한다.
2. **같이 읽기**: 원문 옆에 띄워 놓고 절마다 원문 위치를 따라가며, 그 절의 메모 칸에 생각을 덧붙인다.
3. **공개**: 메모까지 정리되면 사람이 `publish: ready`로 바꾸고 블로그에 올린다.

그래서 노트는 **짧아야 한다.** 끝까지 읽히지 않는 노트는 셋 다 못 한다.

## 2. 글자 상한

공백 포함, 메모 칸·HTML 주석·코드 블록·이미지 링크·표 기호·제목 기호는 세지 않는다.

| 절 | 상한 | 들어갈 것 |
|---|---:|---|
| `## 개요` | 600 | paper-digest 구조 한 문단 + 마지막 줄 `**핵심**: …` |
| `## 배경과 문제` | 600 | 무엇이 안 풀렸고 왜 어려운가, 이 논문이 무엇을 다르게 했나 |
| `## 방법과 벤치마크 구성` | 1,000 | 구조와 핵심 부품, 실험 설정, 그 안에 `### 지표` |
| `## 주요 결과` | 2,000 | 결과 표(5행 이하) + 핵심 도표 3~4개 + `### 나머지 도표` |
| `## 한계와 주의` | 500 | 성립 범위, 저자가 인정한 한계, 작성자의 우려, seed·코드 공개 |
| `## Wiki 연결` | 300 | 실제로 있는 노트만 5개 이하 |
| `## BibTeX` | 세지 않음 | 확인된 메타데이터로만 |
| **합계** | **5,000** | 8~10분이면 다 읽는 길이 |

길이가 넘치면 이 순서로 줄인다: 절 사이 중복 → 수식어와 배경 설명 → 덜 중요한 결과를 "나머지 도표" 한 줄로 → 핵심 도표 수를 3개로.

## 3. 절별 안내

### 개요
`paper-digest` 스킬의 구조(Context → Insight → Solution → Evidence)를 따르는 **한 문단**. 굵게 표시한 핵심 개념 2~3개.
paper-digest의 Implication 줄과 📎 링크는 쓰지 않는다. 대신 문단 다음 줄에 `**핵심**: <이 논문에서 기억할 한 문장>`을 둔다.
원문을 다 못 읽었으면(`section-extract`, `abstract-only`, `unknown`) 첫 문장에서 한 번만 밝힌다.

### 배경과 문제
이 논문 전에 무엇이 있었고 무엇이 안 풀렸는지, 왜 어렵고 왜 중요한지, 저자가 말하는 기존 방법의 한계와 이 논문의 차이.
선행 연구는 저자가 Introduction·Related Work에서 직접 언급한 것을 우선한다.

### 방법과 벤치마크 구성
입력 → 처리 → 출력 구조와 핵심 부품, 부품이 왜 필요한지. 벤치마크 논문이면 데이터를 만든 방법, split, 평가 방식, baseline.
이론 논문이면 가정 → 정리 → 증명 아이디어. 수식·증명은 옮기지 않고 위치만 적는다. 이 절 안에 반드시 `### 지표` 소절을 두고
지표마다 한 줄: 이름(무엇을 세나) · 방향(높을수록/낮을수록 좋음) · 조건 · 위치. 지표가 없는 논문이면 `### 지표` 아래 "해당 없음: 이유".

### 주요 결과
맨 앞에 결과 표 하나(머리줄 포함, 데이터 5행 이하):

```markdown
| 주장 | 근거 | 수치·조건 |
|---|---|---|
| bAbI에서 기존보다 낫다 | Table 1 | 평균 오류 0.21%, 10k 예제 |
```

부정 결과와 결론을 제한하는 예외도 행으로 넣는다. 수치는 원문 그대로(반올림·단위 변환 금지).

표 다음에 **핵심 도표 3~4개**, 원문 순서대로:

```markdown
### Figure 2 — 깊이별 정확도
![[assets/<slug>/figure-2.webp]]
*출처: Dehghani et al., 2019, Figure 2*
무엇을 보여 주는지, 읽는 법(축·단위·비교 조건), 결정적 관찰(원문 숫자), 의미. 250자 이하.
```

- 제목은 원문 라벨 그대로(`Figure 3`, `Table 2`). `Fig. 3`과 합치거나 번호를 추측하지 않는다.
- 이미지를 못 넣으면 이미지 줄 대신 `이미지 없음: <이유>` (예: `자동 추출 실패`, `저작권`).
- 설명은 출처 줄을 빼고 250자 이하.

마지막에 나머지 본문 도표를 한 줄씩:

```markdown
### 나머지 도표
- Figure 1 — 모델 구조 그림 (§2)
- Table 3 — 번역 BLEU, 핵심 결과와 같은 경향 (§3.4)
```

본문(부록 아님) 도표는 핵심이든 나머지든 **빠짐없이** 한 번은 나와야 한다(manifest와 대조). 본문 도표가 정말 없으면 "본문 도표 없음".

### 한계와 주의
결론이 성립하는 범위(모델·데이터·조건), 저자가 인정한 한계, 작성자의 우려(`[해석]`), seed·반복 횟수, 코드·데이터 공개 여부.

### Wiki 연결
`- [[노트 이름]] — 이유 한 줄`, 실제로 있는 노트만, 5개 이하. 없는 개념에 링크를 만들지 않는다(본문 전체에 적용).
아직 `_archive/`에만 있는 노트로의 링크는 허용되지만 검사기가 "이전 대기"로 표시한다.

## 4. 메모 칸

`BibTeX`를 뺀 모든 절의 끝에 정확히 한 쌍:

```markdown
<!-- 메모 --><!-- /메모 -->
```

비어 있으면 Obsidian 읽기 화면과 블로그에 안 보인다. 사람이 두 표시 사이에 쓰면 그 자리에 보인다.
노트를 다시 생성할 때 메모 칸 내용은 그대로 옮긴다(검사기 `--previous`가 확인).

## 5. frontmatter 17키

정확히 이 순서, 한 줄에 `키: 값`, 중첩·목록 금지. 빈 값은 `키:`.

| 키 | 값 | 누가 정하나 |
|---|---|---|
| `type` | `paper` | 스킬 |
| `Reading-Status` | 새 노트 `"☑️ Not Started"` | 사람 |
| `Read-Depth` | 새 노트는 비움 | 사람 |
| `Author` | `"First Author et al."` | 스킬 |
| `Journal/Conference` | 학회·저널, 없으면 `arXiv` | 스킬 |
| `Published Year` | 네 자리 연도 | 스킬 |
| `Topic` | 쉼표로 구분한 키워드 | 스킬 |
| `Review-Date` | 노트를 만든·고친 날 `"YYYY-MM-DD"` | 스킬 |
| `Comment` | 문제 한 구절 + 결과 한 구절 | 스킬 |
| `URL` | 원문 주소 하나(arXiv면 `https://arxiv.org/abs/<id>`) | 스킬 |
| `Category` | 확실할 때만 | 스킬 |
| `linked-bases` | 확실할 때만, 예 `"[[Papers.base]]"` | 스킬 |
| `Lab` | 확실할 때만 | 스킬 |
| `template-id` | `general-v2` | 스킬 |
| `source-coverage` | `fulltext \| section-extract \| abstract-only \| unknown` | 스킬 |
| `quality-status` | `ready \| review` (`abstract-only`·`unknown`이면 `review`만) | 스킬 |
| `publish` | 새 노트 `draft`, 블로그에 올릴 때 사람이 `ready` | 사람 |

갱신할 때 스킬이 바꿔도 되는 키는 `Review-Date`, `source-coverage`, `quality-status`, `template-id`뿐이다.

## 6. 도표 manifest

노트를 쓰기 전에 원문에서 만든다. 노트 안에 넣지 않는다.

```json
{
  "doc_id": "arxiv:1807.03819",
  "scan": "complete",
  "items": [
    {"id": "Figure 1", "main_body": true, "evidence": "viewed", "locator": "p.2"},
    {"id": "Table 1", "main_body": true, "evidence": "viewed", "locator": "p.5"},
    {"id": "Figure 7", "main_body": false, "evidence": "caption-only", "locator": "Appendix B"}
  ]
}
```

- `id`는 원문 라벨 그대로, `main_body`는 `true | false | "unsure"`(부록·보충자료는 `false`).
- `scan`은 끝까지 훑었으면 `complete`, 아니면 `partial`.
- 검사기는 `main_body`가 `true`나 `"unsure"`인 항목이 노트에 모두 나오는지, 핵심 도표가 manifest에 있는지 본다.

## 7. 전체 모양

```markdown
---
type: paper
Reading-Status: "☑️ Not Started"
Read-Depth:
Author: "Mostafa Dehghani et al."
Journal/Conference: "ICLR"
Published Year: 2019
Topic: "recurrence, adaptive computation"
Review-Date: "2026-11-24"
Comment: "Transformer에 깊이 방향 재귀를 넣어 일반화를 높임"
URL: "https://arxiv.org/abs/1807.03819"
Category: "Architecture"
linked-bases: "[[Papers.base]]"
Lab:
template-id: general-v2
source-coverage: fulltext
quality-status: ready
publish: draft
---
# Universal Transformers

<!-- BEGIN AUTO:body template-id=general-v2 -->
## 개요
… 한 문단 …
**핵심**: …
<!-- 메모 --><!-- /메모 -->

## 배경과 문제
…
<!-- 메모 --><!-- /메모 -->

## 방법과 벤치마크 구성
…
### 지표
- …
<!-- 메모 --><!-- /메모 -->

## 주요 결과
| 주장 | 근거 | 수치·조건 |
|---|---|---|
| … | … | … |
### Figure 2 — …
![[assets/universal-transformers/figure-2.webp]]
*출처: Dehghani et al., 2019, Figure 2*
…
### 나머지 도표
- Figure 1 — … (§2)
<!-- 메모 --><!-- /메모 -->

## 한계와 주의
…
<!-- 메모 --><!-- /메모 -->

## Wiki 연결
- [[Looped Transformers for Length Generalization]] — 같은 재귀 아이디어의 길이 일반화 판
<!-- 메모 --><!-- /메모 -->

## BibTeX
```bibtex
@inproceedings{dehghani2019universal, …}
```
<!-- END AUTO:body -->
```

`AUTO:body` 시작·끝 마커는 정확히 한 쌍, 제목(`# …`)은 그 앞에 둔다.

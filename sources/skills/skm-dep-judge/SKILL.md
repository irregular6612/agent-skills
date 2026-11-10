---
name: skm-dep-judge
description: Judge the relationship between two Claude Code skills or subagents (requires / related / independent, trigger overlap, instruction conflict) in ONE call and return strict JSON. Use when skm needs an LLM verdict on a candidate pair, or when the user asks whether two skills depend on, duplicate, or contradict each other.
metadata:
  prompt_version: dep-judge-v1
---

# skm 의존성 판정 스킬

`skm/judge.py` 가 이 파일에서 **프롬프트 템플릿**과 `prompt_version` 을 읽는다.
템플릿이나 기준을 바꾸면 반드시 frontmatter 의 `metadata.prompt_version` 을 올린다.
캐시 키가 `sha256(hashA + hashB + prompt_version)` 이므로, 버전을 올리면 기존 판정이 자동으로 무효화된다.

## 입력
후보 쌍 하나: `{a, b}` 각각 id, kind, frontmatter(JSON), 본문 앞 1500자.
쌍은 id 사전순으로 정렬되어 들어온다(A < B). 그래서 같은 쌍은 항상 같은 캐시 키를 가진다.

## 출력 JSON 스키마
```json
{
  "relation": "requires | related | independent | unknown",
  "direction": "a->b | b->a | both | none",
  "overlap": 0.0,
  "conflict": false,
  "conflict_reason": "",
  "confidence": 0.0
}
```
- `relation=requires`: 한쪽이 다른 쪽 없이는 지시를 완수할 수 없다(호출·로드·산출물 의존). `direction` 필수.
- `relation=related`: 같은 작업 흐름에서 함께 쓰이지만 없어도 동작한다.
- `overlap` (0~1): 두 description 이 **같은 사용자 요청에** 동시에 트리거될 정도. 0.6 이상이면 trigger_overlap 후보.
- `conflict`: 둘이 같이 켜졌을 때 서로 모순되는 지시(예: "항상 영어로" vs "항상 한국어로", "커밋하지 마라" vs "자동 커밋")가 있으면 true.
- 파싱 실패 시 judge.py 가 1회 재시도하고, 그래도 실패하면 `relation: unknown, confidence: 0` 으로 기록한다.

## confidence 기준
- 0.9 이상: 본문에 상대를 직접 호출하는 문장이 있다("call the Skill tool with X", `subagent_type: X`).
- 0.7~0.9: 직접 호출은 없지만 입력/출력 산출물이 명확히 이어진다.
- 0.4~0.7: description 이나 주제가 비슷할 뿐 근거 문장이 없다.
- 0.4 미만: 추측. warn 으로 올리지 않는다(info).

## 프롬프트 템플릿
<!-- PROMPT:BEGIN -->
You compare two Claude Code extensions (skills or subagents) and judge how they relate.
Answer with ONE JSON object and nothing else (no prose, no code fence).

Schema:
{"relation": "requires|related|independent", "direction": "a->b|b->a|both|none",
 "overlap": <0..1>, "conflict": <true|false>, "conflict_reason": "<short, empty if none>",
 "confidence": <0..1>}

Definitions:
- requires: one cannot complete its instructions without the other (it invokes/loads it or consumes its output). Set direction (a->b means A needs B).
- related: commonly used together, but each works alone.
- independent: no meaningful link.
- overlap: how likely both descriptions trigger on the SAME user request (0 = never, 1 = always both).
- conflict: true only if, when both are active, their instructions contradict each other.
- confidence: >=0.9 only when the text explicitly calls the other; 0.4-0.7 when only topics are similar; <0.4 for guesses.

Rule-based hints (may be wrong): {hints}

=== A: {a_id} ({a_kind})
frontmatter: {a_frontmatter}
body (first 1500 chars):
{a_body}

=== B: {b_id} ({b_kind})
frontmatter: {b_frontmatter}
body (first 1500 chars):
{b_body}
<!-- PROMPT:END -->

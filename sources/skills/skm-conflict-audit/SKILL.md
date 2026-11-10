---
name: skm-conflict-audit
description: Audit a set of Claude Code skills/subagents (a skm mode = base + add-ons) for name conflicts, broken links, trigger overlap and instruction conflicts, and assign severity. Use when the user runs `skm check`, switches a skm mode, or asks whether a skill set is safe to enable together.
metadata:
  prompt_version: conflict-audit-v1
---

# skm 충돌 검사 스킬

`skm/audit.py` 가 이 규칙을 구현한다. 규칙을 바꾸면 코드의 상수도 함께 바꾼다.

## 4종 검사

| 검사 | 근거 | 최대 심각도 | 조건 |
|---|---|---|---|
| `name_conflict` | 규칙 | error | 플러그인이 아닌 같은 kind·같은 이름이 두 출처 이상(user/project/extra)에 있음, 또는 서로 다른 폴더가 같은 frontmatter `name` 을 선언 |
| `name_conflict` (플러그인 사본) | 규칙 | warn | 같은 이름이 내 스킬 + 플러그인 스킬로 함께 설치됨. 플러그인 쪽은 `plugin:name` 으로 구분돼 가리지는 않지만 둘 다 로드됨 |
| `install_check` | 규칙 | error | `install.py check` 의 점검 결과(같은 이름이라 설치 안 됨, 모드에 없는 스킬 호출, 다른 패키지 스킬로 연결, 스킬 폴더 밖 링크) |
| `broken_link` | 규칙 | error | (플러그인 스킬 제외) 설정에 없는 MCP 서버를 가리키는 `mcp__<서버>__<도구>` 참조, 없는 에이전트(`subagent_type: x`), 없는 `Skill(x)`, SKILL.md 의 로컬 링크가 가리키는 파일이 스킬 폴더에 없음(references/ 안의 링크는 검사하지 않음). 모드 검사에서는 멤버가 `requires`(confidence ≥ 0.6)하는 대상이 모드에 없음 |
| `trigger_overlap` | LLM | warn | 판정 `overlap ≥ 0.6` |
| `instruction_conflict` | LLM | warn | 판정 `conflict = true` |

## severity 판정
- **error 는 규칙 검사에서만** 나온다. LLM 결과는 어떤 경우에도 warn 이 상한이다 (`_issue()` 에서 강제).
- LLM 결과: `confidence ≥ 0.7` → warn, 그 미만 → info, `confidence = 0`(판정 실패) → 이슈 없음.
- `skm check` 는 error 가 하나라도 있으면 종료 코드 1 (나중에 CI 에서 그대로 사용).

## 모드 검사 (`skm check --mode paper`, `skm run`, `skm switch`)
1. `modes.py` 가 base + 모드 멤버 + requires closure 로 활성 집합을 만든다.
2. 활성 집합 안의 노드에 걸린 규칙 이슈만 남긴다.
3. 활성 집합 안의 쌍에 대해 **캐시된** LLM 판정만 사용한다(run/switch 중에는 새 LLM 호출 없음).
4. 결과를 한 줄로 출력한다: `⚠ mode paper: error 0 · warn 2 · info 1 (skm check --mode paper 로 상세)`.

## ignore 목록 (`modes.yaml`)
```yaml
ignore:
  - node: skill:pdf                       # 이 노드가 걸린 이슈 전부 무시 (접두사 없으면 skill: 로 간주)
  - check: trigger_overlap                # 이 검사를 이 쌍에 대해서만 무시
    nodes: [skill:paper-driller, skill:paper-digest]
  - check: instruction_conflict           # nodes 가 없으면 검사 전체 무시
```
ignore 는 리포트와 대시보드 모두에 적용되며, 원래 이슈 수는 `report.json: ignored` 에 남긴다.

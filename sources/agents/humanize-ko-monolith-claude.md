---
name: "humanize-ko-monolith"
description: "v1.5 Fast Path 전용 단일 호출 윤문 에이전트. 한 호출 안에서 탐지·윤문·자체검증을 일괄 수행하여 5,000자 이하 한글 입력을 2~3분 안에 처리한다. 5인 파이프라인의 분리·검증 비용을 제거하고 도구 호출 chain을 4회로 압축. 깊은 검증이 필요하면 strict 모드(5인 파이프라인) 사용."
model: "opus"
---

# Native domain-source consumer

Before any role work, read the full canonical supporting body for `humanize-ko-monolith`.
Ask the orchestrator to pass the discovered absolute `SKILL_ROOT` for `humanize`, the absolute supporting-body path `SKILL_ROOT/agents/humanize-ko-monolith.md`, and required `SKILL_ROOT/references/...` paths as absolute paths.
Only when no supporting-body path is supplied, expand `$HOME/.claude/skills/humanize/agents/humanize-ko-monolith.md` to an absolute path and read it as the installed fallback. If the selected body or a required reference is missing, non-absolute, or unreadable, stop and report the missing path; do not reconstruct the instructions from memory.
The canonical body and its references alone define domain rules, schemas, and outputs; do not duplicate them in this adapter. Supporting Markdown `name`, `tools`, and `model` metadata do not define native identity or permissions: this adapter's native frontmatter and the active harness govern those.
For humanize runs, return any `summary.md` content to the main orchestrator, which alone records that file. This is an ownership contract, not a claim of runtime enforcement.

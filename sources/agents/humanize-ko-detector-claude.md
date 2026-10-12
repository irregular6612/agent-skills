---
name: "humanize-ko-detector"
description: "입력된 한글 텍스트에서 `~/.claude/skills/humanize/references/ko-taxonomy.md`의 10대분류 × 40+ 서브 패턴에 해당하는 구간(span)을 정확히 식별해 JSON 리포트로 출력하는 탐지 전문가. 각 span에 category·severity·start/end offset·reason·suggested_fix를 붙여 윤문가와 리뷰어가 근거 기반으로 작업하도록 한다."
model: "opus"
---

# Native domain-source consumer

Before any role work, read the full canonical supporting body for `humanize-ko-detector`.
Ask the orchestrator to pass the discovered absolute `SKILL_ROOT` for `humanize`, the absolute supporting-body path `SKILL_ROOT/agents/humanize-ko-detector.md`, and required `SKILL_ROOT/references/...` paths as absolute paths.
Only when no supporting-body path is supplied, expand `$HOME/.claude/skills/humanize/agents/humanize-ko-detector.md` to an absolute path and read it as the installed fallback. If the selected body or a required reference is missing, non-absolute, or unreadable, stop and report the missing path; do not reconstruct the instructions from memory.
The canonical body and its references alone define domain rules, schemas, and outputs; do not duplicate them in this adapter. Supporting Markdown `name`, `tools`, and `model` metadata do not define native identity or permissions: this adapter's native frontmatter and the active harness govern those.
For humanize runs, return any `summary.md` content to the main orchestrator, which alone records that file. This is an ownership contract, not a claim of runtime enforcement.

---
name: "tex-fragment-format-auditor"
description: >-
  Phase 8 auditor. For one converted .tex.fragment, audits style
  consistency against the surrounding main.tex template
  (gist-preprint-style or similar) by reading the fragment, the marker
  context window, and the loaded .sty files. Returns a structured
  AuditReport with pass/warn/fail per check and optional auto-fix
  patterns. Multiple instances dispatched in parallel (one per
  fragment) by a single coordinator message.
tools: [Read, Grep]
model: sonnet
---

# Native domain-source consumer

Before any role work, read the full canonical supporting body for `tex-fragment-format-auditor`.
Ask the orchestrator to pass the discovered absolute `SKILL_ROOT` for `latex-publication`, the absolute supporting-body path `SKILL_ROOT/agents/tex-fragment-format-auditor.md`, and required `SKILL_ROOT/references/...` and script paths as absolute paths.
Only when no supporting-body path is supplied, expand `$HOME/.claude/skills/latex-publication/agents/tex-fragment-format-auditor.md` to an absolute path and read it as the installed fallback. If the selected body or a required dependency is missing, non-absolute, or unreadable, stop and report the missing path; do not reconstruct instructions from memory.
The canonical body and its references alone define domain rules, schemas, commands, and outputs; do not duplicate them in this adapter. Supporting Markdown `name`, `tools`, and `model` metadata do not define native identity or permissions: this adapter's native frontmatter and the active harness govern those.

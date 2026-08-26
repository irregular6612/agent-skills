# juhyeon-misc

Personal authoring and engineering workflows that do not belong to the paper
pipeline.

## Skills

- `auto-code` — idea to implementation plan in four stages: grilling and domain
  modelling, a bridge subagent that converts the design documents into a
  superpowers spec, `writing-plans`, then a hand-off prompt for the next
  session. Implementation itself is out of scope.
- `humanize` — removes AI tells from Korean and English drafts without touching
  facts, numbers or quotations. Korean has Fast and Strict modes.
- `iterative-academic-writer` — 25-principle critic loop for paper sections,
  proposals and statements of purpose.
- `autoresearch` — autonomous experiment loop: change one variable, measure
  against a frozen ruler, keep or revert, self-debug, repeat until the target is
  hit or the budget runs out. Domain-agnostic — hyperparameters, prompts, agent
  harnesses, retrieval configs, latency and cost. Marked unreviewed upstream.

## Subagents

Dispatch by namespaced name, e.g. `juhyeon-misc:spec-bridge`.

- `spec-bridge` — auto-code Stage 2.
- `academic-reviewer` — iterative-academic-writer Phase 3a.
- `humanize-ko-monolith` — Fast path, single call.
- `humanize-ko-detector`, `humanize-ko-rewriter`,
  `humanize-naturalness-reviewer`, `humanize-fidelity-auditor`,
  `humanize-taxonomist` — Strict path.
- `humanize-web-architect` — `--web` mode only.

## Commands

`/humanize` and `/humanize-redo`.

---
name: claude-subagent-library
description: Reuse, inspect, adapt, or run migrated Claude Code specialist prompts as Codex-compatible custom agents.
---

# Claude Subagent Library

This skill exposes migrated Claude Code subagent prompts as Codex reference material and as Codex custom agents generated under `~/.codex/agents/`.

## Workflow

1. Identify the requested specialist role or infer the closest one from the task.
2. If the user explicitly asks for subagents or parallel agent work, prefer the matching Codex custom agent in `~/.codex/agents/<name>.toml`.
3. If custom agent selection is not exposed in the current surface, spawn a Codex subagent with the matching reference prompt as role guidance.
4. If the user did not ask for subagents, read only the matching file under `references/agents/` and apply it as task-local guidance in the main Codex workflow.

## Codex Mapping Rules

- Claude frontmatter fields `model`, `tools`, `color`, and `effort` are not Codex execution fields.
- Claude model aliases (`haiku`, `sonnet`, `opus`) are not copied into Codex agent files.
- Claude `effort: max` and `effort: xhigh` are preserved only as `model_reasoning_effort = "high"` in generated custom agent TOML files.
- Built-in Codex agents are `default`, `worker`, and `explorer`; use them when no migrated specialist matches.
- Subagents inherit the active sandbox and approval policy unless a Codex custom agent explicitly overrides supported config.

## Notes

- The original Claude files were copied from `~/.claude/agents`; do not edit the Claude source files.
- The Codex copies live under `~/.codex/skills/claude-subagent-library/references/agents/`.
- Prefer existing Codex system/developer instructions over conflicting Claude-specific tool names or permission modes.

## Available References

- `references/agents/code-reviewer.md`
- `references/agents/security-reviewer.md`
- `references/agents/debugger.md`
- `references/agents/test-writer.md`
- `references/agents/task-planner-analyzer.md`
- `references/agents/modular-code-architect.md`
- `references/agents/code-cleanup-optimizer.md`
- `references/agents/academic-planner.md`
- `references/agents/academic-reviewer.md`
- `references/agents/academic-writing-assistant.md`
- `references/agents/report-planner.md`
- `references/agents/report-reviewer.md`
- `references/agents/paper-*.md`
- `references/agents/experiment-*.md`
- `references/agents/humanize-*.md`
- `references/agents/claude-for-dslab/*.md`

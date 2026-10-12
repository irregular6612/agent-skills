---
name: claude-command-library
description: Reuse, inspect, adapt, or run migrated Claude Code slash commands from ~/.codex/commands inside Codex.
---

# Claude Command Library

This skill exposes migrated Claude Code slash command prompts as Codex reference material.

## Workflow

1. Match the user's requested command or workflow to a file under `references/commands/`.
2. Read only that command file and any directly referenced sibling command files needed for the task.
3. Execute the workflow using Codex tools and current system instructions.
4. Treat Claude-only slash command syntax, inline command injection, or tool names as guidance, not as executable Codex configuration.

## Notes

- The original Claude files were copied from `~/.codex/commands`; do not edit the Claude source files.
- The migrated command files are references, not Codex slash commands.
- Prefer installed Codex skills when they cover the same workflow more directly.

## Available References

- `references/commands/autoresearch.md`
- `references/commands/autoresearch/plan.md`
- `references/commands/autoresearch/probe.md`
- `references/commands/autoresearch/debug.md`
- `references/commands/autoresearch/fix.md`
- `references/commands/autoresearch/learn.md`
- `references/commands/autoresearch/reason.md`
- `references/commands/autoresearch/predict.md`
- `references/commands/autoresearch/scenario.md`
- `references/commands/autoresearch/security.md`
- `references/commands/autoresearch/ship.md`
- `references/commands/humanize.md`
- `references/commands/humanize-redo.md`

# agent-skills

Personal agent configuration for Claude Code and Codex, kept in one repository.

Source of truth for skills, subagents, hooks and commands that I author and
maintain. Third-party skills installed from other marketplaces are deliberately
not mirrored here.

Repository: https://github.com/irregular6612/agent-skills

## Layout

```
.claude-plugin/marketplace.json   Claude Code marketplace manifest (4 plugins)
claude-code/
  juhyeon/                        my own plugins and skills
  karpathy/                       third-party, kept for reference
  K-dense-AI/                     third-party, kept for reference
codex/
  skills/                         Codex mirrors of the same skills
  agents/                         Codex subagent definitions (.toml)
  AGENTS.md                       global Codex instructions
```

## Claude Code

Four plugins are published from `claude-code/juhyeon/`:

| Plugin | Skills | Subagents | Hooks |
|---|---|---|---|
| `paper-workflow` | paper-radar, paper-driller, paper-understand | 7 | 2 |
| `paper-writing` | paper-section-rewrite, paper-readability-review, paper-digest | – | – |
| `paper-banana` | paper-banana | – | – |
| `juhyeon-misc` | auto-code, humanize, iterative-academic-writer, autoresearch | 9 | – |

Install:

```bash
claude plugin marketplace add irregular6612/agent-skills
claude plugin install paper-workflow@juhyeon
```

Enable or disable a single plugin without reinstalling:

```bash
claude plugin disable paper-workflow@juhyeon
claude plugin enable  paper-workflow@juhyeon
```

Inspect what a plugin contributes and what it costs in context:

```bash
claude plugin details paper-workflow
```

## Codex

Codex has no plugin system. `codex/skills/` and `codex/agents/` mirror the same
material as flat directories; copy or symlink them into `~/.codex/`.

The Codex mirror lags the Claude Code side — `paper-radar`, `paper-understand`,
`auto-code` and `autoresearch` have no Codex counterpart yet, and
`codex/skills/paper-banana/` carries only `SKILL.md` because the 241 MB engine is
already vendored under `claude-code/juhyeon/paper-banana/`.

`codex/agents/` mirrors only the subagents an owned skill actually dispatches.
The other 20 `.toml` files under `~/.codex/agents/` belong to deleted skills or
to the flat directories kept for reference, and are deliberately not tracked.

## Conventions

- Directories under `claude-code/` are grouped by original author. `juhyeon/` is
  mine; the others are vendored copies kept for reference and are not published
  as plugins.
- Subagents that a plugin owns live in `<plugin>/agents/`. Claude Code registers
  them namespaced as `<plugin>:<agent>`, so dispatch by the prefixed name.
- Hooks live in `<plugin>/hooks/hooks.json` and address their handlers through
  `${CLAUDE_PLUGIN_ROOT}` rather than an absolute path.
- Secrets never enter the repository. `.env` files, virtualenvs and generated
  outputs are excluded in `.gitignore`.

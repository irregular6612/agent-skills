# paper-workflow

Discovery → pre-read note → study loop for research papers.

## Skills

- `paper-radar` — repeatable interest-track sweep. Collects candidates, dedupes
  against previous radar state and the existing wiki, ranks by learning value,
  and writes a private digest.
- `paper-driller` — turns one paper into an evidence-traced pre-read note.
- `paper-understand` — multi-session tutor over an existing note.

Handoff between them is file-based (`_wiki/radar/state.json`), so each skill
still works when the others are not installed.

## Subagents

`paper-driller` fans out to seven subagents. Dispatch them by their namespaced
names:

| Agent | Model / effort | Used by |
|---|---|---|
| `paper-workflow:paper-preread-analyst` | sonnet / high | preread (default) |
| `paper-workflow:paper-spine` | opus / max | deep |
| `paper-workflow:paper-section-driller` | sonnet / xhigh | deep |
| `paper-workflow:paper-digest-composer` | opus / max | deep |
| `paper-workflow:paper-evidence` | sonnet / xhigh | deep |
| `paper-workflow:paper-comparison` | sonnet / xhigh | deep |
| `paper-workflow:paper-meta` | haiku | deep |

## Hooks

- `PostToolUse` on `Write|Edit|MultiEdit` — validates paper notes against
  `skills/paper-driller/references/paper-schema.json`.
- `SubagentStop` — appends subagent identity to `~/.claude/logs/paper-driller-qc.jsonl`.

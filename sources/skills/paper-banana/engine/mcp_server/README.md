# PaperBanana MCP Server — local canonical engine

The engine under this skill is shared by Claude and Codex. Discovery of the skill does not register or start an MCP server. Registration is a separate, explicitly approved operation. `setup` neither registers MCP nor copies credentials.

## Prepare locally

Resolve `SKILL_ROOT` to the directory containing the discovered `SKILL.md`. Prepare its environment with `uv sync --extra mcp` in `SKILL_ROOT/engine` if dependency installation is authorized. The engine's `.env` is machine-local and ignored by Git. Obtain credentials through the active harness's secure configuration workflow, never through committed examples.

Do not use unpinned `uvx --from paperbanana[mcp]` as a reproduction of this canonical engine: that downloads a different release.

## Thin native registration adapters

```bash
claude mcp add --scope user --transport stdio paperbanana -- uv --directory "$SKILL_ROOT/engine" run paperbanana-mcp
codex mcp add paperbanana -- uv --directory "$SKILL_ROOT/engine" run paperbanana-mcp
```

The command argv is the same. Only native registration/config syntax differs. Use an absolute path: config files do not expand the literal `${SKILL_ROOT}` placeholder.

Read back without invoking model generation:

```bash
claude mcp get paperbanana
codex mcp get paperbanana --json
```

Registration readback does not prove the server connects or model providers work. A generation or evaluation tool may use paid providers. Never run it without separate authorization.

The tools are `generate_diagram`, `generate_plot`, `evaluate_diagram`, and `download_references`; use the names actually exposed by the active client. Claude prefixes such as `mcp__paperbanana__` are not a Codex API promise. Model defaults and provider configuration are shared in the engine; native adapter syntax does not change them.

## Removing an explicitly registered server

```bash
claude mcp remove --scope user paperbanana
codex mcp remove paperbanana
```

This is outside installer rollback ownership. Preserve preexisting MCP entries and secrets. Local `.venv`, `.env`, outputs, and known Python bytecode under `paper-banana/engine` are runtime state, not vendored source.

Current model availability, price, connection, generation quality, and provider execution are unverified in the SSOT installation tests.

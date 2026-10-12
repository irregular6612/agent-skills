# F11–F12: regenerated cache preservation and explicit engine bytecode

Implementation candidate only. Independent exact-HEAD approval is required
before actual HOME reapplication. These tests use fake HOME and workspace clones.

## F12: minimum explicit runtime policy

F8's opaque `sources/skills/paper-banana-claude/engine/.venv` boundary remains.
F12 additionally permits `__pycache__` immediately below these 11 existing engine
Python package directories, and nowhere else:

- `mcp_server`
- `paperbanana`
- `paperbanana/agents`
- `paperbanana/core`
- `paperbanana/data`
- `paperbanana/evaluation`
- `paperbanana/guidelines`
- `paperbanana/providers`
- `paperbanana/providers/image_gen`
- `paperbanana/providers/vlm`
- `paperbanana/reference`

The full prefix is `sources/skills/paper-banana-claude/engine/`. These are the
parents of the currently tracked engine Python modules. New packages do not
receive automatic exceptions. A runtime root and every parent must be real
directories. Git must prove the root is ignored and that no indexed descendant
exists, including forced `git add -f`. Without a Git index, proof fails closed.
Only root metadata, index and ignore rules are inspected; no runtime payload is
read or traversed. A normal source selection can skip these opaque execution
subtrees, but directly selecting any PRIVATE path as a manifest asset still
fails. All other PRIVATE names, denylisted names, source symlinks and nonregular
entries remain rejected. Runtime contents are never copied, published or deleted
by setup. `.gitignore`, sources, manifest, templates and immutable lock are
unchanged.

## F11: provenance before automatic quarantine

The native adapter checkpoints the exact retired selector in its moved cache
record before moving the original. This is limited to non-pinned `superpowers`
or `bagjuhyeon-agent-ssot@generated-local-cache` at the exact corresponding native
cache path. Ordinary moved files/directories and old tombstones without that
selector evidence keep the old occupant-refusal behavior. There is no implicit
migration of the failed previous journal; the operator already rolled that HOME
back and a new installation creates the new records.

A regenerated leaf is accepted only with an existing original backup, safe
real-directory root/parents, and nonempty revision directories containing regular
`.claude-plugin/plugin.json` or `.codex-plugin/plugin.json` metadata whose name
matches the recorded selector and whose version is a nonempty string. Unknown
root entries, unrelated plugin names, symlink revision/metadata roots, malformed
metadata, selector/path mismatch, pinned selectors and absent backups fail closed.
No cache source is imported into the repository.

The whole regenerated tree is renamed to a fresh private
`$HOME/.agent-skills-setup/quarantine/N`. Payload files and user modifications
inside a recognized revision are preserved, not edited or deleted. They are not
merged with the original backup and are not restored over it. An unrelated root
occupant that lacks recognized metadata is refused without writes. The matching
metadata does not prove who produced a tree; setup makes no such attribution.

Before rename, the journal stores the unique quarantine destination and source
device/inode/mode/size/mtime identity. A fresh process can finish a rename that
never happened or recognize one that happened before its checkpoint. A changed
root identity, occupied destination, unsafe destination or simultaneous old/new
occupants fails closed. Completed quarantine paths remain in state after
uninstall; setup does not remove them. Original restore uses the existing F9
checkpoint and backup. A second successful uninstall is an exact no-op.

Dry-run only validates and prints proposed quarantine/restoration. It does not
write a journal, rename data or invoke native CLIs. `--validate` validates source
policy only, not HOME state. Install/uninstall check managed user modifications
before proceeding. The native adapter rechecks cache paths and reconciles
recognized regenerated caches before/after native operations.

## Execution and limits

- `tests/live_regenerated_cache.py --repo BASELINE --baseline` first reproduces
  F11 dry/rerun/uninstall-dry exit2 and F12 validate/dry/rerun exit2 on approved
  F8–F10 HEAD `1c88a07301a5b0ecf6fb550f6ea39ba4e904ecda`.
- `tests/live_regenerated_cache.py` exercises real local native retirement,
  deterministic regeneration, backup/quarantine preservation, native list
  readback, original registry bytes/mode/mtime, no-op rerun and second uninstall.
  F12 uses actual `py_compile` without importing/executing engine code.
- `AGENT_SKILLS_F11_F12=1 python3 tests/live_native_discovery.py` uses actual
  `compileall` in all 11 package directories plus cache regeneration, then
  Claude control initialization and Codex app-server skills/config readback.
  It asserts dry/rerun no-op after both CLI readbacks and exact original
  controlled config restoration. No user/model turn is submitted.
- `tests/test_regenerated_cache.py` contains synthetic safety/protocol tests,
  including both cache formats, official-selector path, forced tracked runtime,
  PRIVATE selection, unsafe paths, user edits and interrupted quarantine.
  These unit fixtures are not presented as actual native behavior.
- The Claude CLI reserves `claude-plugins-official` for approved Anthropic GitHub
  sources. Actual CLI tests use `generated-local-cache`; the official selector
  path is covered by protocol fixtures. Native generation is not inferred from
  these deterministic injections.
- Authenticated Codex curated registration uses the existing protocol fixture
  policy in isolation. Actual HOME remote catalog checks belong to the operator.
  No HOME/auth/history/internal database is copied. Public pinned-plugin downloads
  may occur; no paid API, external publication/push or launchd changes occur.
- Inode checkpoint/revalidation is not a proof of race-free operation with
  external processes modifying descendant payloads. No lock covers native
  external writers. Unsafe observed conflicts are refused; an externally
  modified recognized payload is preserved as a whole, not declared original.
  Native cache subtree byte identity, actual agent execution, hooks, semantic
  divergent snapshot integration and taste-skill immutable revision remain
  unverified or unresolved.

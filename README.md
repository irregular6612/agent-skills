# agent-skills: item-symlink SSOT

Install from a durable checkout outside iCloud:

```bash
git clone https://github.com/irregular6612/agent-skills ~/Workspace/agent-skills
cd ~/Workspace/agent-skills
./setup --dry-run
./setup
```

`./setup` uses macOS Bash and Python 3 stdlib. It requires the Claude and Codex
native plugin CLIs on PATH for a full installation; missing CLIs fail explicitly.
No global Python package installation, paid API, launchd changes, or publishing.
`--assets-only` is an explicit offline asset test mode, NOT a complete plugin setup.

## Contract

- `manifest.yaml` (JSON-compatible YAML) enumerates item symlinks. The complete
  `skills`, `agents`, `commands`, or `prompts` roots are never linked wholesale.
- `sources/` contains approved canonical originals and explicit harness variants.
  Claude/Codex exact-match scientific skills share one original. Actual differing
  snapshots retain overlays; copied mtimes are not evidence of which is newer.
  See `docs/SYMLINK-INVENTORY.json` and `docs/HARNESS-VARIANTS.json`.
  Current correction decisions and active counts are in `docs/SETUP-CORRECTIONS.md`;
  historical inventories are provenance, not the current installation manifest.
- `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` link to `sources/instructions/`.
  The current inventory confirmed an empty Claude guideline; the existing repo
  Codex guideline is preserved. A different future machine's existing guidelines
  are backed up, never silently imported into or used to overwrite the checkout.
- Codex TOML agents link individually and their `config_file` entries are merged
  into config.toml. Claude commands are exposed as Codex reference prompts;
  this is not a claim that every Claude command is natively executable in Codex.
- `templates/claude-settings.json` shares owned paper hooks and permission rules;
  `templates/codex-config.json` shares agent/plugin declarations. Existing machine
  config, unknown keys, permissions, comments in TOML, and project trust stay local.
  Config files remain regular files, never symlinks. Single-quoted scalar keys
  are supported. Managed dotted keys, inline tables, array tables, and target
  multiline values fail before ANY HOME/native writes on Python 3.9 and 3.12.
  Use explicit `[agents.role]` tables with scalar assignments for managed fields.
  Python 3.11+ additionally validates full TOML with tomllib. Both macOS-default
  Python 3.9.6/Bash 3.2 and Python 3.12 were exercised in this run.
- Destinations are checked after Unicode NFD normalization and case folding,
  including overlapping paths. This portable conservative policy rejects aliases
  even on case-sensitive filesystems, without writing a probe into HOME.
- Claude skills and slash-command wrappers share a native command namespace.
  Managed names must be unique across both categories before any HOME/native writes.
  `/humanize` remains the unchanged skill; use `/humanize-command` for the explicit
  text/file wrapper and `/humanize-redo` for a second pass. Approved old
  `commands/humanize.md` copies/links are backed up and retired, then restored with
  their original bytes/link/mode/mtime on uninstall. The old command source stays
  unchanged as an approval snapshot; modified copies/links fail before any writes.
  Unknown/external assets outside those explicit managed paths remain untouched.
- Claude native agent names must be unique. Three byte-identical prompt bodies
  share canonical definitions; the different DSLab reviewer is named
  `dslab-academic-reviewer`. `retired_links` backs up/removes approved old aliases
  and restores them on uninstall; modified aliases fail before any writes.
- `.system`, unrelated plugin caches, external taste-skill links, agentcat-usage,
  lost-me and other unclassified assets are preserved. Exclusion is NOT deletion
  of a user's preexisting denylisted skills/plugins.
- `dependencies/lock.yaml` pins superpowers at immutable upstream commits:
  Claude v6.4.1 and Codex v6.4.2. Metadata-only native catalogs select those commits
  as `superpowers@ssot-pinned`. Upstream plugin payloads live only in each
  harness's native cache, never vendored by setup into the repo. Other superpowers
  registrations and the old copied `bagjuhyeon-agent-ssot@generated-local-cache`
  registration are backed up/retired through the native CLI. Obsolete dedicated
  catalogs containing only those plugins are also backed up/unregistered and read
  back, even if their plugin is already gone. Mixed/unrelated catalogs and those
  used by unrelated installed plugins remain untouched. Uninstall restores exact
  registry bytes and native catalog caches, then reads back marketplace names/sources.
- Auth/credentials/tokens, history, sessions, projects/memory, logs, cache, SQLite,
  `.DS_Store`, and the denylist are never imported from HOME. Only the explicit
  config/registry files needing reversible changes are backed up locally.

## Backup, restore, and editing

Real conflicting items, including dangling or external symlinks, are moved (not
recursively deleted) into `$HOME/.agent-skills-setup/backups/`. The journal maps
original locations to backups. Each move and the restore command are printed.
The state and backups are local-only; never add them to Git.

```bash
./setup --uninstall
```

Uninstall removes only links this checkout created and restores exact original
files/symlinks/configs/plugin caches. Already-correct preexisting symlinks are not
claimed and remain after uninstall. User edits to managed local config or a
replaced link fail closed before further writes; save your local edits, restore
that managed file/link to its installed state, then retry uninstall. Repo edits
are immediately visible through the item links without reinstalling. Add a new
manifest item and rerun setup to create a new link.

Native cache regeneration is not attributed to a particular process. Setup
recognizes only a previously retired selector/path recorded in its journal and
a real cache tree whose revision directories contain matching plugin metadata.
It preserves the whole regenerated tree under local `quarantine/`, separately
from the ORIGINAL backup. It never merges it with or restores it over the
original. The rename is journaled for retry before/after interruption. Unknown
leaf contents, symlink roots/parents, missing backups and modified managed
configs still fail closed. Older tombstones without selector evidence are not
automatically upgraded. See `docs/SETUP-REGENERATED-CACHE.md` for exact limits.
Native-generated bootstrap state (e.g. `.claude.json`, CLI logs, or empty cache
directories) is
harness-owned and is deliberately not collected, deleted, or byte-restored.
Uninstall restores controlled config/registrations and original conflict items,
not the entire HOME snapshot. The rollback journal is not a crash-proof filesystem
transaction; interrupted I/O/native commands may need inspection of the printed
backups before retry. Never delete backups merely to bypass a conflict.

`--dry-run` reads local metadata only and makes no filesystem/network/native CLI
changes. It prints only proposed changes, and prints nothing on an already fully
installed fixture. Network/plugin errors return nonzero, never fabricated success.
A partial native installation retains a journal for `--uninstall`.

## Layout and verification

```text
setup                           single command entrypoint
tools/setup_symlinks.py          path checks, journal, links, config merge/restore
tools/setup_plugins.py           native pin, duplicate cleanup/readback/restore
manifest.yaml                   item destinations + provenance
sources/{skills,agents,commands,instructions,hooks}/
templates/                      whitelisted shared config only
dependencies/lock.yaml           immutable plugin coordinates + unresolved packs
dependencies/marketplaces/       native catalog metadata, no plugin payload
policy/denylist.yaml             matt-pocock/mattpocock/auto-code exclusions
docs/inventory/t_8f75d661/        upstream read-only migration/inventory evidence
```

The historical `claude-code/` and `codex/` trees remain reference material for the
previous marketplace layout. They are NOT setup inputs; only manifest sources
are active SSOT originals. The denylisted legacy auto-code tree is removed from
the current checkout/package (history remains). No old marketplace installation
is needed for owned direct-link assets. Codex now has a native plugin system;
the prior README claim that it did not is obsolete.

```bash
./setup --validate
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
# Isolated native CLI/network tests (no model calls or paid API):
python3 tests/live_native_smoke.py
python3 tests/live_native_duplicates.py
python3 tests/live_native_marketplaces.py
python3 tests/live_native_discovery.py
```

Independent fresh-clone and actual-home release validation belong to the
pre-created dev-verifier/dev-operator cards. Do not treat these implementation
self-tests as release approval, and do not push this implementation automatically.

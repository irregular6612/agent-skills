# Claude shared marketplace ownership

## Scope and record

`known_marketplaces.json` is a shared registry, not a setup-owned whole file. Other
files (`settings.json`, `installed_plugins.json`, Codex config) retain their existing
whole-file protections. No force/adopt mode is added.

The version-1 installer journal can contain a `kind: marketplaces` record, with
`marketplaces: 1` as its entry-scoped schema version. Its `installed` map includes
only `ssot-pinned` and the names of dedicated marketplaces this setup retired.
Each name maps to an expected source identity and installLocation, or to `null`
when that name must remain absent. Source identity compares `source`, `path`,
`url`, `repo`, `ref`, `sha`, and `subdir`, including presence/absence. It excludes
unknown source fields. Entry `lastUpdated`, `autoUpdate`, and unknown fields are
not ownership expectations. Other marketplace names are not expectations.

The `original` map stores complete original entries for those names only.
`original_digest` authenticates the original backup bytes. The untouched original
backup remains in `backups/N` after rollback. Journal archives remain in
`marketplace_journal_archive`. Setup-created entries removed on rollback are also
retained in `marketplace_archive`, including externally added metadata.

## Writes and rollback

Initial capture copies the original registry without moving it out of the shared
location. Before native pin-add or retirement, the journal durably stores the
expected final entries and `pending` before-state identities. During an interrupted
operation, each affected entry must match its exact before or expected after state.
New setup is refused until `--uninstall` completes rollback. Native command readback
checks source expectations, and finally blocks never rehash/adopt arbitrary
marketplace changes. Mutating Claude commands can themselves drop unknown fields
from unrelated entries. A durable `native_overlay` captures the pre-command registry.
After command readback, missing non-runtime fields and unknown source fields are
reinserted. Harness `lastUpdated`/`autoUpdate` values remain current. Unrelated
source changes or removed unrelated entries are refused, not adopted. Interrupted
overlay repair is resumed before rollback; normal setup refuses that pending phase.
A successful operation removes `pending` after exact semantic readback.

Uninstall removes the setup-created pin directly from current JSON rather than
invoking a marketplace removal command that could delete a repository catalog.
It restores only missing retired entries from the verified original backup.
Preexisting owned entries retain current metadata and unknown fields. Unrelated
entries retain their current semantic values. Same-name re-registration of a
retired entry is a conflict, including an entry identical to its original value.
Different source/installLocation, removal of an expected entry, duplicate JSON
keys, malformed entry shapes, symlinks, or changed original backups are refused.

A durable `rollback` checkpoint permits either pre-rollback expectations or the
original entry projection after atomic replacement. A durable `write_pending`
digest identifies a setup-written leftover temporary file. Unknown temporary files
are never removed. Before replacement, current bytes are reread to detect concurrent
writes. Restart tests exercise both sides of `os.replace` in a new interpreter.
Audit backups use unused numbered slots, so reinstall does not overwrite them.

## Legacy migration

A hash-only file record migrates only when native flags establish the ownership
names and a historical witness matches the existing installed SHA-256 exactly.
The witness is either current bytes themselves, or current bytes with only JSON
`<marketplace>.lastUpdated` string values replaced by values actually present in
the original backup. The JSON path-aware replacement keeps all other bytes,
ordering, whitespace, and values intact. Arbitrary timestamp removal or semantic
similarity is not evidence. Missing witness, whitespace drift, user additions, or
source changes before migration remain safe refusals. After migration, equivalent
whitespace and unrelated additions are accepted by entry-scoped checks.

Migration also checks that a setup-created `ssot-pinned` did not exist in the original
backup and points exactly to this repository's Claude catalog. Preexisting pins
must have unchanged source identities. Retired names must have original entries
and be absent in the reconstructed installed state. The old record and hash witness
are retained, not overwritten by a current-file hash. Dry run stages migration only
in memory and never writes the journal. Normal installer saves persist the staged
record after preflight; no external script directly edits state.

## Explicit limits

- A setup-created entry must be removed as a registration. Its added metadata
  cannot remain in the active registry under that name; the complete observed
  entry is archived. Surviving entries retain runtime/unknown fields in-place.
- Semantic preservation does not mean JSON whitespace, key order, mtime, or inode
  preservation during actual rollback. Registry mode is preserved. No whole-file
  backup is blindly restored and no registry/cache file deletion is introduced.
- External native writers do not honor setup's lock. A narrow race between the
  final reread and atomic replacement remains. Apply only while harness writers
  are stopped; this implementation does not claim cross-process transactional
  isolation with Claude.
- Removing and re-adding `ssot-pinned` with precisely identical semantic source
  identity cannot be distinguished from the original registration without external
  provenance. Different source or a reoccupied retired name is refused.
- Native `claude plugin marketplace add` also changes `settings.json`. That separately
  hash-managed file can still refuse setup. Registry-only additions pass; this change
  does not authorize adoption of settings changes or widen ownership to settings.
- Native/runtime interpretation of future unknown source fields is not known.
  Their values are preserved, not treated as evidence to change known source identity.
- Crash before an initial backup copy/journal capture completes can leave an unused
  audit backup. It is not overwritten or automatically adopted.

Actual HOME application requires independent verifier approval and a separate
operator application approval. This implementation is only a workspace candidate.

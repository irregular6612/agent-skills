# F8–F10 runtime and native rollback corrections

Historical F8–F10 implementation evidence follows. F12 extends the runtime
policy and F11 journals regenerated-cache preservation; the current contract is
in `SETUP-REGENERATED-CACHE.md`. The isolation/authentication limits below remain.

This is an implementation candidate, not a release approval. The authenticated
Codex `superpowers@openai-curated-remote` roundtrip is still unverified. A fake
HOME returns `chatgpt authentication required for remote plugin catalog`; the
name is reserved, so a local marketplace cannot substitute for that catalog.
Actual HOME/auth/history/internal databases must not be copied to bypass this.
An independent gate must resolve this before actual HOME reapplication.

## F8: explicit local execution-state boundary

Only `sources/skills/paper-banana-claude/engine/.venv` is an opaque local runtime
boundary. Its root and all parents must be real directories, not symlinks. Git
must confirm that the subtree is ignored and that no indexed payload exists,
even if somebody used `git add -f`. Validation checks only the index, ignore
rule and root metadata. It does not read or traverse runtime contents.

This is not a relaxation for shareable sources: selecting `.venv` itself in a
manifest still fails `relative()`. All other PRIVATE names, denylisted names,
source symlinks and nonregular entries remain rejected. The venv may contain
its normal interpreter links because these are local execution state, not
validated/imported source assets. A source skill is still linked item-by-item;
source originals, manifest namespace, templates and dependency coordinates are
unchanged. Setup does not delete the runtime. No runtime payload is committed,
vendored, imported from HOME, or included in `git archive`/bundle artifacts.

A tar-only checkout with no Git index cannot establish ignored/untracked runtime
ownership and fails closed if this runtime boundary exists. Use the bundle
checkout for execution with a local venv. This deliberately narrow exception is
not a generic cache/.venv/private-content bypass. New runtime locations need
an explicit policy review rather than automatic exclusions.

## F9: original cache parents and crash-resumable rollback

`Installer.restore_parent()` recreates missing ancestors only for a verified
journal destination. It checks symlinks and non-directory components again
before creating anything. Original parents are not claimed as setup-created
cleanup directories. Unrelated files or destination occupants are not replaced.

Before an original backup is renamed, the record checkpoints `restoring` with
its device/inode/type/size/mtime identity. Resume accepts a missing installed
leaf while the verified backup remains. It also recognizes a completed rename
whose journal removal was interrupted. Original files/directories are not
unlinked twice. A modified restored item fails the identity check.

Native rollback checkpoints `removed` instead of deleting native expectations.
Original marketplace names/locations and Codex plugin metadata remain in the
journal through interrupted file restoration and failed native verification.
Setup install refuses an in-progress rollback; `--uninstall` is the resume path.
The second successful uninstall remains an exact no-op.

The actual-CLI local fixture did not itself remove the empty Claude cache
parent. The test explicitly removes that empty synthetic parent to reproduce
the operator-observed precondition, then injects a rename failure. This is not
claimed as proof of the native process responsible for the original deletion.

## F10: native registration is not just config/cache bytes

Before retirement, Codex's actual plugin list is reduced to selector, version,
enabled state, supported source coordinates and exposed commit metadata.
Uninstall restores files, asks the supported CLI for the actual installed list,
and re-adds a missing retired selector using `codex plugin add SELECTOR --json`.
It never reads/resets/copies native internal databases or auth/history files.
It then requires the original selector set, version, enabled state and exposed
immutable coordinates. Already-present wrong versions/commits are rejected,
not overwritten. Missing unrelated original plugins are not silently re-added.

Native verification saves controlled original registry/config files in private
local state, restores their original bytes/mode/mtime after CLI writes (including
failed CLI writes), and preserves disabled original states. The snapshots and
metadata survive a failed verification so a fresh process can retry. A user
config byte change on retry is rejected before further CLI work. Old Codex
journals without original plugin metadata cannot prove this guarantee and fail
closed instead of declaring a config-only restoration successful.

If the remote catalog has moved and supported CLI installation cannot reproduce
the recorded original version/commit, verification fails with the journal
retained. This does not invent a version-pinning option that the CLI lacks.
Reinstallation does not guarantee original cached subtree byte identity;
original selector/version/source/config restoration is a different guarantee.

## Executed checks

- Python 3.9.6 and 3.12.8: 70 regressions each, including all prior 48 F1–F7 tests
  and 22 new F8–F10 tests; both exit 0.
- Approved F7 clone: independent synthetic F8 rejection, F9 missing-parent failure
  and lost native expectations, F10 config-only verification missing a deliberately
  unregistered plugin; assertions passed.
- Actual supported CLI local fixtures: F8 validate/dry-run/rerun/uninstall after
  runtime creation; F9 safe parent recreation and interrupted resume; F10
  `superpowers@original-immutable-fixture` v6.4.2, original Git SHA
  `8ca22dba9a94f28898bbce59f2537ff4d87c747d`, config bytes/mode/mtime and plugin
  metadata restored. Each defect uses a separate fake HOME. Exit 0.
- Exact `superpowers@openai-curated-remote`, including original disabled state,
  failed-CLI retry and wrong version/commit rejection: protocol fixtures only,
  not actual authenticated remote native discovery.
- Existing actual native discovery: Claude skill30/command2/agent31 exact metadata,
  Codex skill35/role34 config_file, link138, collisions0, zero model turns. Exit 0.
- Existing actual duplicate and dedicated/mixed/unrelated marketplace roundtrips,
  native smoke and dry-run/rerun/second uninstall checks: exit 0.

No actual HOME/source repo edits, external publishing/push, paid API/model turns,
launchd changes, auth/history/database reads or exports were performed.
Divergent snapshot semantic merging and taste-skill immutable revision remain
out of scope and unresolved, as in the original release.

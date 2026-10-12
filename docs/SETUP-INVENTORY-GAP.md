# F13: Codex metadata / native inventory disagreement

## Policy

A retirement candidate in Codex config/cache is not proof that Codex currently owns an installed plugin. Full setup refuses when `local_plugins()` finds a retired selector which is absent from actual `codex plugin list --json`. The error names the selector and states that config/cache are preserved.

This check runs in preflight before installer-created harness directories, journal entries, managed assets/config edits, or native registration mutations. It also runs at native install entry and after retirement readback, so a residual metadata-only candidate cannot be reported as successful retirement. CLI list itself can create bootstrap metadata or update native caches; this policy does not claim native reads are filesystem-pure.

No metadata-only record is promoted to native retirement provenance. No cache is moved, deleted, or quarantined on this refusal path. PRIVATE content and symlinks are not granted new permissions. Existing ownership checks and F11 quarantine remain unchanged.

Dry-run remains metadata-only and does not call native CLIs. A pre-install dry-run is a proposed plan, not ownership confirmation or a guarantee that real setup can proceed. When actual inventory disagrees, real setup exits 2 rather than succeeding and leaving a permanent dry-only retirement. After a successful full install and native readback, both dry-run and real rerun must be no-ops. Assets-only is still explicitly offline and is not full setup.

## Tests

- `tests/test_inventory_gap.py`: protocol fixtures verify refusal before any installer writes, visible retirement allowance, disabled/generated candidates, already-exact pin, unrelated/pinned metadata exemption, read-only dry-run, and symlink protection.
- `tests/live_inventory_gap.py`: actual Claude/Codex CLIs in fresh fake HOMEs. Synthetic local and curated-selector metadata are absent from native inventory; setup refuses repeatedly and preserves original config/cache bytes, mode, mtime and symlinks. Two uninstalls are exact no-ops. A separate healthy install verifies both actual CLI readbacks, dry/rerun/dry no-ops, original config restoration and exact second uninstall.
- The curated-selector fixture contains no authentication or DB copied from real HOME. It is not a test of authenticated curated APIs or restoration on the user's real HOME.

The full F1–F12 suites and actual local CLI/discovery suites remain required on both Python 3.9 and 3.12. Actual HOME rollout stays on hold until independent verification approves this exact candidate and the operator's separate release conditions are met.

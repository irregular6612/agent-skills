#!/usr/bin/env python3
"""Phase 9: Apply converted fragments to main.tex atomically.

Reads the plan, validates main.tex hasn't changed since planning (SHA1
match), backs up main.tex to main.tex.bak.<timestamp> (rotates to keep
last 5), replaces each `% MD-INJECT: <id>` ... `% MD-INJECT-END` block's
body with the corresponding fragment, and atomically replaces main.tex.

Usage:
  md_inject_apply.py --plan .build/md_inject/plan.json
                     [--dry-run]
                     [--no-backup]
                     [--force]           # skip sha1 check
                     [--json]

Exit codes:
  0  applied (or dry-run printed diff)
  1  fragments missing for one or more injections
  2  main.tex sha1 mismatch (without --force) or plan invalid
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


# ── Marker regex (mirrors md_inject_plan.py) ────────────────────
import re

_MARKER_START_RE = re.compile(r"^%\s*MD-INJECT:\s*(\S+)\s*$")
_MARKER_END_RE = re.compile(r"^%\s*MD-INJECT-END\s*$")


@dataclass
class ApplyReport:
    target: str
    backup: str | None = None
    n_applied: int = 0
    n_missing_fragments: int = 0
    n_preamble_lines_added: int = 0
    n_usepackage_added: int = 0
    auto_bib_paths: list[str] = field(default_factory=list)
    dry_run: bool = False
    diff: str = ""
    warnings: list[str] = field(default_factory=list)


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _rotate_backups(target: Path, keep: int = 5) -> list[Path]:
    backups = sorted(target.parent.glob(f"{target.name}.bak.*"), reverse=True)
    to_delete = backups[keep:]
    for b in to_delete:
        try:
            b.unlink()
        except OSError:
            pass
    return backups[:keep]


def _make_backup(target: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = target.parent / f"{target.name}.bak.{stamp}"
    backup.write_bytes(target.read_bytes())
    _rotate_backups(target)
    return backup


def _load_fragment(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _aggregate_meta(plan: dict) -> tuple[list[str], list[str], list[str]]:
    r"""Scan each injection's meta.json and collect:
      - required_packages (deduped, order preserved across fragments)
      - preamble_snippets (deduped by first 80 chars; Round 4.5+)
      - auto_bib_paths

    Returns (pkg_usepackage_lines, preamble_snippet_blocks, auto_bib_paths).
    """
    packages: list[str] = []
    seen: set[str] = set()
    snippets: list[str] = []
    seen_snip: set[str] = set()
    bibs: list[str] = []
    for inj in plan.get("injections") or []:
        meta_path = Path(inj.get("meta_out") or "")
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for pkg in meta.get("required_packages") or []:
            if pkg and pkg not in seen:
                seen.add(pkg)
                packages.append(pkg)
        for snip in meta.get("preamble_snippets") or []:
            # De-duplicate via the first 80 chars of the snippet body so
            # two fragments emitting the same \lstset{...} block don't
            # pollute the preamble with duplicates.
            key = snip.strip()[:80]
            if key and key not in seen_snip:
                seen_snip.add(key)
                snippets.append(snip)
        bib = meta.get("auto_bib_path")
        if bib and bib not in bibs:
            bibs.append(bib)

    pkg_lines = [f"\\usepackage{{{p}}}" for p in packages]
    return pkg_lines, snippets, bibs


def _publish_auto_bibs(auto_bibs: list[str], target_dir: Path) -> list[tuple[str, str]]:
    r"""Copy each auto-generated .bib from the build cache into ``target_dir``
    so BibTeX can resolve ``\bibliography{<stem>}`` without needing a
    ``BIBINPUTS`` environment variable.

    Returns list of ``(src, dst)`` pairs that were actually (re)published
    — entries whose source is already identical to an existing dst are
    skipped silently.
    """
    published: list[tuple[str, str]] = []
    for src_str in auto_bibs:
        src = Path(src_str)
        if not src.exists():
            continue
        dst = target_dir / src.name
        # Idempotency: if dst already matches src byte-for-byte, skip.
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            continue
        shutil.copy2(src, dst)
        published.append((str(src), str(dst)))
    return published


def _find_marker_regions(tex_text: str) -> list[tuple[str, int, int]]:
    """Return list of (marker_id, start_line_idx, end_line_idx) for each
    paired marker. Line indices are 0-based in the splitlines() list,
    pointing at the `% MD-INJECT:` and `% MD-INJECT-END` lines themselves.
    """
    out: list[tuple[str, int, int]] = []
    stack: list[tuple[str, int]] = []
    for i, line in enumerate(tex_text.splitlines()):
        ms = _MARKER_START_RE.match(line.rstrip())
        me = _MARKER_END_RE.match(line.rstrip())
        if ms:
            stack.append((ms.group(1), i))
        elif me and stack:
            mid, start = stack.pop()
            out.append((mid, start, i))
    return out


def _insert_preamble(lines: list[str], additions: list[str]) -> tuple[list[str], int]:
    """Idempotent preamble injection after `\\usepackage{gist-preprint}`
    (or after `\\documentclass` if gist-preprint not present).

    Skips any addition line that already appears verbatim in the preamble.
    Returns (new_lines, n_added).
    """
    if not additions:
        return lines, 0

    # Locate anchor
    anchor = -1
    for i, line in enumerate(lines):
        if re.match(r"^\s*\\usepackage\{gist-preprint\}", line):
            anchor = i
            break
    if anchor < 0:
        for i, line in enumerate(lines):
            if re.match(r"^\s*\\documentclass", line):
                anchor = i
                break
    if anchor < 0:
        return lines, 0

    existing_lines = set(line.strip() for line in lines)
    # Round 4.5: additions may be multi-line blocks (e.g. \lstset{...})
    # — we need to check "is this whole block already present?" rather
    # than line-by-line, because a multi-line block would otherwise be
    # appended piecemeal.
    existing_text = "\n".join(line.rstrip() for line in lines)

    new_lines: list[str] = []
    added = 0
    for add in additions:
        stripped = add.strip()
        if not stripped:
            continue
        if "\n" in stripped:
            # Multi-line block: fingerprint by first 80 non-whitespace
            # chars so tiny indentation differences don't cause dupe.
            fp = re.sub(r"\s+", " ", stripped)[:80]
            fp_existing = re.sub(r"\s+", " ", existing_text)
            if fp in fp_existing:
                continue
            new_lines.extend(add.splitlines())
        else:
            if stripped in existing_lines:
                continue
            new_lines.append(add)
        added += 1
    if not new_lines:
        return lines, 0

    block = (
        ["", "% ─── preamble additions from md_inject_apply (idempotent) ───"]
        + new_lines
        + ["% ─── end preamble additions ───"]
    )
    return lines[: anchor + 1] + block + lines[anchor + 1 :], added


def apply(plan: dict, *, dry_run: bool, force: bool, no_backup: bool) -> ApplyReport:
    target = Path(plan["target"])
    report = ApplyReport(target=str(target), dry_run=dry_run)
    if not target.exists():
        raise FileNotFoundError(target)

    orig_bytes = target.read_bytes()
    current_sha1 = _sha1(orig_bytes)
    planned_sha1 = plan.get("target_sha1", "")
    if planned_sha1 and current_sha1 != planned_sha1 and not force:
        raise RuntimeError(
            f"main.tex has changed since plan was built "
            f"({planned_sha1[:12]} → {current_sha1[:12]}). "
            f"Re-run md_inject_plan.py or pass --force."
        )

    tex_text = orig_bytes.decode("utf-8")
    lines = tex_text.splitlines()

    regions = _find_marker_regions(tex_text)
    regions_by_id = {mid: (start, end) for mid, start, end in regions}

    # Load fragments, sort injections by start_line descending so we can
    # splice without re-computing indices.
    injections = sorted(
        plan.get("injections") or [],
        key=lambda i: -(regions_by_id.get(i["marker_id"], (i.get("marker_start_line", 0) - 1,))[0]),
    )

    for inj in injections:
        mid = inj["marker_id"]
        if mid not in regions_by_id:
            report.warnings.append(
                f"marker '{mid}' not found in main.tex (stale plan?)"
            )
            continue
        frag_path = Path(inj["fragment_out"])
        if not frag_path.exists():
            report.n_missing_fragments += 1
            report.warnings.append(f"fragment missing: {frag_path}")
            continue
        fragment = _load_fragment(frag_path).rstrip("\n")
        start, end = regions_by_id[mid]
        # Replace lines between start and end (exclusive); keep markers.
        body = fragment.splitlines()
        lines = lines[: start + 1] + body + lines[end:]
        report.n_applied += 1

    # Aggregate per-fragment required_packages + preamble_snippets
    # + auto_bib_paths. These are discovered during Phase 7 (convert)
    # based on what pandoc actually emits, so they are more accurate
    # than the static plan.preamble_additions list built at Phase 6.
    pkg_usepackage_lines, preamble_snippets, auto_bibs = _aggregate_meta(plan)

    # Combine in this order:
    #   1. \usepackage{...} — package loads
    #   2. preamble snippets (\lstset{...}, \newunicodechar{...}) —
    #      package config that depends on packages being loaded
    #   3. static plan.preamble_additions — ad-hoc commands
    combined_additions = (
        pkg_usepackage_lines
        + (preamble_snippets or [])
        + (plan.get("preamble_additions") or [])
    )

    lines, added = _insert_preamble(lines, combined_additions)
    report.n_preamble_lines_added = added
    report.n_usepackage_added = sum(
        1 for a in pkg_usepackage_lines if a.strip() not in set(l.strip() for l in orig_bytes.decode("utf-8").splitlines())
    )
    # Copy auto-generated .bib files next to target so BibTeX can find them
    # via \bibliography{stem}. This happens even in dry-run-mode for the
    # report; the actual file write is suppressed in dry-run below.
    if not dry_run:
        published = _publish_auto_bibs(auto_bibs, target.parent)
    else:
        published = []
    report.auto_bib_paths = [dst for _, dst in published] or auto_bibs
    if auto_bibs:
        stems = sorted({Path(b).stem for b in auto_bibs})
        report.warnings.append(
            "numeric citations auto-resolved — add the following to main.tex "
            "bibliography list if not already present: "
            + ", ".join(stems)
            + f" ({len(published)} .bib file(s) copied next to target)"
        )

    new_text = "\n".join(lines)
    if not new_text.endswith("\n"):
        new_text += "\n"

    if dry_run:
        diff = difflib.unified_diff(
            orig_bytes.decode("utf-8").splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"{target.name} (before)",
            tofile=f"{target.name} (after md_inject)",
            n=3,
        )
        report.diff = "".join(diff)
        return report

    if not no_backup:
        report.backup = str(_make_backup(target))

    # Atomic write
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False,
        dir=target.parent, prefix=".md_inject.", suffix=".tmp",
    ) as tmp:
        tmp.write(new_text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target)

    return report


def _format_report(r: ApplyReport) -> str:
    lines = [
        f"Phase 9 — Apply",
        f"  target:        {r.target}",
        f"  applied:       {r.n_applied}",
        f"  preamble adds: {r.n_preamble_lines_added}"
        + (f" (auto \\usepackage: {r.n_usepackage_added})" if r.n_usepackage_added else ""),
    ]
    if r.auto_bib_paths:
        lines.append(f"  auto-bib:      {len(r.auto_bib_paths)} file(s)")
        for b in r.auto_bib_paths:
            lines.append(f"                 - {b}")
    if r.backup:
        lines.append(f"  backup:        {r.backup}")
    if r.n_missing_fragments:
        lines.append(f"  ⚠ missing:     {r.n_missing_fragments}")
    for w in r.warnings:
        lines.append(f"  ! {w}")
    if r.dry_run:
        lines.append("")
        lines.append("(dry-run: no file written)")
        lines.append("")
        lines.append(r.diff)
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Apply fragments to main.tex (Phase 9)")
    p.add_argument("--plan", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--force", action="store_true", help="skip sha1 staleness check")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"[md_inject_apply] plan not found: {plan_path}", file=sys.stderr)
        return 2
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    try:
        report = apply(
            plan,
            dry_run=args.dry_run,
            force=args.force,
            no_backup=args.no_backup,
        )
    except RuntimeError as e:
        print(f"[md_inject_apply] {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"[md_inject_apply] target not found: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(_format_report(report))

    return 0 if report.n_missing_fragments == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

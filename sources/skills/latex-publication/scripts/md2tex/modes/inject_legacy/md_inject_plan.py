#!/usr/bin/env python3
"""Phase 6: MD → TeX injection planner.

Scans the target main.tex for `% MD-INJECT: <id>` ... `% MD-INJECT-END`
paired sentinels, resolves each marker_id to a Markdown source under
--md-root, and emits an InjectionPlan JSON to .build/md_inject/plan.json.

When no markers exist, operates in suggest-only mode: fuzzy-matches MD H1s
against \\section/\\subsection titles in the target and prints proposed
marker insertions. Never modifies main.tex.

Usage:
  md_inject_plan.py <project_dir>
                    --target docs/manuscripts/pre-print-template/main.tex
                    [--md-root docs/]
                    [--manifest md-inject.yaml]
                    [--out .build/md_inject/plan.json]
                    [--suggest-only]
                    [--json]

Exit codes:
  0  plan written or suggestions produced
  1  no markers AND no plausible suggestions
  2  invalid inputs (target missing, etc.)
  3  plan invariants violated (duplicate marker_id, unterminated marker)
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


# ── Marker detection ────────────────────────────────────────────
_MARKER_START_RE = re.compile(r"^%\s*MD-INJECT:\s*(\S+)\s*$")
_MARKER_END_RE = re.compile(r"^%\s*MD-INJECT-END\s*$")

# Section titles for suggest mode
_SECTION_RE = re.compile(
    r"^\\(section|subsection|subsubsection)\*?\{([^}]+)\}"
)
_MD_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# Rough Korean → English keyword hints for suggest mode
_KR_EN_HINTS = {
    "서론": ["introduction", "intro"],
    "개요": ["overview", "introduction"],
    "이론": ["theory", "theoretical", "background", "preliminaries"],
    "설계": ["design", "method", "proposed"],
    "방법": ["method", "methodology", "approach"],
    "실험": ["experiment", "experiments", "evaluation"],
    "평가": ["evaluation", "experiments"],
    "결과": ["results", "findings"],
    "분석": ["analysis", "results"],
    "논의": ["discussion"],
    "결론": ["conclusion"],
    "관련": ["related", "related work"],
    "측정": ["measurement", "metric", "metrics"],
    "프레임워크": ["framework"],
    "아키텍처": ["architecture"],
    "과제": ["task", "tasks"],
    "동기": ["motivation"],
}


@dataclass
class Marker:
    id: str
    start_line: int  # 1-indexed, the `% MD-INJECT:` line
    end_line: int  # 1-indexed, the `% MD-INJECT-END` line


@dataclass
class Injection:
    marker_id: str
    marker_start_line: int
    marker_end_line: int
    md_source: str
    md_sha1: str
    pandoc_extra_flags: list[str] = field(default_factory=list)
    h1_strip: bool = True
    fragment_out: str = ""
    meta_out: str = ""


@dataclass
class Suggestion:
    target_line: int
    target_section: str
    suggested_md: str
    md_h1: str
    confidence: float


@dataclass
class InjectionPlan:
    target: str
    target_sha1: str
    md_root: str
    build_cache: str
    preamble_additions: list[str] = field(default_factory=list)
    injections: list[Injection] = field(default_factory=list)
    bootstrap_suggestions: list[Suggestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Helpers ─────────────────────────────────────────────────────
def _sha1_file(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat_id(marker_id: str) -> str:
    """Turn 'design/v3/02_theoretical_foundations' into a safe basename."""
    return re.sub(r"[^A-Za-z0-9_]+", "_", marker_id).strip("_")


def find_markers(tex_text: str) -> list[Marker]:
    """Find paired `% MD-INJECT: <id>` ... `% MD-INJECT-END` blocks."""
    markers: list[Marker] = []
    stack: list[tuple[str, int]] = []  # (id, start_line)
    for i, raw_line in enumerate(tex_text.splitlines(), start=1):
        line = raw_line.rstrip()
        ms = _MARKER_START_RE.match(line)
        me = _MARKER_END_RE.match(line)
        if ms:
            if stack:
                raise ValueError(
                    f"main.tex:{i}: new % MD-INJECT: {ms.group(1)} opened "
                    f"before previous % MD-INJECT: {stack[-1][0]} "
                    f"(opened at line {stack[-1][1]}) was closed"
                )
            stack.append((ms.group(1), i))
        elif me:
            if not stack:
                raise ValueError(
                    f"main.tex:{i}: % MD-INJECT-END with no matching opener"
                )
            mid, start = stack.pop()
            markers.append(Marker(id=mid, start_line=start, end_line=i))
    if stack:
        mid, start = stack[-1]
        raise ValueError(
            f"main.tex:{start}: % MD-INJECT: {mid} never closed"
        )
    # Check for duplicate ids
    seen: dict[str, int] = {}
    for m in markers:
        if m.id in seen:
            raise ValueError(
                f"duplicate marker_id '{m.id}' at lines {seen[m.id]} and {m.start_line}"
            )
        seen[m.id] = m.start_line
    return markers


def _resolve_md_path(marker_id: str, md_root: Path) -> Path | None:
    """Resolve marker_id to an absolute MD path.

    Tries (in order):
      1. <md_root>/<marker_id>.md
      2. <md_root>/<marker_id>/index.md
      3. glob <md_root>/**/<basename-of-marker_id>.md  (unique match only)
    """
    candidates = [
        md_root / f"{marker_id}.md",
        md_root / marker_id / "index.md",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    base = Path(marker_id).name
    matches = sorted(md_root.rglob(f"{base}.md"))
    if len(matches) == 1:
        return matches[0].resolve()
    return None


def _h1_of(md_path: Path) -> str:
    try:
        text = _read_text(md_path)
    except OSError:
        return ""
    m = _MD_H1_RE.search(text)
    return m.group(1).strip() if m else ""


def _section_titles(tex_text: str) -> list[tuple[int, str, str]]:
    """(line_no, kind, title) for every \\section/\\subsection in target."""
    out: list[tuple[int, str, str]] = []
    for i, line in enumerate(tex_text.splitlines(), start=1):
        m = _SECTION_RE.match(line.lstrip())
        if m:
            out.append((i, m.group(1), m.group(2).strip()))
    return out


def _score(kr_title: str, en_title: str) -> float:
    """Heuristic 0..1 similarity between a Korean MD H1 and an English section title."""
    kr = kr_title.lower()
    en = en_title.lower()
    # Direct word match via hint dict
    for kw, en_hints in _KR_EN_HINTS.items():
        if kw in kr:
            for h in en_hints:
                if h in en:
                    return 0.80
    # Fallback: normalized sequence ratio on ASCII chars only
    kr_ascii = re.sub(r"[^a-z0-9]", "", kr)
    en_ascii = re.sub(r"[^a-z0-9]", "", en)
    if not kr_ascii or not en_ascii:
        return 0.0
    return difflib.SequenceMatcher(a=kr_ascii, b=en_ascii).ratio() * 0.6


def suggest_markers(
    tex_text: str, md_paths: list[Path], *, threshold: float = 0.55
) -> list[Suggestion]:
    titles = _section_titles(tex_text)
    out: list[Suggestion] = []
    for md in md_paths:
        h1 = _h1_of(md)
        if not h1:
            continue
        best: tuple[float, int, str] | None = None
        for line_no, _kind, sec_title in titles:
            score = _score(h1, sec_title)
            if score < threshold:
                continue
            if best is None or score > best[0]:
                best = (score, line_no, sec_title)
        if best is not None:
            score, line_no, sec_title = best
            out.append(
                Suggestion(
                    target_line=line_no,
                    target_section=sec_title,
                    suggested_md=str(md),
                    md_h1=h1,
                    confidence=round(score, 2),
                )
            )
    out.sort(key=lambda s: (-s.confidence, s.target_line))
    return out


# ── Plan building ───────────────────────────────────────────────
def build_plan(
    project_dir: Path,
    target: Path,
    md_root: Path,
    *,
    build_cache: Path | None = None,
    manifest: dict | None = None,
    suggest_only: bool = False,
) -> InjectionPlan:
    if not target.exists():
        raise FileNotFoundError(f"target tex not found: {target}")
    if not md_root.exists():
        raise FileNotFoundError(f"md root not found: {md_root}")

    build_cache = build_cache or (project_dir / ".build" / "md_inject")
    tex_text = _read_text(target)
    target_sha1 = _sha1_file(target)

    plan = InjectionPlan(
        target=str(target.resolve()),
        target_sha1=target_sha1,
        md_root=str(md_root.resolve()),
        build_cache=str(build_cache.resolve()),
    )

    # Preamble defensive additions (idempotent check done at apply time).
    # These are safe no-ops if the target already defines them; \providecommand
    # only acts when the command is undefined.
    plan.preamble_additions = [
        r"\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}",
        r"\providecommand{\passthrough}[1]{\texttt{#1}}",
        # Defensive booktabs rule fallbacks (pandoc emits \toprule/\midrule/\bottomrule)
        # Pandoc emits \toprule/\midrule/\bottomrule from booktabs; the
        # target's preamble should \usepackage{booktabs}. We do NOT inject
        # providecommand fallbacks for these because (a) they would render
        # as plain \hline (ugly), and (b) \endhead/\endlastfoot cannot be
        # safely \providecommand'd since LaTeX reserves the \end... name
        # space. If booktabs is missing, the user sees a clear error.
        r"\tolerance=1000",
        r"\emergencystretch=3em",
    ]

    markers = find_markers(tex_text)

    if not markers or suggest_only:
        md_paths = sorted(md_root.rglob("*.md"))
        plan.bootstrap_suggestions = suggest_markers(tex_text, md_paths)
        if not markers:
            plan.warnings.append(
                f"no % MD-INJECT markers found in {target}; emitted "
                f"{len(plan.bootstrap_suggestions)} suggestion(s). "
                "Add markers and re-run without --suggest-only."
            )

    if markers and not suggest_only:
        for m in markers:
            md_path = _resolve_md_path(m.id, md_root)
            if md_path is None:
                plan.warnings.append(
                    f"marker '{m.id}' at line {m.start_line}: no MD file found "
                    f"under {md_root} (tried {m.id}.md, {m.id}/index.md, **/{Path(m.id).name}.md)"
                )
                continue
            flat = _flat_id(m.id)
            inj = Injection(
                marker_id=m.id,
                marker_start_line=m.start_line,
                marker_end_line=m.end_line,
                md_source=str(md_path),
                md_sha1=_sha1_file(md_path),
                pandoc_extra_flags=[],
                h1_strip=True,
                fragment_out=str(build_cache / f"{flat}.tex.fragment"),
                meta_out=str(build_cache / f"{flat}.meta.json"),
            )
            # Apply manifest overrides if present
            if manifest and "injections" in manifest:
                override = manifest["injections"].get(m.id) or {}
                for k, v in override.items():
                    if hasattr(inj, k):
                        setattr(inj, k, v)
                    elif k == "pandoc_extra_flags":
                        inj.pandoc_extra_flags = list(v)
            plan.injections.append(inj)

    return plan


def _load_manifest(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return None


def _format_human(plan: InjectionPlan) -> str:
    lines: list[str] = []
    lines.append(f"target:  {plan.target}")
    lines.append(f"md_root: {plan.md_root}")
    lines.append(f"cache:   {plan.build_cache}")
    lines.append("")
    if plan.injections:
        lines.append(f"injections ({len(plan.injections)}):")
        for i in plan.injections:
            lines.append(
                f"  {i.marker_id}  main.tex:{i.marker_start_line}-{i.marker_end_line}"
                f"  ← {Path(i.md_source).name}"
            )
    if plan.bootstrap_suggestions:
        lines.append("")
        lines.append(f"suggestions ({len(plan.bootstrap_suggestions)}):")
        for s in plan.bootstrap_suggestions:
            lines.append(
                f"  main.tex:{s.target_line} \\section{{{s.target_section}}} "
                f"← {Path(s.suggested_md).name}  (conf={s.confidence})"
            )
    if plan.warnings:
        lines.append("")
        lines.append("warnings:")
        for w in plan.warnings:
            lines.append(f"  ! {w}")
    return "\n".join(lines)


def _to_json(plan: InjectionPlan) -> str:
    # dataclasses → dict, preserving nested dataclass fields
    def _encode(o):
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        return o

    return json.dumps(_encode(plan), ensure_ascii=False, indent=2)


def main() -> int:
    p = argparse.ArgumentParser(description="Plan MD→TeX injection (Phase 6)")
    p.add_argument("project_dir", nargs="?", default=".", help="project root")
    p.add_argument("--target", default=None, help="path to main.tex (default: auto-detect)")
    p.add_argument("--md-root", default="docs", help="MD source root")
    p.add_argument("--manifest", default=None, help="optional md-inject.yaml")
    p.add_argument("--out", default=None, help="plan.json output path")
    p.add_argument("--suggest-only", action="store_true", help="bootstrap mode")
    p.add_argument("--json", action="store_true", help="emit JSON to stdout")
    args = p.parse_args()

    project = Path(args.project_dir).resolve()
    if not project.is_dir():
        print(f"[md_inject_plan] not a directory: {project}", file=sys.stderr)
        return 2

    if args.target:
        target = Path(args.target)
        if not target.is_absolute():
            target = project / target
    else:
        candidates = [
            project / "main.tex",
            project / "docs/manuscripts/pre-print-template/main.tex",
        ]
        matches = [c for c in candidates if c.exists()]
        if not matches:
            matches = sorted(project.rglob("main.tex"))
        if not matches:
            print("[md_inject_plan] no main.tex found; use --target", file=sys.stderr)
            return 2
        target = matches[0]

    md_root = Path(args.md_root)
    if not md_root.is_absolute():
        md_root = project / md_root

    manifest = _load_manifest(Path(args.manifest) if args.manifest else None)

    try:
        plan = build_plan(
            project_dir=project,
            target=target,
            md_root=md_root,
            manifest=manifest,
            suggest_only=args.suggest_only,
        )
    except ValueError as e:
        print(f"[md_inject_plan] {e}", file=sys.stderr)
        return 3
    except FileNotFoundError as e:
        print(f"[md_inject_plan] {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else Path(plan.build_cache) / "plan.json"
    if not args.suggest_only:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_to_json(plan), encoding="utf-8")

    if args.json:
        print(_to_json(plan))
    else:
        print(_format_human(plan))
        if not args.suggest_only:
            print(f"\nplan written to: {out_path}")

    if args.suggest_only and not plan.bootstrap_suggestions:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

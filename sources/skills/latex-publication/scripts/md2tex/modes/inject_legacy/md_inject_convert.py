#!/usr/bin/env python3
"""Phase 7: MD → TeX fragment converter (parallel via ProcessPoolExecutor).

Reads an InjectionPlan JSON, runs per-file pipeline
  pre-process → pandoc → post-process
in a worker pool, emits *.tex.fragment + *.meta.json per injection, and a
ConversionSummary JSON.

Usage:
  md_inject_convert.py --plan .build/md_inject/plan.json
                       [--workers N]
                       [--no-auto-cite]
                       [--palette templates/md_inject/color-palette-map.yaml]
                       [--only <glob>]
                       [--force]
                       [--summary <path>]
                       [--json]

Exit codes:
  0  all successes
  1  ≥1 conversion failure (partial results still written)
  2  tool missing (pandoc) or plan invalid
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Make the preprocess package importable when running this script directly.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from preprocess import (  # noqa: E402
    strip_frontmatter,
    strip_horizontal_rules,
    strip_obsidian_artifacts,
)
from preprocess import html_to_latex  # noqa: E402
from preprocess import mermaid_extract  # noqa: E402
from preprocess import code_math_blocks  # noqa: E402
from preprocess import citation_resolver  # noqa: E402
from preprocess import numeric_citation_resolver  # noqa: E402
from preprocess import pandoc_postprocess  # noqa: E402
from preprocess import template_presets  # noqa: E402 — Round 4.5


# ── Result types ────────────────────────────────────────────────
@dataclass
class ConversionResult:
    marker_id: str
    status: str  # "success" | "failed" | "skipped_cached"
    fragment_out: str = ""
    meta_out: str = ""
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    n_mermaids: int = 0
    n_tables: int = 0
    n_citations_rewritten: int = 0
    n_citations_unmatched: int = 0
    n_numeric_citations_rewritten: int = 0
    n_longtable_converted: int = 0
    source_sha1: str = ""
    required_packages: list[str] = field(default_factory=list)
    # Round 4.5: preamble snippets (e.g. \lstset{...}) the aggregator
    # should copy into main.tex above \begin{document} — distinct from
    # full \usepackage{} lines carried by ``required_packages``.
    preamble_snippets: list[str] = field(default_factory=list)
    auto_bib_path: str | None = None


@dataclass
class ConversionSummary:
    plan_path: str
    workers: int
    n_total: int = 0
    n_success: int = 0
    n_failed: int = 0
    n_skipped_cached: int = 0
    wall_time_s: float = 0.0
    serial_estimate_s: float = 0.0
    speedup: float = 0.0
    results: list[ConversionResult] = field(default_factory=list)


# ── Worker (runs in subprocess) ─────────────────────────────────
def _run_one(task: dict) -> dict:
    """Convert a single MD to a TeX fragment. Must be picklable."""
    start = time.perf_counter()
    res = ConversionResult(marker_id=task["marker_id"], status="failed")
    try:
        md_path = Path(task["md_source"])
        fragment_out = Path(task["fragment_out"])
        meta_out = Path(task["meta_out"])
        cache_dir = fragment_out.parent
        cache_dir.mkdir(parents=True, exist_ok=True)

        md_text = md_path.read_text(encoding="utf-8")
        source_sha1 = hashlib.sha1(md_text.encode("utf-8")).hexdigest()
        res.source_sha1 = source_sha1

        # Cache hit?
        if not task.get("force") and fragment_out.exists() and meta_out.exists():
            try:
                cached_meta = json.loads(meta_out.read_text(encoding="utf-8"))
                if cached_meta.get("source_sha1") == source_sha1:
                    res.status = "skipped_cached"
                    res.fragment_out = str(fragment_out)
                    res.meta_out = str(meta_out)
                    res.warnings = cached_meta.get("warnings", [])
                    res.n_mermaids = cached_meta.get("n_mermaids", 0)
                    res.n_tables = cached_meta.get("n_tables", 0)
                    res.n_citations_rewritten = cached_meta.get(
                        "n_citations_rewritten", 0
                    )
                    res.n_citations_unmatched = cached_meta.get(
                        "n_citations_unmatched", 0
                    )
                    res.n_numeric_citations_rewritten = cached_meta.get(
                        "n_numeric_citations_rewritten", 0
                    )
                    res.n_longtable_converted = cached_meta.get(
                        "n_longtable_converted", 0
                    )
                    res.required_packages = cached_meta.get(
                        "required_packages", []
                    )
                    res.preamble_snippets = cached_meta.get(
                        "preamble_snippets", []
                    )
                    res.auto_bib_path = cached_meta.get("auto_bib_path")
                    res.duration_s = time.perf_counter() - start
                    return asdict(res)
            except (json.JSONDecodeError, OSError):
                pass

        all_warnings: list[str] = []

        # Pre-processing
        md_text, w = strip_frontmatter(md_text)
        all_warnings += w
        md_text, w = strip_obsidian_artifacts(md_text)
        all_warnings += w
        md_text, w = strip_horizontal_rules(md_text)
        all_warnings += w
        md_text, w = html_to_latex.convert(md_text, task.get("palette") or {})
        all_warnings += w
        md_text, w = code_math_blocks.convert(md_text)
        all_warnings += w

        # Round 4.5 — template preset MD-level transforms. Must run
        # BEFORE mermaid_extract (which swallows fenced blocks into
        # placeholders), so fenced ``algorithm`` blocks get the proper
        # pseudocode conversion rather than ASCII-art fallback.
        preset_name = task.get("template_preset") or template_presets.detect_preset(
            task.get("main_tex_path")
        )
        if preset_name and preset_name != "none":
            pp_result = template_presets.apply_preset_preprocess(md_text, preset_name)
            md_text = pp_result.text
            all_warnings += pp_result.warnings
            # Stash so postprocess can merge required_packages.
            res.required_packages = list(pp_result.required_packages)

        md_text, w, mermaid_blocks = mermaid_extract.convert(md_text)
        all_warnings += w
        res.n_mermaids = len(mermaid_blocks)

        # F2: Numeric [N] bibliography extraction + inline \cite rewrite.
        # Writes an auto-generated .bib alongside the fragment cache so
        # bibtex/biber can resolve \cite{refN}. Runs BEFORE the ordinary
        # Author(Year) resolver so literal [N] tokens are removed first.
        auto_bib_path = Path(str(fragment_out).replace(".tex.fragment", "") + ".auto.bib")
        nr = numeric_citation_resolver.resolve_numeric_citations(
            md_text,
            auto_bib_out=auto_bib_path,
            enabled=task.get("numeric_cite", True),
        )
        md_text = nr.text
        all_warnings += nr.warnings
        res.n_numeric_citations_rewritten = nr.n_inline_rewritten
        if nr.auto_bib_path:
            res.auto_bib_path = nr.auto_bib_path

        # Citation resolution — needs the bib index (shared state via pickle)
        index = task.get("_bib_index")
        if index is not None:
            rr = citation_resolver.resolve(
                md_text,
                index,
                enabled=task.get("auto_cite", True),
                normalize_cite=True,
            )
            md_text = rr.text
            all_warnings += rr.warnings
            res.n_citations_rewritten = rr.n_rewritten
            res.n_citations_unmatched = rr.n_unmatched

        # Optional H1 strip (when injecting into a pre-existing section)
        if task.get("h1_strip", True):
            lines = md_text.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("# "):
                    del lines[i]
                    # Drop trailing blank line
                    if i < len(lines) and not lines[i].strip():
                        del lines[i]
                    md_text = "\n".join(lines)
                    break

        # Write preprocessed MD to cache
        pre_path = cache_dir / f"{fragment_out.stem.replace('.tex', '')}.preprocessed.md"
        pre_path.write_text(md_text, encoding="utf-8")

        # Pandoc
        pandoc = shutil.which("pandoc")
        if not pandoc:
            res.error = "pandoc not on PATH"
            res.duration_s = time.perf_counter() - start
            return asdict(res)

        raw_out = cache_dir / f"{fragment_out.stem.replace('.tex', '')}.raw.tex"
        # Pandoc's `markdown` input format is the most featureful — it
        # enables raw_tex, tex_math_dollars, pipe_tables, fenced_code,
        # and fenced_code_attributes by default. `gfm` in pandoc 3+
        # does not support raw_tex or fenced_code_attributes, which
        # breaks our citation_resolver's raw `\citep{}` spans. Using
        # pandoc's native `markdown` format keeps compatibility with
        # the Squid-Game design v3 MD corpus and the typical Obsidian
        # flavor; pipe tables and code fences work identically.
        from_fmt = "markdown"
        extra_flags = list(task.get("pandoc_extra_flags") or [])
        # Pandoc 3+ only accepts section/chapter/part/default as the argument
        # of --top-level-division. We always emit section as the top level.
        if "--top-level-division" not in " ".join(extra_flags):
            extra_flags += ["--top-level-division", "section"]
        # F-h1strip-1: when h1_strip removes the MD H1 line, shift remaining
        # headings UP by one so H2 (``##``) becomes \section (not
        # \subsection), and H3 (``###``) becomes \subsection. Without this
        # shift the output is one level too deep and section numbering comes
        # out as "0.1 X", "0.2 Y", etc. (visible in the PDF under acmart).
        # Respects manually-supplied --shift-heading-level-by in manifest.
        if task.get("h1_strip", True) and "--shift-heading-level-by" not in " ".join(extra_flags):
            extra_flags += ["--shift-heading-level-by=-1"]
        cmd = [
            pandoc,
            "--from", from_fmt,
            "--to", "latex",
            "--no-highlight",
            "--wrap=none",
            "--listings",
            "--output", str(raw_out),
            str(pre_path),
        ] + extra_flags
        # Note: --citeproc is off by default in pandoc unless --citeproc is passed;
        # we intentionally do NOT pass --citeproc so our pre-processed \citep{}
        # stays verbatim.
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            res.error = f"pandoc exit {proc.returncode}: {proc.stderr.strip()[:500]}"
            res.duration_s = time.perf_counter() - start
            return asdict(res)

        raw_tex = raw_out.read_text(encoding="utf-8")

        # Post-processing
        cfg = pandoc_postprocess.PostprocessConfig(
            source_relpath=task.get("md_relpath", Path(task["md_source"]).name),
            source_sha1=source_sha1,
            image_path_rewrites=task.get("image_path_rewrites") or {},
            include_sentinels=True,
            table_mode=task.get("table_mode", "auto"),
        )
        pp = pandoc_postprocess.postprocess(raw_tex, cfg)
        fragment_text = pp.text
        all_warnings += pp.warnings
        # Merge preset-added required_packages (set above during
        # preprocess) with the set discovered by pandoc_postprocess,
        # preserving order and deduplicating.
        merged_pkgs: list[str] = list(res.required_packages)
        for p in pp.required_packages:
            if p not in merged_pkgs:
                merged_pkgs.append(p)
        res.required_packages = merged_pkgs
        res.preamble_snippets = pp.preamble_snippets
        res.n_longtable_converted = pp.n_longtable_converted
        res.n_tables = fragment_text.count(r"\begin{longtable}") + fragment_text.count(
            r"\begin{tabular}"
        )

        fragment_out.write_text(fragment_text, encoding="utf-8")

        meta = {
            "source_sha1": source_sha1,
            "warnings": all_warnings,
            "n_mermaids": res.n_mermaids,
            "n_tables": res.n_tables,
            "n_citations_rewritten": res.n_citations_rewritten,
            "n_citations_unmatched": res.n_citations_unmatched,
            "n_numeric_citations_rewritten": res.n_numeric_citations_rewritten,
            "n_longtable_converted": res.n_longtable_converted,
            "required_packages": res.required_packages,
            "preamble_snippets": res.preamble_snippets,
            "auto_bib_path": res.auto_bib_path,
            "mermaid_blocks": [
                {
                    "index": b.index,
                    "first_line": b.first_nonempty_line,
                    "line_count": b.line_count,
                    "kind": getattr(b, "kind", "mermaid"),
                }
                for b in mermaid_blocks
            ],
        }
        meta_out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        res.status = "success"
        res.fragment_out = str(fragment_out)
        res.meta_out = str(meta_out)
        res.warnings = all_warnings
    except Exception as e:  # noqa: BLE001
        res.error = f"{type(e).__name__}: {e}"
    finally:
        res.duration_s = time.perf_counter() - start

    return asdict(res)


# ── Orchestrator ────────────────────────────────────────────────
def _load_palette(path: Path | None) -> dict[str, str]:
    if path is None:
        # __file__: latex-publication/scripts/md2tex/modes/inject_legacy/md_inject_convert.py
        # 5 levels up → latex-publication/
        default = Path(__file__).resolve().parents[4] / (
            "templates/md_inject/color-palette-map.yaml"
        )
        path = default if default.exists() else None
    if path is None or not path.exists():
        return {}
    return html_to_latex.load_palette_from_yaml(str(path))


def _discover_bibs(target: Path) -> list[Path]:
    target_dir = target.parent
    bibs = sorted(target_dir.glob("*.bib"))
    if bibs:
        return bibs
    # Fallback: scan up to 2 levels up
    for d in [target_dir.parent, target_dir.parent.parent]:
        if not d or not d.exists():
            continue
        bibs = sorted(d.glob("*.bib"))
        if bibs:
            return bibs
    return []


def convert_all(
    plan: dict,
    *,
    workers: int,
    only: str | None,
    force: bool,
    auto_cite: bool,
    palette: dict[str, str],
) -> ConversionSummary:
    injections = plan.get("injections") or []
    if only:
        injections = [i for i in injections if fnmatch.fnmatch(i["marker_id"], only)]

    # Build bib index once, share via task dict (pickled to workers)
    target_path = Path(plan["target"])
    bib_paths = _discover_bibs(target_path)
    bib_index = citation_resolver.build_bib_index(bib_paths) if auto_cite else None

    tasks: list[dict] = []
    md_root = Path(plan["md_root"])
    for inj in injections:
        md_path = Path(inj["md_source"])
        try:
            md_rel = md_path.relative_to(md_root)
        except ValueError:
            md_rel = md_path
        tasks.append(
            {
                "marker_id": inj["marker_id"],
                "md_source": inj["md_source"],
                "md_relpath": str(md_rel),
                "fragment_out": inj["fragment_out"],
                "meta_out": inj["meta_out"],
                "pandoc_extra_flags": inj.get("pandoc_extra_flags") or [],
                "h1_strip": inj.get("h1_strip", True),
                "palette": palette,
                "force": force,
                "auto_cite": auto_cite,
                "_bib_index": bib_index,
            }
        )

    results: list[ConversionResult] = []
    start = time.perf_counter()
    n = len(tasks)
    w = min(workers, n) if n > 0 else 1

    if n == 0:
        return ConversionSummary(
            plan_path=str(target_path),
            workers=w,
            n_total=0,
            wall_time_s=0.0,
        )

    if w <= 1:
        for t in tasks:
            r = _run_one(t)
            results.append(ConversionResult(**r))
    else:
        with ProcessPoolExecutor(max_workers=w) as pool:
            futures = [pool.submit(_run_one, t) for t in tasks]
            for fut in as_completed(futures):
                results.append(ConversionResult(**fut.result()))

    wall = time.perf_counter() - start
    serial_est = sum(r.duration_s for r in results)
    speedup = (serial_est / wall) if wall > 0 else 0.0

    summary = ConversionSummary(
        plan_path=str(target_path),
        workers=w,
        n_total=n,
        n_success=sum(1 for r in results if r.status == "success"),
        n_failed=sum(1 for r in results if r.status == "failed"),
        n_skipped_cached=sum(1 for r in results if r.status == "skipped_cached"),
        wall_time_s=round(wall, 3),
        serial_estimate_s=round(serial_est, 3),
        speedup=round(speedup, 2),
        results=sorted(results, key=lambda r: r.marker_id),
    )
    return summary


def _format_summary(s: ConversionSummary) -> str:
    lines = [
        f"Phase 7 — Convert  ({s.n_total} injections, {s.workers} workers)",
        f"  success:  {s.n_success}",
        f"  cached:   {s.n_skipped_cached}",
        f"  failed:   {s.n_failed}",
        f"  wall:     {s.wall_time_s}s",
        f"  serial:   {s.serial_estimate_s}s  (speedup {s.speedup}x)",
    ]
    for r in s.results:
        if r.status == "failed":
            lines.append(f"  ❌ {r.marker_id}: {r.error}")
        elif r.warnings:
            n = len(r.warnings)
            head = r.warnings[0][:100]
            lines.append(
                f"  ⚠ {r.marker_id}  ({n} warning{'s' if n != 1 else ''}; "
                f"first: {head})"
            )
        else:
            lines.append(f"  ✅ {r.marker_id}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Convert MD → TeX fragments (Phase 7)")
    p.add_argument("--plan", required=True, help="path to plan.json")
    p.add_argument("--workers", type=int, default=min(os.cpu_count() or 2, 8))
    p.add_argument("--no-auto-cite", action="store_true")
    p.add_argument("--palette", default=None, help="color palette YAML")
    p.add_argument("--only", default=None, help="glob filter on marker_id")
    p.add_argument("--force", action="store_true", help="ignore sha1 cache")
    p.add_argument("--summary", default=None, help="summary JSON output path")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"[md_inject_convert] plan not found: {plan_path}", file=sys.stderr)
        return 2
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    if not shutil.which("pandoc"):
        print(
            "[md_inject_convert] ❌ pandoc not on PATH. Install via `brew install pandoc`.",
            file=sys.stderr,
        )
        return 2

    palette = _load_palette(Path(args.palette) if args.palette else None)

    summary = convert_all(
        plan,
        workers=max(1, args.workers),
        only=args.only,
        force=args.force,
        auto_cite=not args.no_auto_cite,
        palette=palette,
    )

    summary_path = (
        Path(args.summary)
        if args.summary
        else Path(plan["build_cache"]) / "conversion_summary.json"
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.json:
        print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    else:
        print(_format_summary(summary))
        print(f"\nsummary written to: {summary_path}")

    return 0 if summary.n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

r"""Diagram fenced-block handling (mermaid, dataview, plantuml, graphviz, ASCII-art).

Per the approved plan (Decision 4), this skill does NOT render diagrams to
PNG automatically. Each recognised fenced block whose info-string is a
diagram language is replaced with a \fbox{\parbox{...}} placeholder
containing a short excerpt of the source so the author can locate and
replace it manually. A \% TODO comment flags the spot for LaTeX-aware
editors and reviewers.

Recognised info-strings:
  - ``mermaid`` — Mermaid.js diagrams
  - ``dataview`` / ``dataviewjs`` — Obsidian Dataview queries
  - ``plantuml`` — PlantUML
  - ``graphviz`` / ``dot`` — Graphviz DOT
  - ``tikz`` / ``tikz-cd`` — raw TikZ (still rarely inline-compilable in fragments)

Bare triple-backtick blocks (``` with no info-string) are also checked
heuristically: if the content contains >= 2 Unicode box-drawing characters
(``┌─┐│└┘├┤┬┴┼╔═╗║╚╝`` range) AND is >= 3 lines, it is treated as an
ASCII-art diagram and replaced with a placeholder. This avoids breaking
genuine code blocks in the process (Python/Bash/etc. don't use box chars).

This keeps the pipeline 100% dependency-free (no mmdc, no Chrome sidecar),
and guarantees every fragment compiles on the first try — the author then
replaces placeholders at their own pace.

Backwards-compat alias: :func:`convert` still returns ``(text, warnings,
blocks)`` and ``blocks[i].index`` is a 1-based counter across ALL diagram
types in document order, matching the v1 API used by ``md_inject_convert``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["convert", "MermaidBlock"]


# Languages that we always treat as diagram (labelled placeholders).
_DIAGRAM_LANGUAGES = {
    "mermaid",
    "dataview",
    "dataviewjs",
    "plantuml",
    "graphviz",
    "dot",
    "tikz",
    "tikz-cd",
}

# Fenced code block: captures info-string (`lang`) and raw body.
# Matches ```lang, ```lang attrs, ``` (bare).
_FENCE_RE = re.compile(
    r"^```(?P<info>[^\n]*)\n(?P<body>.*?)\n```\s*$",
    re.DOTALL | re.MULTILINE,
)

# Unicode box-drawing + block characters used to detect ASCII-art diagrams.
# Range covers U+2500–U+257F (box drawing) and U+2580–U+259F (block elements).
_BOX_CHAR_RE = re.compile(r"[─-▟]")


@dataclass
class MermaidBlock:
    """Metadata for one extracted diagram block.

    The class name is kept for back-compat with md_inject_convert; this
    field now represents ANY diagram type, not only mermaid.
    """

    index: int
    first_nonempty_line: str
    line_count: int
    kind: str = "mermaid"  # one of _DIAGRAM_LANGUAGES | "ascii-art"


def _escape_for_latex_body(raw: str) -> str:
    r"""Escape backslashes + braces so the raw DSL can appear literally
    inside a \parbox. Does NOT try to preserve indentation beyond a single
    space-collapse (readability over fidelity)."""
    safe = raw.replace("\\", r"\textbackslash ")
    safe = safe.replace("{", r"\{").replace("}", r"\}")
    safe = safe.replace("&", r"\&").replace("%", r"\%")
    safe = safe.replace("$", r"\$").replace("#", r"\#")
    safe = safe.replace("_", r"\_").replace("^", r"\^{}")
    safe = safe.replace("~", r"\~{}")
    return safe


def _first_nonempty(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s
    return "(empty)"


def _render_placeholder(index: int, kind: str, src: str) -> str:
    """Render a compact, column-safe \\fbox placeholder.

    Width safety:
      * ``\\linewidth`` (NOT ``\\textwidth``) so the placeholder respects
        single-column constraint in 2-column document classes (acmart
        sigconf, IEEE compsoc). Using \\textwidth in a 2-col layout causes
        the box to span both columns and overlap neighbouring text.
      * Box-drawing Unicode chars (U+2500–U+259F) are replaced with ``·``
        in the excerpt because some fonts render them with a wider advance
        than Latin monospace, causing single-line \\texttt{} to overflow
        the \\fbox by a few points (visible as the ``3.3pt Overfull`` log
        warnings).
      * Excerpt is capped at 40 chars so the label fits on one line even
        at \\scriptsize; the first meaningful line is still informative
        enough for the author to locate the source block.
    """
    first = _first_nonempty(src)
    # Replace box-drawing chars so the texttt line fits in the column.
    sanitized = re.sub(r"[─-▟]", "·", first)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    if len(sanitized) > 40:
        excerpt = sanitized[:40].rstrip() + "…"
    else:
        excerpt = sanitized or "(empty)"
    safe_excerpt = _escape_for_latex_body(excerpt)
    if kind == "ascii-art":
        kind_label = "ASCII-art"
    elif kind == "pipe-table":
        kind_label = "Pipe-table"
    else:
        kind_label = kind.capitalize()
    line_count = src.count("\n") + 1
    return (
        "\\begin{center}\n"
        "\\fbox{\\begin{minipage}{0.9\\linewidth}%\n"
        "\\centering\n"
        f"\\small\\textbf{{[{kind_label} diagram placeholder \\#{index}]}}\\par\n"
        "\\vspace{0.3em}\n"
        f"\\scriptsize\\textit{{{line_count} line(s); first: ``{safe_excerpt}''}}\\par\n"
        "\\vspace{0.3em}\n"
        "\\footnotesize\\textit{TODO: render manually and replace with "
        "\\textbackslash includegraphics}\n"
        "\\end{minipage}}\n"
        "\\end{center}\n"
        f"% TODO: render {kind} block #{index} and replace placeholder above\n"
    )


def _is_asciiart(body: str) -> bool:
    """Heuristic: a bare-fenced block is treated as an ASCII-art diagram
    (and replaced with a placeholder) when ANY of:

    1. ``>= 2`` Unicode box-drawing characters (``┌─┐│└┘├┤┬┴┼╔═╗║╚╝``) and
       ``>= 3`` lines — classic box diagrams.
    2. ``>= 3`` lines and the average line carries ``>= 3`` unescaped ``|``
       characters — "pipe-table" pseudo-tables that authors paste into a
       bare code fence instead of Markdown's ``|col|col|`` syntax.
       Rendering these via ``lstlisting`` in a 2-column class causes
       catastrophic horizontal overflow (Round 4.5: seen with FSPM-Score
       leaderboard, rule-phase E[r] dump, etc.). Treating them as
       ASCII-art placeholders is safe because the author never intended
       them to be code, just tabular illustration.

    Python/shell/LaTeX code blocks are unaffected — they carry a language
    info-string (``python``, ``bash``) which the caller handles via the
    language whitelist before calling ``_is_asciiart``.
    """
    lines = body.splitlines()
    if len(lines) < 3:  # need >= 3 lines
        return False
    box_hits = len(_BOX_CHAR_RE.findall(body))
    if box_hits >= 2:
        return True
    # Pipe-table heuristic: lines are "pipe-lines" if they contain >= 3
    # ``|`` characters. If the majority (>= 60%) of non-blank lines are
    # pipe-lines, treat as pseudo-table. Uses majority instead of MIN so
    # an ``...`` continuation row or a stray caption doesn't disqualify
    # an otherwise obvious pipe-table. Round 4.5.
    nonempty = [ln for ln in lines if ln.strip()]
    if len(nonempty) < 3:
        return False
    pipe_lines = sum(1 for ln in nonempty if ln.count("|") >= 3)
    if pipe_lines >= 3 and pipe_lines / len(nonempty) >= 0.6:
        return True
    return False


def convert(text: str) -> tuple[str, list[str], list[MermaidBlock]]:
    """Replace recognised diagram fenced blocks with \fbox placeholders.

    Returns:
      (new_text, warnings, blocks)
      where blocks[i] records the ith block's metadata for downstream
      aggregation (e.g., summary.n_mermaids). Index is 1-based.
    """
    warnings: list[str] = []
    blocks: list[MermaidBlock] = []
    counter = {"n": 0}
    kinds_seen: dict[str, int] = {}

    def _sub(match: re.Match) -> str:
        info = (match.group("info") or "").strip().lower()
        body = match.group("body")

        # Determine diagram kind. Info-string takes precedence; else try
        # ASCII-art / pipe-table heuristics on bare fences.
        kind: str | None = None
        if info in _DIAGRAM_LANGUAGES:
            kind = info
        elif info == "":
            # Pipe-table heuristic gets its own label for clearer
            # diagnostics (so authors know WHY the block became a
            # placeholder). Box-drawing fallback keeps "ascii-art".
            lines_ne = [ln for ln in body.splitlines() if ln.strip()]
            if len(lines_ne) >= 3:
                pipe_lines = sum(1 for ln in lines_ne if ln.count("|") >= 3)
                if pipe_lines >= 3 and pipe_lines / len(lines_ne) >= 0.6:
                    kind = "pipe-table"
            if kind is None and _is_asciiart(body):
                kind = "ascii-art"

        if kind is None:
            return match.group(0)  # leave as-is (code block, math, etc.)

        counter["n"] += 1
        kinds_seen[kind] = kinds_seen.get(kind, 0) + 1
        blocks.append(
            MermaidBlock(
                index=counter["n"],
                first_nonempty_line=_first_nonempty(body),
                line_count=body.count("\n") + 1,
                kind=kind,
            )
        )
        return _render_placeholder(counter["n"], kind, body)

    out = _FENCE_RE.sub(_sub, text)
    if counter["n"]:
        parts = [f"{n}×{k}" for k, n in sorted(kinds_seen.items())]
        warnings.append(
            f"replaced {counter['n']} diagram block(s) [{', '.join(parts)}] "
            "with placeholder (manual replacement required)"
        )
    return out, warnings, blocks

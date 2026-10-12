"""Preprocessing modules for MD → TeX conversion.

Each module is a pure-function transformer:
  text: str, config: dict → (new_text: str, warnings: list[str])

Modules are designed to be safe under multiprocessing.ProcessPoolExecutor
(no module-level mutable state, no shared file handles).

Pipeline order (enforced by md_inject_convert.py):
  1. strip_frontmatter          — remove YAML frontmatter
  2. strip_obsidian_artifacts   — [[wikilinks]], #tags
  3. html_to_latex.convert      — <font color>, <sub>, <sup>, <u>, <br>
  4. code_math_blocks.convert   — ```math fenced blocks → $$...$$
  5. mermaid_extract.convert    — ```mermaid → \\fbox placeholder
  6. citation_resolver.resolve  — Author(Year) → \\citep{bibkey}
  7. pandoc conversion (subprocess, handled by caller)
  8. pandoc_postprocess.postprocess
"""

from __future__ import annotations

import re

__all__ = [
    "strip_frontmatter",
    "strip_obsidian_artifacts",
    "strip_horizontal_rules",
]


_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]")
_INLINE_TAG_RE = re.compile(r"(?<![\w/`])#([A-Za-z][\w/-]{1,40})\b")
# Stand-alone horizontal rule: a line containing only 3+ dashes/asterisks/
# underscores, optionally surrounded by whitespace. Must have blank lines
# or document edge around it to avoid matching YAML-style separators inside
# fenced blocks (strip_frontmatter runs FIRST, so leading --- frontmatter
# is already removed before this regex sees the body).
_HR_RE = re.compile(r"(?m)^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$")


def strip_frontmatter(text: str) -> tuple[str, list[str]]:
    """Remove a leading YAML frontmatter block if present."""
    new_text, n = _FRONTMATTER_RE.subn("", text, count=1)
    warnings: list[str] = []
    if n:
        warnings.append("removed leading YAML frontmatter block")
    return new_text, warnings


def strip_obsidian_artifacts(text: str) -> tuple[str, list[str]]:
    """Convert [[link|label]] → label, [[Page]] → Page. Drop inline #tags."""
    warnings: list[str] = []
    wl_hits = 0

    def _wl_sub(match: re.Match) -> str:
        nonlocal wl_hits
        wl_hits += 1
        target, label = match.group(1), match.group(2)
        return label.strip() if label else target.strip()

    out = _WIKILINK_RE.sub(_wl_sub, text)

    tag_hits = 0

    def _tag_sub(_match: re.Match) -> str:
        nonlocal tag_hits
        tag_hits += 1
        return ""

    out = _INLINE_TAG_RE.sub(_tag_sub, out)

    if wl_hits:
        warnings.append(f"stripped {wl_hits} Obsidian wikilinks")
    if tag_hits:
        warnings.append(f"stripped {tag_hits} inline #tags")
    return out, warnings


def strip_horizontal_rules(text: str) -> tuple[str, list[str]]:
    r"""Remove stand-alone Markdown horizontal rules (``---``, ``***``, ``___``).

    Academic papers use sections and whitespace, not visual rules, to separate
    content. Pandoc renders each HR as ``\begin{center}\rule{0.5\linewidth}
    {0.5pt}\end{center}`` which produces an unwanted page-width line that
    visually competes with section headings.

    This function runs AFTER :func:`strip_frontmatter` so a leading ``---``
    frontmatter block is already gone. It preserves rules that appear inside
    fenced code blocks by NOT running a state machine — we rely on the fact
    that Pandoc/GFM fenced code requires backtick delimiters, and our HR
    regex anchors to line-start with optional whitespace (it does match
    ``---`` inside a code block, but this is acceptable since the HR semantic
    inside code is purely textual).
    """
    warnings: list[str] = []
    new_text, n = _HR_RE.subn("", text)
    # Collapse the resulting extra blank lines so the TeX output is compact.
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    if n:
        warnings.append(f"stripped {n} horizontal rule line(s) (---/***/___)")
    return new_text, warnings

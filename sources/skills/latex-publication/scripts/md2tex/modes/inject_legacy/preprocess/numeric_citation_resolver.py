r"""Numeric [N] citation resolver for IEEE / ACM number-style bibliographies.

Many Korean-authored CS papers use the IEEE/ACM numeric style:

    본문: "Omohundro [1]는 ...", "Greenblatt et al.~[2]은 ..."
    말미: "## References
           [1] S. Omohundro, "The basic AI drives," in Proc. AGI, 2008.
           [2] R. Greenblatt, C. Shlegeris, ..., arXiv:2412.14093, 2024."

Pandoc's default treatment leaves both the inline ``[1]`` and the bibliography
as literal text: the ``[1]`` becomes ``{[}1{]}`` in LaTeX (no ``\cite``), and
bibtex finds no citations so ``\bibliography`` produces an empty Reference
section. This is the behaviour documented as **F2** in the skill test report.

This module runs during MD pre-processing — BEFORE pandoc sees the text — and
performs three transformations atomically:

1. **Extract numeric bibliography.** Scan the MD tail for a ``## References``
   (or ``## Bibliography`` / ``## 참고문헌`` etc.) section whose entries match
   ``[N] ...`` on their own lines. Parse each entry into a minimal BibTeX
   record and write an auto-generated ``.bib`` file alongside the fragment
   cache. The generated key is ``ref<N>`` (e.g. ``ref1``, ``ref2`` …).
2. **Rewrite inline citations.** Replace every ``[N]`` in the body (outside
   of code fences, math blocks, and Markdown link references ``[text](url)``)
   with ``\cite{ref<N>}``. Adjacent runs like ``[1, 2, 5]`` or ``[1-3]`` are
   collapsed into a single ``\cite{ref1,ref2,ref5}``.
3. **Strip the bibliography section.** The ``## References`` block is removed
   from the body (its content now lives in the auto-generated .bib). The
   caller must ensure ``\bibliography{<auto-bib-path>}`` exists in main.tex
   — we emit a warning reminding the author.

Korean section headings supported: ``참고문헌``, ``인용문헌``, ``참고 문헌``.

Safety:
  * ASCII ``[N]`` inside fenced code or inline-code spans is preserved.
  * Pandoc image refs ``![alt](url)`` and link refs ``[text](url)`` are
    preserved (we only rewrite bracketed numbers NOT followed by ``(``).
  * Numbers > 999 are ignored (they are almost certainly section numbers or
    data, not citations).
  * If no numeric bibliography is detected, this module is a no-op.

This module is pure-functional; writing the auto-bib to disk is the ONLY side
effect and the caller controls the path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "NumericRefEntry",
    "NumericCiteResult",
    "resolve_numeric_citations",
]


# ── Section header aliases ─────────────────────────────────────
# Matches at line start; accepts ``##`` or ``###`` heading level with any
# trailing whitespace/number. One of the accepted titles (case-insensitive
# for ASCII; literal for Korean).
_REF_HEADER_RE = re.compile(
    r"(?im)^\#{2,3}\s*(?:\d+\.?\s*)?"
    r"(?:references?|bibliography|참고문헌|참고\s*문헌|인용문헌)\s*\n",
)

# Entry line: "[N] …" possibly followed by continuation lines until blank or
# next entry. We capture the full block by a non-greedy sweep inside
# _split_entries().
_ENTRY_START_RE = re.compile(r"^\[\s*(\d{1,3})\s*\]\s*(.*)$")

# Inline citation matches (body pass):
#   [1]               → single
#   [1, 2, 5]         → comma list
#   [1-3]             → range
#   [1,2-4,7]         → mixed
# Negative-lookahead '(' excludes MD link refs `[label](url)`.
# Negative-lookbehind '!' excludes image refs `![alt](url)`.
_INLINE_NUMERIC_RE = re.compile(
    r"(?<!!)\[(?P<nums>\s*\d{1,3}(?:\s*[,\-]\s*\d{1,3})*\s*)\](?!\()"
)

# Code fence / inline-code guards. We walk line-by-line and skip regions.
_FENCE_OPEN_RE = re.compile(r"^\s*(`{3,}|~{3,})(\S*)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+?`")

# Display math and inline math guards (needed because $\citep{$ would break
# math). Pandoc's `tex_math_dollars` handles $...$ and $$...$$.
_DISPLAY_MATH_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\\)\$[^\$\n]+?(?<!\\)\$")


@dataclass
class NumericRefEntry:
    number: int
    raw_text: str                 # "S. Omohundro, \"The basic AI drives,\" ..."
    bib_key: str                  # "ref1"
    title: str = ""
    author: str = ""
    year: str = ""
    venue: str = ""
    eprint: str = ""              # arXiv ID if detected


@dataclass
class NumericCiteResult:
    text: str
    bib_entries: list[NumericRefEntry] = field(default_factory=list)
    auto_bib_path: str | None = None    # populated by caller
    n_inline_rewritten: int = 0
    n_inline_unresolved: int = 0        # [N] where N has no matching entry
    warnings: list[str] = field(default_factory=list)


# ── Entry parser ───────────────────────────────────────────────
_ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)(\d{2})\b")
_TITLE_QUOTED_RE = re.compile(r'"([^"]+?)[,."]')
_TITLE_TICKED_RE = re.compile(r"[“‘]([^”’]+?)[,.”’]")
# Markdown emphasis as title fallback: *Book Title*
_TITLE_ITALIC_RE = re.compile(r"(?<![\*\w])\*([^*\n]{3,200}?)\*(?!\*)")


def _format_authors(raw: str) -> str:
    """Normalize a raw IEEE/ACM author string to BibTeX's ``A and B and C`` form.

    Handles the common patterns we see in Korean-authored CS papers:

      * ``S. Omohundro``                         → ``S. Omohundro``
      * ``R. Greenblatt, C. Shlegeris, et al.``  → ``R. Greenblatt and C. Shlegeris and others``
      * ``A. Tversky and D. Kahneman``           → ``A. Tversky and D. Kahneman``
      * ``R. Schaeffer, B. Miranda, and S. Koyejo`` → ``R. Schaeffer and B. Miranda and S. Koyejo``

    The critical bits:
      * Strip trailing "et al." (in any comma position) and append ``others``.
      * Remove leading ``and`` from each comma-split segment (Oxford-comma
        artefact: the last author often reads ``, and S. Koyejo``).
      * Strip trailing comma and period — the ACM-Reference-Format .bst
        emits a "Name 1 has a comma at the end" error otherwise.
    """
    raw = raw.strip()
    # Drop any trailing period/comma on the whole block.
    raw = re.sub(r"[,.]+\s*$", "", raw)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    # Strip leading "and " from Oxford-comma segments.
    parts = [re.sub(r"^and\s+", "", p, flags=re.IGNORECASE) for p in parts]
    # Detect & strip "et al." wherever it appears.
    has_etal = False
    cleaned: list[str] = []
    for p in parts:
        low = p.lower().rstrip(".").strip()
        if low in {"et al", "others"}:
            has_etal = True
            continue
        # Also handle "X et al." attached to a name (rare).
        sub = re.sub(r"\s+et\s+al\.?\s*$", "", p, flags=re.IGNORECASE)
        if sub != p:
            has_etal = True
        if sub.strip():
            cleaned.append(sub.strip().rstrip(","))
    if has_etal:
        cleaned.append("others")
    return " and ".join(cleaned) if cleaned else raw


def _parse_entry_text(raw: str) -> dict[str, str]:
    """Extract author / title / year / venue / arXiv-id from a single entry.

    Heuristic best-effort — the goal is a plausible BibTeX record, not
    perfect bibliography parsing.

    The extraction order matters: arXiv IDs like ``1906.01820`` share the
    same shape as a 4-digit year prefix, so we strip arXiv references BEFORE
    scanning for the year — otherwise Hubinger 2019 gets a year of ``1906``.
    """
    fields: dict[str, str] = {}

    arxiv = _ARXIV_RE.search(raw)
    if arxiv:
        fields["eprint"] = arxiv.group(1)

    # Extract year from text with arXiv IDs removed so their 4-digit
    # prefix doesn't leak.
    year_search_text = _ARXIV_RE.sub("", raw)
    year_m = _YEAR_RE.search(year_search_text)
    if year_m:
        fields["year"] = year_m.group(1) + year_m.group(2)

    # Title: prefer ASCII double-quoted, else typographic quotes, else
    # Markdown italic *Book Title* (for books without quoted titles).
    tm = (
        _TITLE_QUOTED_RE.search(raw)
        or _TITLE_TICKED_RE.search(raw)
        or _TITLE_ITALIC_RE.search(raw)
    )
    if tm:
        fields["title"] = tm.group(1).strip()

    # Author region: everything BEFORE the title start (first ", <quote>" or
    # first "*" for italic). If no title delimiter is present, treat the
    # region up to the first period+space as author and rest as venue.
    split_idx = tm.start() if tm else len(raw)
    if not tm:
        # No title delimiter — use first ". " as author/venue boundary.
        period_m = re.search(r"\.\s+", raw)
        if period_m:
            split_idx = period_m.start()
    author_raw = raw[:split_idx]
    fields["author"] = _format_authors(author_raw)

    # Venue: everything AFTER the title region. Strip the title's trailing
    # delimiter (quote or asterisk) plus arXiv/year so they don't duplicate.
    after = raw[tm.end():] if tm else raw[split_idx:]
    venue = _ARXIV_RE.sub("", after)
    venue = re.sub(r"\b(19|20)\d{2}\b", "", venue, count=1)
    # Strip Markdown emphasis markers that survived from the input.
    venue = re.sub(r"\*+", "", venue)
    # Remove stray leading/trailing punctuation and collapse whitespace.
    venue = re.sub(r"\s{2,}", " ", venue).strip(" ,.\"'\t\n")
    if venue:
        fields["note"] = venue

    return fields


def _split_entries(ref_block: str) -> list[tuple[int, str]]:
    """Split a References block into [(number, full_text), …].

    Continuation lines (indented or non-[N] starts) are folded into the
    current entry.
    """
    out: list[tuple[int, str]] = []
    current_num: int | None = None
    current_buf: list[str] = []

    for line in ref_block.splitlines():
        m = _ENTRY_START_RE.match(line.strip())
        if m:
            if current_num is not None:
                out.append((current_num, " ".join(current_buf).strip()))
            current_num = int(m.group(1))
            current_buf = [m.group(2).strip()]
        elif current_num is not None and line.strip():
            current_buf.append(line.strip())
        # blank line: keep accumulating; next [N] or EOF ends entry
    if current_num is not None:
        out.append((current_num, " ".join(current_buf).strip()))
    return out


def _extract_ref_block(md_text: str) -> tuple[str, int, int] | None:
    """Locate the numeric-bibliography block, return (block_text, start_off,
    end_off) OR None if not found.

    The block runs from the ``## References`` header to EOF OR the next H1/H2
    that isn't another references alias.
    """
    m = _REF_HEADER_RE.search(md_text)
    if not m:
        return None
    body_start = m.end()
    # Find the next H1/H2 heading AFTER body_start.
    next_heading = re.search(
        r"(?m)^\#{1,2}\s+", md_text[body_start:]
    )
    body_end = body_start + next_heading.start() if next_heading else len(md_text)
    block = md_text[body_start:body_end]
    return block, m.start(), body_end


# ── Body rewriter ──────────────────────────────────────────────
def _expand_nums(raw: str) -> list[int]:
    """Parse '1, 2-4, 7' → [1,2,3,4,7] (keeps order, dedupes)."""
    out: list[int] = []
    seen: set[int] = set()
    for part in (p.strip() for p in raw.split(",") if p.strip()):
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                lo, hi = int(a), int(b)
            except ValueError:
                continue
            if lo > hi:
                lo, hi = hi, lo
            for n in range(lo, hi + 1):
                if n not in seen:
                    seen.add(n)
                    out.append(n)
        else:
            try:
                n = int(part)
            except ValueError:
                continue
            if n not in seen:
                seen.add(n)
                out.append(n)
    return out


def _rewrite_body_citations(
    body: str,
    valid_nums: set[int],
    result: NumericCiteResult,
) -> str:
    """Replace inline [N] runs with \\cite{refN,...} outside guarded regions."""
    # Carve out guarded spans: fenced code blocks + inline code + math.
    # Strategy: tokenise by regex alternation, process only 'text' tokens.

    guards: list[re.Pattern] = [
        re.compile(r"(?s)```.*?```"),
        re.compile(r"(?s)~~~.*?~~~"),
        _DISPLAY_MATH_RE,
        _INLINE_MATH_RE,
        _INLINE_CODE_RE,
    ]

    # Build a mask of protected offsets.
    protected: list[tuple[int, int]] = []
    for g in guards:
        for m in g.finditer(body):
            protected.append((m.start(), m.end()))
    protected.sort()

    def is_protected(pos: int) -> bool:
        for s, e in protected:
            if s <= pos < e:
                return True
            if s > pos:
                break
        return False

    def _sub(match: re.Match) -> str:
        if is_protected(match.start()):
            return match.group(0)
        nums = _expand_nums(match.group("nums"))
        if not nums:
            return match.group(0)
        keys: list[str] = []
        for n in nums:
            if n in valid_nums:
                keys.append(f"ref{n}")
            else:
                result.n_inline_unresolved += 1
        if not keys:
            # Entirely unresolved — leave as-is so reviewer can see.
            return match.group(0)
        result.n_inline_rewritten += 1
        return r"\cite{" + ",".join(keys) + "}"

    return _INLINE_NUMERIC_RE.sub(_sub, body)


# ── BibTeX emission ────────────────────────────────────────────
def _escape_bib(s: str) -> str:
    r"""Escape BibTeX-sensitive characters inside braced fields."""
    return s.replace("{", r"\{").replace("}", r"\}").replace("\\", r"\\")


def _entry_to_bibtex(e: NumericRefEntry) -> str:
    lines = [f"@misc{{{e.bib_key},"]
    if e.author:
        lines.append(f"  author = {{{_escape_bib(e.author)}}},")
    if e.title:
        lines.append(f"  title = {{{_escape_bib(e.title)}}},")
    if e.year:
        lines.append(f"  year = {{{_escape_bib(e.year)}}},")
    if e.venue:
        lines.append(f"  note = {{{_escape_bib(e.venue)}}},")
    if e.eprint:
        lines.append(f"  eprint = {{{_escape_bib(e.eprint)}}},")
        lines.append("  archivePrefix = {arXiv},")
    # Fall back: preserve the raw entry text so authors can repair manually.
    lines.append(f"  annote = {{{_escape_bib(e.raw_text)}}},")
    lines.append("}")
    return "\n".join(lines)


# ── Public API ─────────────────────────────────────────────────
def resolve_numeric_citations(
    md_text: str,
    *,
    auto_bib_out: Path | None = None,
    enabled: bool = True,
) -> NumericCiteResult:
    """Detect numeric bibliography in ``md_text``, rewrite inline [N] to
    ``\\cite{refN}``, and emit a companion .bib file at ``auto_bib_out``.

    Returns a :class:`NumericCiteResult`. If no numeric bibliography is
    detected the text is returned unchanged and no file is written.
    """
    result = NumericCiteResult(text=md_text)
    if not enabled:
        return result

    found = _extract_ref_block(md_text)
    if not found:
        return result

    ref_block, ref_start, ref_end = found
    pairs = _split_entries(ref_block)
    if not pairs:
        result.warnings.append(
            "detected ## References header but no '[N] ...' entries parsed"
        )
        return result

    # Build entries + valid-number set.
    valid_nums: set[int] = set()
    for num, raw in pairs:
        parsed = _parse_entry_text(raw)
        entry = NumericRefEntry(
            number=num,
            raw_text=raw,
            bib_key=f"ref{num}",
            title=parsed.get("title", ""),
            author=parsed.get("author", ""),
            year=parsed.get("year", ""),
            venue=parsed.get("note", ""),
            eprint=parsed.get("eprint", ""),
        )
        result.bib_entries.append(entry)
        valid_nums.add(num)

    # Rewrite BODY (everything BEFORE the references header).
    body = md_text[:ref_start]
    body = _rewrite_body_citations(body, valid_nums, result)

    # The references block itself is discarded from the MD; bibtex will
    # render it instead.
    tail = md_text[ref_end:]
    result.text = body.rstrip() + ("\n\n" + tail.lstrip() if tail.strip() else "\n")

    # Write auto-bib if a path was supplied.
    if auto_bib_out is not None:
        auto_bib_out.parent.mkdir(parents=True, exist_ok=True)
        bib_lines = [
            "% Auto-generated by latex-korean-setup "
            "numeric_citation_resolver.",
            "% Source: numeric [N] bibliography extracted from MD.",
            "% Manual edits to this file are OK but will be overwritten on "
            "re-injection.",
            "",
        ]
        for e in result.bib_entries:
            bib_lines.append(_entry_to_bibtex(e))
            bib_lines.append("")
        auto_bib_out.write_text("\n".join(bib_lines), encoding="utf-8")
        result.auto_bib_path = str(auto_bib_out)

    result.warnings.append(
        f"extracted {len(result.bib_entries)} numeric reference(s) → "
        f"{result.auto_bib_path or '(in-memory only)'}; "
        f"rewrote {result.n_inline_rewritten} inline [N] span(s) "
        f"to \\cite{{refN}}. ** Add \\bibliography{{<path>}} in main.tex. **"
    )
    if result.n_inline_unresolved:
        result.warnings.append(
            f"{result.n_inline_unresolved} inline [N] number(s) had no "
            "matching entry and were left as literal brackets"
        )
    return result

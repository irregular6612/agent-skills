r"""Resolve Author(Year) patterns in MD prose to \citep{bibkey}.

Strategy:
  1. Parse references.bib once per run → build two indices:
       (surname_lower, year_int)           → bibkey
       (surname_lower, year_int, etal)     → bibkey   (etal is bool)
     When multiple entries collide on (surname, year), the resolver
     keeps all candidates and refuses to auto-rewrite (emits a warning
     instead of guessing).
  2. Scan MD body for:
       Surname(Year)
       Surname (Year)
       Surname et al. (Year)
       Surname & Other (Year)        ← falls back to warning only
       "Surname et al., Year"         ← parenthetical comma style
     Ambiguous/collision hits produce warnings without rewriting.
  3. Normalize any existing `\cite{key}` -> `\citep{key}` (natbib
     authoryear compatibility, per gist-preprint.sty:67).

Korean text is passed through untouched. A Korean surname will never
match the [A-Z] prefix of the regex, so false positives on Korean
content are near-zero.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

__all__ = ["BibIndex", "build_bib_index", "resolve", "ResolveResult"]


# ── BibTeX parsing ───────────────────────────────────────────────
_ENTRY_RE = re.compile(
    r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,\s]+)\s*,(?P<body>.*?)\n\}\s*(?=@|\Z)",
    re.DOTALL,
)
_FIELD_RE = re.compile(
    r"(?P<field>\w+)\s*=\s*(?:\{(?P<braced>.*?)\}|\"(?P<quoted>.*?)\"|(?P<bare>[^,\n]+))",
    re.DOTALL,
)


@dataclass
class BibEntry:
    key: str
    type_: str
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def year(self) -> int | None:
        y = self.fields.get("year", "").strip()
        m = re.search(r"(\d{4})", y)
        return int(m.group(1)) if m else None

    @property
    def first_author_surname(self) -> str | None:
        """Return lowercase surname of the first author.

        Handles both "Last, First" and "First Middle Last" formats. For
        multiple authors separated by ' and ', takes the first.
        """
        raw = self.fields.get("author") or self.fields.get("editor") or ""
        raw = _strip_braces(raw).strip()
        if not raw:
            return None
        first = raw.split(" and ")[0].strip()
        if "," in first:
            surname = first.split(",", 1)[0].strip()
        else:
            # "First Middle Last" → take the last whitespace-separated token
            tokens = first.split()
            surname = tokens[-1] if tokens else ""
        surname = re.sub(r"[{}\\]", "", surname).strip()
        return surname.lower() or None


def _strip_braces(s: str) -> str:
    # Peel one layer of braces if the whole field is wrapped
    s = s.strip()
    while s.startswith("{") and s.endswith("}"):
        s = s[1:-1].strip()
    # Collapse internal {X} wrappers around single tokens
    return re.sub(r"\{([^{}]*)\}", r"\1", s)


def _parse_bib_text(text: str) -> list[BibEntry]:
    # Strip full-line comments starting with %
    cleaned = re.sub(r"(?m)^%.*$", "", text)
    entries: list[BibEntry] = []
    for m in _ENTRY_RE.finditer(cleaned):
        key = m.group("key").strip()
        type_ = m.group("type").strip().lower()
        if type_ in {"comment", "preamble", "string"}:
            continue
        body = m.group("body")
        fields: dict[str, str] = {}
        for fm in _FIELD_RE.finditer(body):
            name = fm.group("field").strip().lower()
            val = fm.group("braced") or fm.group("quoted") or fm.group("bare") or ""
            fields[name] = _strip_braces(val.strip().rstrip(","))
        entries.append(BibEntry(key=key, type_=type_, fields=fields))
    return entries


# ── Index ────────────────────────────────────────────────────────
class BibIndex:
    """Maps (surname_lower, year) → list[bibkey]. Ambiguous hits stay as lists."""

    def __init__(self, entries: list[BibEntry]) -> None:
        self._by_sy: dict[tuple[str, int], list[str]] = defaultdict(list)
        self._keys: set[str] = set()
        for e in entries:
            surname = e.first_author_surname
            year = e.year
            self._keys.add(e.key)
            if surname and year is not None:
                self._by_sy[(surname, year)].append(e.key)

    def lookup(self, surname: str, year: int) -> list[str]:
        return list(self._by_sy.get((surname.lower(), year), []))

    def has_key(self, key: str) -> bool:
        return key in self._keys

    @property
    def size(self) -> int:
        return sum(len(v) for v in self._by_sy.values())


def build_bib_index(bib_paths: Iterable[Path | str]) -> BibIndex:
    all_entries: list[BibEntry] = []
    for p in bib_paths:
        path = Path(p)
        if not path.exists():
            continue
        try:
            all_entries.extend(_parse_bib_text(path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            all_entries.extend(
                _parse_bib_text(path.read_text(encoding="utf-8", errors="replace"))
            )
    return BibIndex(all_entries)


# ── Citation rewriting ───────────────────────────────────────────
# Matches:
#   Smith(2024)           Smith (2024)
#   Smith et al. (2024)   Smith et al.(2024)
#   Smith et al., 2024    (inside parens only)
# Accepts hyphens and dotless initials in surnames, rejects lowercase leading.
_AUTHOR_YEAR_RE = re.compile(
    r"""
    (?P<pre>(?<![\w\\{])
           (?<!\\cite)(?<!\\citet)(?<!\\citep)
           (?<!\*\*)(?<!_))
    (?P<surname>[A-Z][A-Za-z\-]{1,30})
    (?P<etal>\s+et\s+al\.?)?
    \s*\(\s*(?P<year>\d{4})\s*\)
    """,
    re.VERBOSE,
)

# Parenthetical comma-style:  (Smith et al., 2024; Jones, 2020)
_PAREN_COMMA_RE = re.compile(
    r"""
    \(
    (?P<inner>
        [A-Z][A-Za-z\-]{1,30}(?:\s+et\s+al\.?)?,\s*\d{4}
        (?:\s*;\s*[A-Z][A-Za-z\-]{1,30}(?:\s+et\s+al\.?)?,\s*\d{4})*
    )
    \)
    """,
    re.VERBOSE,
)

# Normalize bare \cite{foo} → \citep{foo}. Never rewrites \citep/\citet.
_BARE_CITE_RE = re.compile(r"\\cite\{([^}]+)\}")


@dataclass
class ResolveResult:
    text: str
    n_rewritten: int = 0
    n_unmatched: int = 0
    n_ambiguous: int = 0
    n_cite_normalized: int = 0
    unmatched_samples: list[str] = field(default_factory=list)
    ambiguous_samples: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def resolve(
    text: str,
    index: BibIndex,
    *,
    enabled: bool = True,
    normalize_cite: bool = True,
    max_samples: int = 10,
) -> ResolveResult:
    r"""Run citation resolution on MD text.

    Args:
      text: Markdown source.
      index: BibIndex built from references.bib.
      enabled: if False, skip auto-rewrite but still run \cite normalization.
      normalize_cite: rewrite bare \cite{key} → \citep{key}.
      max_samples: how many unmatched/ambiguous surname(year) to collect
                   for warning surfacing.
    """
    result = ResolveResult(text=text)

    if normalize_cite:
        def _cite_sub(m: re.Match) -> str:
            key = m.group(1)
            if not index.has_key(key):
                result.warnings.append(
                    f"\\cite{{{key}}}: key not in references.bib (kept as \\citep anyway)"
                )
            result.n_cite_normalized += 1
            return rf"\citep{{{key}}}"
        result.text = _BARE_CITE_RE.sub(_cite_sub, result.text)

    if not enabled:
        return result

    def _ay_sub(match: re.Match) -> str:
        surname = match.group("surname")
        year = int(match.group("year"))
        etal = match.group("etal") or ""
        candidates = index.lookup(surname, year)
        if len(candidates) == 1:
            result.n_rewritten += 1
            return rf"\citep{{{candidates[0]}}}"
        elif len(candidates) > 1:
            result.n_ambiguous += 1
            if len(result.ambiguous_samples) < max_samples:
                result.ambiguous_samples.append(
                    f"{surname}{etal} ({year}) ambiguous: {candidates}"
                )
            return match.group(0)
        else:
            result.n_unmatched += 1
            if len(result.unmatched_samples) < max_samples:
                result.unmatched_samples.append(f"{surname}{etal} ({year})")
            return match.group(0)

    result.text = _AUTHOR_YEAR_RE.sub(_ay_sub, result.text)

    if result.n_unmatched:
        head = "; ".join(result.unmatched_samples[:3])
        result.warnings.append(
            f"{result.n_unmatched} Author(Year) not matched in references.bib "
            f"(first: {head})"
        )
    if result.n_ambiguous:
        head = "; ".join(result.ambiguous_samples[:3])
        result.warnings.append(
            f"{result.n_ambiguous} Author(Year) ambiguous (first: {head})"
        )
    return result

r"""Post-process pandoc's raw LaTeX output to fit gist-preprint-style templates.

Transforms applied in order:
  1. Drop \hypertarget{id}{%\section{X}\label{id}} -> \section{X}\label{id}
  2. Replace \passthrough{\lstinline!X!} -> \texttt{\detokenize{X}} (Korean safe)
  3. Replace \begin{Shaded}\begin{Highlighting}[] ... \end{Highlighting}\end{Shaded}
     -> \begin{lstlisting} ... \end{lstlisting}
  4. Normalize longtable column specs {@{}llll@{}} -> {@{}p{0.25\textwidth}...@{}}
  5. Optionally convert longtable environments to table* + tabular for
     2-column layout compatibility (ACM sigconf, IEEE, etc.) — controlled
     by ``PostprocessConfig.table_mode``.
  6. Strip unwanted horizontal-rule output (``\begin{center}\rule{...}\end{center}``)
     when the source ``---`` was intended as a section separator.
  7. Rewrite image paths per a mapping dict (main.tex is not always at the
     same depth as the MD source).
  8. Strip any accidental \begin{document}/\end{document} (pandoc sometimes
     emits these when the source contains raw_tex).
  9. Remove lone \newcommand/\renewcommand lines (they belong in preamble,
     not in fragments). Surface a warning with the command name so the
     author can move them to math_commands.tex manually.
 10. Detect required LaTeX packages (listings, longtable, booktabs, array,
     tabularx, verbatim) so the caller can append \usepackage{} lines to
     the preamble_additions list.
 11. Wrap in BEGIN/END sentinel comments with a content SHA1.

All functions are side-effect-free except the final hash computation.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

__all__ = [
    "PostprocessConfig",
    "PostprocessResult",
    "postprocess",
    "detect_required_packages",
]


_HYPERTARGET_RE = re.compile(
    r"\\hypertarget\{(?P<id>[^}]+)\}\{%\s*\n"
    r"(?P<body>\\(?:section|subsection|subsubsection|paragraph)\*?\{[^}]*\})"
    r"\\label\{(?P=id)\}\}",
)

_PASSTHROUGH_RE = re.compile(
    r"\\passthrough\{\\lstinline!([^!]*)!\}",
)

_SHADED_RE = re.compile(
    r"\\begin\{Shaded\}\s*\n\\begin\{Highlighting\}\[\]\s*(.*?)"
    r"\\end\{Highlighting\}\s*\n\\end\{Shaded\}",
    re.DOTALL,
)

# _LONGTABLE_COLS_RE (v1, char-class) was too restrictive: pandoc's
# calc-width column specs contain ``(``, ``)``, ``-``, ``*`` which were not
# in the safelist, so long-celled tables silently skipped normalisation,
# leaving raw ``\real{F}`` (undefined in xelatex) in the output. Round 4.
# v2 uses a brace-matched parser (``_extract_longtable_header`` +
# ``_find_longtable_headers``) instead so ANY column spec — simple or
# calc-width — is captured.
#
# Prefix still detected via regex for speed:
_LONGTABLE_START_RE = re.compile(r"\\begin\{longtable\}(?P<pre>\[\]?)\{")

# Pandoc's calc-width column: ``p{(\linewidth - N\tabcolsep) * \real{F}}``
# where F is a fractional width (0.0–1.0). Matching this with balanced
# braces in mind means we look for the whole p{ ... } token from the
# outside.
_PANDOC_CALC_COL_RE = re.compile(
    r"(?:>\s*\{[^}]*\}\s*)?"            # optional >{\raggedright\arraybackslash}
    r"p\{[^{}]*\\real\{(?P<frac>\d*\.?\d+)\}\s*\}",
)

_NEWCMD_RE = re.compile(
    r"^\\(?:re)?newcommand\{\\([A-Za-z@]+)\}(?:\[\d+\])?\{[^\n]*\}\s*$",
    re.MULTILINE,
)

_DOCENV_RE = re.compile(
    r"^\\(?:begin|end)\{document\}\s*$",
    re.MULTILINE,
)

# Pandoc wraps caption-less longtables in
#   {\def\LTcaptype{none} % do not increment counter
#   \begin{longtable}...\end{longtable}
#   }
# `\LTcaptype{none}` requires a `none` counter; recent longtable versions
# fail with "No counter 'none' defined". We strip the wrapper entirely
# (the inner longtable works without it).
_LTCAPTYPE_OPEN_RE = re.compile(
    r"^\{\\def\\LTcaptype\{none\}[^\n]*\n",
    re.MULTILINE,
)

# Horizontal rule output from pandoc's ``---`` horizontal rule directive.
# Matches both with and without trailing newlines. Our preprocess strips
# ``---`` before pandoc, but some authors emit raw ``\rule`` in .md that
# pandoc passes through, so we also clean up the post-output form.
_HR_OUTPUT_RE = re.compile(
    r"\\begin\{center\}\s*\\rule\{[^}]+\}\{[^}]+\}\s*\\end\{center\}\s*",
)

# Detect an MD-authored numeric prefix at the start of a section title,
# e.g. ``\section{1. 서론}`` or ``\subsection{3.1 2층 직교 설계}``. LaTeX
# adds its own \thesection counter, so preserving the manual prefix
# produces ``1 1. 서론`` in the rendered PDF.  Captures the following
# shapes:
#   ``1.``, ``1.1``, ``1.1.``, ``2.3.4`` (with or without trailing dot)
# followed by a space or Korean/English heading text. Does NOT match
# single-digit identifiers in algorithms or equation titles (those go
# in \subsubsection or \paragraph in practice).
_SECTION_NUM_RE = re.compile(
    r"(\\(?:section|subsection|subsubsection|paragraph)\*?\{)"
    r"(?P<num>\d+(?:\.\d+)*\.?)[\s ]+"
    r"(?P<rest>[^}]+)"
)

# v1 used ``\{(?P<cols>[^}]*)\}`` for cols, which stopped at the first
# ``}`` — for pandoc's calc-width specs this means cols was captured as
# ``@{`` only (the rest of the header leaked into the body, producing
# broken tabular). Replaced by brace-matched parsing in
# ``_iter_longtable_blocks``. Regex kept for body-end lookup only.
_LONGTABLE_END_RE = re.compile(r"\\end\{longtable\}")

# Bare math-operator macros used as ``_\op`` / ``^\op`` without braces.
# ``\max`` / ``\min`` / ``\sup`` / etc. expand (via amsmath's
# ``\DeclareMathOperator*``) to a ``\mathop{…}`` sequence that cannot be
# absorbed by ``_`` / ``^`` directly — xelatex reports "! Missing {
# inserted. … \mathop". Authors commonly write ``$\tau_\max$`` as a
# shorthand for ``$\tau_{\max}$`` in Markdown; we auto-wrap here so the
# build succeeds without nagging the author. The whitelist is the
# amsmath-declared operators (see ``latex/required/amsmath/amsopn.dtx``).
_BARE_MATH_OP_RE = re.compile(
    r"(?P<pos>[_^])\\(?P<op>"
    r"max|min|sup|inf|lim|limsup|liminf|argmax|argmin"
    r"|det|dim|ker|gcd|lcm|Pr|exp|log|ln"
    r"|sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan"
    r"|sinh|cosh|tanh|coth|deg|hom"
    r")\b(?!\{)",
)

# ── Required-package detection ────────────────────────────────
# Maps the LaTeX signature (env or command) that appears in the fragment
# onto the LaTeX package that must be \usepackaged for it to work.
_PACKAGE_TRIGGERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\\begin\{lstlisting\}"), "listings"),
    (re.compile(r"\\begin\{longtable\}"), "longtable"),
    (re.compile(r"\\toprule|\\midrule|\\bottomrule|\\cmidrule"), "booktabs"),
    (re.compile(r"\\begin\{tabularx\}"), "tabularx"),
    # ``array`` provides \arraybackslash / >{...} / p{...} adjustments
    # that pandoc's longtable output relies on. Round 4: previously we
    # only matched \begin{array} / \newcolumntype, missing the common
    # ``>{\raggedright\arraybackslash}p{...}`` cell directives, which
    # then triggered "Undefined control sequence: \arraybackslash" at
    # build time.
    (
        re.compile(
            r"\\begin\{array\}|^\s*\\newcolumntype|\\arraybackslash\b",
            re.MULTILINE,
        ),
        "array",
    ),
    (re.compile(r"\\begin\{Verbatim\}"), "fancyvrb"),
    (re.compile(r"\\includegraphics"), "graphicx"),
    (re.compile(r"\\textcolor\{|\\color\{"), "xcolor"),
    (re.compile(r"\\hyperref|\\hypertarget|\\href"), "hyperref"),
    # Round 4.6: the display-math shrink wrapper emits \adjustbox{max
    # width=...}. Detect both the command and the env form.
    (re.compile(r"\\adjustbox\{|\\begin\{adjustbox\}"), "adjustbox"),
]


@dataclass
class PostprocessConfig:
    source_relpath: str = "<unknown>"
    source_sha1: str = ""
    image_path_rewrites: dict[str, str] = field(default_factory=dict)
    include_sentinels: bool = True
    columns_width_fraction: float = 0.25
    # How to render tables:
    #   "longtable" — leave pandoc's longtable untouched (original behaviour;
    #                 only safe in 1-column layouts)
    #   "table-star" — convert every longtable to table* + tabular (safe in
    #                 both 1-column and 2-column modes, but loses
    #                 page-spanning)
    #   "auto" — same as "table-star" (default; conservative for ACM/IEEE
    #                 2-column templates)
    table_mode: str = "auto"
    # Strip MD-authored numeric prefix from section titles (e.g.
    # ``\section{1. 서론}`` → ``\section{서론}``) so LaTeX's auto-numbering
    # doesn't duplicate with the prefix.  Set False when section titles
    # genuinely contain leading numbers that must be preserved (e.g.
    # mathematical / chemical nomenclature).
    strip_section_number_prefix: bool = True
    # Unwrap pandoc ``\begin{quote}...\end{quote}`` blocks. Markdown
    # authors reach for ``> ...`` as a "callout" marker (Obsidian, GitHub
    # admonitions) but in 2-column class the quote environment inherits
    # paragraph indentation that visually collides with the border. Round
    # 4.5: user explicitly asked to drop the callout frame and keep only
    # the source text. Set False to keep ``\begin{quote}`` intact.
    unwrap_blockquotes: bool = True
    # Strip ``\textbf{...}`` when the content looks like prose emphasis
    # rather than a named label. Heuristic: length > 12 Unicode chars OR
    # contains sentence punctuation (``.,:;``). Short labels like
    # ``\textbf{IV}``, ``\textbf{α 보존}`` are preserved. Round 4.5: user
    # requested because Korean prose conventions rarely use bold for
    # mid-paragraph emphasis.
    strip_prose_bold: bool = True
    # Maximum character length below which a ``\textbf{...}`` is treated
    # as a label/name and kept.
    prose_bold_max_len: int = 12
    # Detect a trailing italic paragraph matching ``(Figure|Table|표|
    # 그림)\s*\d+`` immediately after a table*/figure*/minipage block and
    # move it inside as ``\caption{...}``. Round 4.5: user requested for
    # MD documents that put captions below instead of pandoc-native
    # ``Table: ...`` syntax.
    attach_trailing_captions: bool = True
    # Wrap ``\[...\]`` display math in ``\adjustbox{max
    # width=\columnwidth}`` when the body length exceeds the threshold
    # below. Round 4.6 — fixes the case where a single long one-line
    # formula (e.g. ``FSPM-Score_A = E_t,seeds [max(0, θ_t − p_forfeit(t))
    # · 1[Survival]] − E_t,seeds [· 1[Neutral]]`` ~230 chars) silently
    # overflows the right column margin in 2-column classes.
    shrink_wide_display_math: bool = True
    # Character threshold. Bodies shorter than this are left unwrapped
    # (short formulae render at their natural \displaystyle size). Tuned
    # so the typical 1-line inline-display math on a two-column layout
    # (column width ~3in ≈ 60–80 chars of math) isn't unnecessarily
    # wrapped.
    display_math_shrink_threshold: int = 120


@dataclass
class PostprocessResult:
    text: str
    warnings: list[str] = field(default_factory=list)
    required_packages: list[str] = field(default_factory=list)
    # Optional LaTeX snippets the caller should inject into the preamble
    # ABOVE ``\begin{document}`` (as opposed to full ``\usepackage{}``
    # lines, which live in ``required_packages``). Used for lstset
    # configuration, fancyvrb setup, etc.
    preamble_snippets: list[str] = field(default_factory=list)
    n_longtable_converted: int = 0


def _find_matching_brace(text: str, open_idx: int) -> int:
    """Return the index just past the ``}`` that closes the ``{`` at
    ``open_idx``. Depth-aware — correctly pairs nested ``{`` / ``}``
    pairs (pandoc's calc-width column spec contains ``\\real{F}`` inside
    the outer ``p{...}``, so a naïve ``str.find("}")`` would mis-stop).

    Returns ``-1`` if unbalanced (caller should give up on this header).
    """
    assert text[open_idx] == "{", (
        f"expected '{{' at {open_idx} but got {text[open_idx]!r}"
    )
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            # Skip escaped character (e.g. ``\{``, ``\}``) so it doesn't
            # count for depth.
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _iter_longtable_headers(text: str):
    """Yield ``(start, header_end, pre, cols_str)`` for each
    ``\\begin{longtable}...{...}`` header. ``cols_str`` is the literal
    content between the header's matched ``{`` and ``}`` (outer braces
    excluded). Uses brace-matched parsing so calc-width specs (which
    contain nested ``{...}``) are captured correctly.
    """
    for m in _LONGTABLE_START_RE.finditer(text):
        start = m.start()
        open_idx = m.end() - 1  # the ``{`` at the end of the match
        close_idx = _find_matching_brace(text, open_idx)
        if close_idx < 0:
            continue  # unbalanced — skip this one
        cols_str = text[open_idx + 1 : close_idx - 1]
        pre = m.group("pre") or ""
        yield start, close_idx, pre, cols_str


def _split_column_spec(cols: str) -> list[str]:
    """Split a longtable cols-spec into column tokens, depth-aware.

    Tokens retained:
      * ``@{...}`` — intercolumn directives (outer braces included)
      * ``>{...}`` — pre-cell directives (outer braces included)
      * ``p{...}``, ``m{...}``, ``b{...}`` — fixed-width columns
      * ``l`` / ``c`` / ``r`` — single-char columns
      * ``X`` — tabularx flex column
    Whitespace between tokens is dropped.
    """
    out: list[str] = []
    i = 0
    n = len(cols)
    while i < n:
        ch = cols[i]
        if ch.isspace():
            i += 1
            continue
        if ch in {"l", "c", "r", "X"}:
            out.append(ch)
            i += 1
        elif ch in {"p", "m", "b", "@", ">", "<", "!"} and i + 1 < n and cols[i + 1] == "{":
            j = _find_matching_brace(cols, i + 1)
            if j < 0:
                # Unbalanced — fall back and take the rest as one token.
                out.append(cols[i:])
                break
            out.append(cols[i:j])
            i = j
        else:
            # Unknown character — keep it verbatim so we don't silently
            # drop user-custom column modifiers (e.g. ``|``, ``*``).
            out.append(ch)
            i += 1
    return out


def _is_pandoc_calc_pcol(token: str) -> bool:
    """True iff token is a pandoc calc-width ``p{...}`` (contains
    ``\\real{...}``). Plain ``p{5cm}`` returns False — those are
    author-authored and should be preserved."""
    return token.startswith("p{") and "\\real{" in token


def _normalize_column_spec(cols: str) -> str:
    """Rewrite every variable-width column to a simple
    ``p{frac\\textwidth}`` of equal share. Fixed-width ``p{5cm}``,
    ``X``, and ``@{...}`` / ``>{...}`` tokens are preserved.

    Variable-width columns are:
      * ``l`` / ``c`` / ``r``
      * pandoc calc-width ``p{(\\linewidth - N\\tabcolsep) * \\real{F}}``
    """
    tokens = _split_column_spec(cols)
    variable_idx: list[int] = []
    for idx, tok in enumerate(tokens):
        if tok in {"l", "c", "r"} or _is_pandoc_calc_pcol(tok):
            variable_idx.append(idx)
    if not variable_idx:
        return cols  # nothing to rewrite
    count = len(variable_idx)
    # 0.85/N leaves ~15% for intercolumn \tabcolsep padding so the
    # rightmost column doesn't clip off the page edge. Round 3 calibrated
    # this value on 5-column tables; same constant re-used here.
    frac = round(0.85 / max(count, 2) * 1000) / 1000
    width = rf"p{{{frac}\textwidth}}"
    for idx in variable_idx:
        tokens[idx] = width
    return "".join(tokens)


# Back-compat shim: the old public name ``_expand_column_spec`` is kept
# so external callers / tests that import it continue to work. Internally
# everything uses ``_normalize_column_spec`` which handles the full set
# of pandoc output shapes.
def _expand_column_spec(cols: str) -> str:  # pragma: no cover — shim
    return _normalize_column_spec(cols)


def _fix_longtable_columns(text: str) -> tuple[str, int]:
    """Rewrite every ``\\begin{longtable}...{cols}`` header so ``cols``
    only contains fixed-width / X columns. Leaves the body intact.
    """
    count = 0
    # Collect replacements first, apply back-to-front so slice offsets
    # stay valid.
    rewrites: list[tuple[int, int, str]] = []
    for start, end, pre, cols_str in _iter_longtable_headers(text):
        new_cols = _normalize_column_spec(cols_str)
        if new_cols == cols_str:
            continue
        count += 1
        replacement = rf"\begin{{longtable}}{pre}{{{new_cols}}}"
        rewrites.append((start, end, replacement))
    if not rewrites:
        return text, 0
    out_parts: list[str] = []
    cursor = 0
    for start, end, replacement in rewrites:
        out_parts.append(text[cursor:start])
        out_parts.append(replacement)
        cursor = end
    out_parts.append(text[cursor:])
    return "".join(out_parts), count


def _longtable_to_tabular(text: str) -> tuple[str, int]:
    r"""Convert ``\begin{longtable}...\end{longtable}`` → ``\begin{table*}
    \centering\small\begin{tabular}...\end{tabular}\end{table*}``.

    Strips longtable-specific control commands (``\endfirsthead``,
    ``\endhead``, ``\endfoot``, ``\endlastfoot``, and any stray
    ``\noalign{}``) that would trigger "command not available in tabular"
    errors. Retains ``\toprule/\midrule/\bottomrule`` which come from
    booktabs and work identically in tabular.

    The caller is responsible for:
      * ``\usepackage{booktabs,longtable,array}`` in the preamble
        (``detect_required_packages`` marks these for inclusion).
      * Ensuring ``table*`` fits the document layout (single-column class:
        ``table*`` falls back to ``table``; 2-column class: spans both
        columns, which is typically desired for wide tables).
    """
    count = 0
    # Walk the text with brace-matched header parser (calc-width safe).
    # Each iteration: find next \begin{longtable}, capture cols to the
    # matched close-brace of the header, then scan forward for the next
    # \end{longtable}. Nested longtables are not supported (neither is
    # pandoc), so linear scan is sound.
    pieces: list[str] = []
    cursor = 0
    headers = list(_iter_longtable_headers(text))
    if not headers:
        return text, 0
    for start, header_end, pre, cols_str in headers:
        end_match = _LONGTABLE_END_RE.search(text, header_end)
        if end_match is None:
            # No matching \end{longtable} — bail out on this one.
            continue
        body = text[header_end:end_match.start()]
        block_end = end_match.end()

        cols = cols_str  # already normalised by _fix_longtable_columns
        body = re.sub(r"\\endfirsthead\b", "", body)
        body = re.sub(r"\\endhead\b", "", body)
        body = re.sub(r"\\endfoot\b", "", body)
        body = re.sub(r"\\endlastfoot\b", "", body)
        body = re.sub(r"\\noalign\{\}", "", body)
        # Pandoc's longtable template emits ``\bottomrule`` inside the
        # page-break-footer block (between ``\endhead`` and
        # ``\endlastfoot``), which after stripping ends up ORPHANED
        # between ``\midrule`` and the data rows — producing a spurious
        # horizontal line mid-table and NO line at the actual bottom.
        # Strip every ``\bottomrule`` from the body and re-append a
        # single one just before ``\end{tabular}``.
        body = re.sub(r"\\bottomrule\s*\n?", "", body)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        replacement = (
            "\\begin{table*}\n"
            "\\centering\n"
            "\\small\n"
            f"\\begin{{tabular}}{{{cols}}}\n"
            f"{body}\n"
            "\\bottomrule\n"
            "\\end{tabular}\n"
            "\\end{table*}"
        )
        pieces.append(text[cursor:start])
        pieces.append(replacement)
        cursor = block_end
        count += 1
    pieces.append(text[cursor:])
    return "".join(pieces), count


# Round 4.5 — lstset preamble snippet to keep pandoc's ``lstlisting`` blocks
# inside a column in 2-col layouts. Without these, the default
# ``basicstyle`` (``\normalsize\ttfamily``) + no line-breaking makes any
# code line wider than ~50 chars spill across the gutter. We scale down
# to ``\footnotesize`` and enable soft line-breaks that break at word
# boundaries and indent the continuation with ``breakindent``.
_LSTSET_SNIPPET = r"""% ─── latex-korean-setup: lstlisting 2-column safety (Round 4.5) ──
% Defensive lstset so ``lstlisting`` blocks coming from pandoc-converted
% fenced code fit inside a single 2-column class column. Authors can
% override any of these by adding a local \lstset{...} AFTER
% \usepackage{korean-patch} in their preamble.
\lstset{
  basicstyle=\footnotesize\ttfamily,
  breaklines=true,
  breakatwhitespace=true,
  breakindent=0pt,
  columns=fullflexible,
  keepspaces=true,
  xleftmargin=0pt,
  xrightmargin=0pt,
  showstringspaces=false,
  upquote=true,
}"""


_QUOTE_ENV_RE = re.compile(
    r"\\begin\{quote\}\s*\n?(?P<body>.*?)\\end\{quote\}\s*",
    re.DOTALL,
)


def _unwrap_blockquotes(text: str) -> tuple[str, int]:
    r"""Replace ``\begin{quote}...\end{quote}`` with its body. Round 4.5:
    Markdown ``> ...`` callouts compiled by pandoc render as an indented
    quote environment whose left padding + italic-guided styling is at
    odds with 2-column ACM / IEEE layouts (visible as single-line overflow
    and awkward corner spacing). Stripping the wrapper yields a plain
    paragraph, which the user explicitly requested ("callout 제거하고
    source만 옮기도록").

    The body is not altered further — inline ``\textbf`` / ``\emph`` /
    math stay intact; only the environment frame goes away. Trailing
    blank line is collapsed to avoid creating a double blank-line.
    """
    count = 0

    def _sub(match: re.Match) -> str:
        nonlocal count
        count += 1
        body = match.group("body").strip()
        return body + "\n\n"

    out = _QUOTE_ENV_RE.sub(_sub, text)
    return out, count


# Display-math auto-shrink: pandoc emits inline-style ``\[...\]`` for
# fenced math (``$$...$$``) and for Markdown's ``display math``. In a
# 2-column layout, long single-line formulae overflow the column
# because ``\[...\]`` does not break. Wrapping in
# ``\adjustbox{max width=\columnwidth}`` shrinks the formula ONLY when
# it exceeds the column; shorter math renders at normal size. Round 4.6
# (user-reported: FSPM-Score_A formula in §3.3 spilled past the gutter).
_DISPLAY_MATH_RE = re.compile(r"\\\[(?P<body>.*?)\\\]", re.DOTALL)

# Minimum body length (characters, trimmed) above which we wrap. The
# value is tuned so the 110-char ``\text{FSPM-Score}_B = w_1 \cdot …``
# stays as-is (it fits the column), while the 230-char ``FSPM-Score_A``
# formula gets shrunk. Authors can override via
# ``PostprocessConfig.display_math_shrink_threshold``.
_DISPLAY_MATH_DEFAULT_THRESHOLD = 120


# Bold strip: match \textbf{...} whose braces are balanced. Pure regex
# can't match balanced braces, so we find \textbf{ openings and walk
# braces with _find_matching_brace (reused from longtable cols).
_TEXTBF_OPEN_RE = re.compile(r"\\textbf\{")


def _strip_prose_bold(text: str, max_len: int) -> tuple[str, int]:
    r"""Strip ``\textbf{X}`` → ``X`` when X looks like prose emphasis
    rather than a named label. Heuristic:

      * Content length (Unicode code-points, trimmed) > ``max_len``, OR
      * Content contains sentence punctuation ``.,:;!?``, OR
      * Content contains spaces AND ends with a Korean syllable (Hangul
        Syllables block U+AC00–U+D7A3) — Korean prose habit.

    Short Latin / Korean labels (``IV``, ``α 보존``, ``N개 모델``) are
    kept. Nested ``\textbf`` (rare) is handled by walking braces rather
    than regex-matching `[^}]*`.
    """
    sentence_re = re.compile(r"[.,:;!?]")
    hangul_syllable_re = re.compile(r"[가-힣]")

    out_parts: list[str] = []
    cursor = 0
    count = 0
    for m in _TEXTBF_OPEN_RE.finditer(text):
        open_idx = m.end() - 1  # index of the ``{``
        close_idx = _find_matching_brace(text, open_idx)
        if close_idx < 0:
            continue  # unbalanced — leave as-is
        inner = text[open_idx + 1 : close_idx - 1]
        trimmed = inner.strip()
        is_prose = (
            len(trimmed) > max_len
            or bool(sentence_re.search(trimmed))
            or (" " in trimmed and bool(hangul_syllable_re.search(trimmed[-3:])))
        )
        if not is_prose:
            continue  # keep \textbf intact
        out_parts.append(text[cursor : m.start()])
        out_parts.append(inner)  # strip wrapper
        cursor = close_idx
        count += 1
    if count == 0:
        return text, 0
    out_parts.append(text[cursor:])
    return "".join(out_parts), count


# Caption detection: a ``\emph{...}`` paragraph matching "(Figure|Table|
# 표|그림)\s*N" immediately after a table*/figure*/fbox float block.
_TRAILING_CAPTION_RE = re.compile(
    r"(?P<float>\\end\{(?:table\*|table|figure\*|figure)\}"
    r"|\\end\{minipage\}\}\s*\n?\\end\{center\})"
    r"\s*\n+"
    r"\\emph\{(?P<prefix>(?:Figure|Table|표|그림)\s*\d+[:.]?)\s*(?P<body>[^}]*?)\}"
)


def _attach_trailing_captions(text: str) -> tuple[str, int]:
    r"""If a float-like block is followed by ``\emph{Figure N: ...}`` /
    ``\emph{Table N: ...}`` / ``\emph{표 N: ...}`` / ``\emph{그림 N:
    ...}``, move the text inside the float as ``\caption{prefix body}``.

    Only applies to table*/figure*/table/figure floats — the
    ``\fbox{\begin{minipage}...}`` diagram placeholder isn't a float so
    ``\caption`` there would crash LaTeX.

    Returns the (possibly unchanged) text and the count of captions
    attached.
    """
    count = 0

    def _sub(match: re.Match) -> str:
        nonlocal count
        float_end = match.group("float")
        prefix = match.group("prefix").rstrip(":. ")
        body = match.group("body").strip()
        caption_text = f"{prefix}: {body}" if body else prefix
        # Only table/table*/figure/figure* support \caption inside the
        # environment; skip if the captured tail is the minipage case.
        if not float_end.startswith("\\end{table") and not float_end.startswith(
            "\\end{figure"
        ):
            return match.group(0)
        # Insert \caption just BEFORE \end{table*} / \end{figure*}.
        count += 1
        env_name = float_end[len("\\end{") : -1]
        caption_stmt = f"\\caption{{{caption_text}}}\n{float_end}"
        # Walk back from float_end start to find the \begin{env_name} and
        # replace the whole span float-body to include \caption.
        return caption_stmt

    # Replace in-place. We assume \caption placement at the env tail is
    # acceptable for both table and figure styles; ACM sigconf puts table
    # captions at top by convention but \caption works at any position.
    # Authors can re-order by hand if their class forbids bottom captions.
    out = _TRAILING_CAPTION_RE.sub(_sub, text)
    return out, count


def _shrink_wide_display_math(text: str, threshold: int) -> tuple[str, int]:
    r"""Wrap long ``\[...\]`` display math in
    ``\begin{center}\adjustbox{max width=\columnwidth}{$\displaystyle
    ...$}\end{center}`` so the formula shrinks to fit a 2-column layout.

    ``max width`` (not ``scale``) means short math is left at natural
    size; only bodies over ``threshold`` characters get modified.
    Threshold is applied to the trimmed body length, excluding the
    ``\[`` / ``\]`` delimiters.

    ``\adjustbox`` comes from the ``adjustbox`` package (standard in
    recent TeX Live distributions; the caller adds it to
    ``required_packages``).
    """
    count = 0

    def _sub(match: re.Match) -> str:
        nonlocal count
        body = match.group("body").strip()
        if len(body) <= threshold:
            return match.group(0)  # short — leave as-is
        count += 1
        # ``\displaystyle`` keeps operator rendering (big sum/int/frac)
        # identical to the \[...\] form; without it the body would
        # degrade to ``\textstyle`` sizes inside the \adjustbox.
        return (
            "\\begin{center}\n"
            "\\adjustbox{max width=\\columnwidth}{$\\displaystyle "
            + body
            + "$}\n"
            "\\end{center}"
        )

    out = _DISPLAY_MATH_RE.sub(_sub, text)
    return out, count


def _apply_image_rewrites(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    for old, new in mapping.items():
        text = text.replace(f"\\includegraphics{{{old}}}", f"\\includegraphics{{{new}}}")
        text = re.sub(
            r"\\includegraphics\[([^\]]*)\]\{" + re.escape(old) + r"\}",
            lambda m, n=new: rf"\includegraphics[{m.group(1)}]{{{n}}}",
            text,
        )
    return text


def _strip_newcommands(text: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    collected: list[str] = []

    def _sub(match: re.Match) -> str:
        name = match.group(1)
        collected.append(name)
        return ""

    out = _NEWCMD_RE.sub(_sub, text)
    if collected:
        warnings.append(
            "stripped \\newcommand definitions from fragment: "
            + ", ".join(sorted(set(collected)))
            + " — move to preamble (e.g. math_commands.tex) manually"
        )
    return out, warnings


def detect_required_packages(text: str) -> list[str]:
    """Scan a fragment and return the list of LaTeX packages that must be
    \\usepackage'd for it to compile.

    De-duplicated; order is deterministic (first match wins).
    """
    found: list[str] = []
    for pat, pkg in _PACKAGE_TRIGGERS:
        if pkg in found:
            continue
        if pat.search(text):
            found.append(pkg)
    return found


def postprocess(raw_tex: str, cfg: PostprocessConfig) -> PostprocessResult:
    """Run all postprocess steps and return a :class:`PostprocessResult`.

    Back-compat shim: older callers unpacking ``(text, warnings)`` should
    migrate to ``result.text`` / ``result.warnings`` / ``result.required_packages``.
    """
    warnings: list[str] = []
    out = raw_tex

    # 1. \hypertarget
    out = _HYPERTARGET_RE.sub(r"\g<body>\\label{\g<id>}", out)

    # 2. \passthrough{\lstinline!X!}
    out = _PASSTHROUGH_RE.sub(
        lambda m: rf"\texttt{{\detokenize{{{m.group(1)}}}}}", out
    )

    # 3. Shaded/Highlighting blocks
    def _shaded_sub(match: re.Match) -> str:
        body = match.group(1)
        body = re.sub(r"\\[A-Z][A-Za-z]+Tok\{([^{}]*)\}", r"\1", body)
        return "\\begin{lstlisting}\n" + body.strip() + "\n\\end{lstlisting}"

    out = _SHADED_RE.sub(_shaded_sub, out)

    # 4. longtable column normalization + strip \LTcaptype{none} wrapper
    out, n_tbl = _fix_longtable_columns(out)
    if n_tbl:
        warnings.append(f"normalized {n_tbl} longtable column spec(s)")
    stripped = _LTCAPTYPE_OPEN_RE.sub("", out)
    if stripped != out:
        stripped = re.sub(
            r"(\\end\{longtable\}\s*\n)\}\s*\n",
            r"\1",
            stripped,
        )
        out = stripped
        warnings.append("stripped pandoc \\LTcaptype{none} wrapper")

    # 5. Convert longtable -> table*+tabular for 2-column compatibility.
    n_lt_to_tbl = 0
    if cfg.table_mode in {"auto", "table-star"}:
        out, n_lt_to_tbl = _longtable_to_tabular(out)
        if n_lt_to_tbl:
            warnings.append(
                f"converted {n_lt_to_tbl} longtable → table*+tabular "
                "(F-longtable-1 2-column compat; set table_mode='longtable' "
                "to keep original)"
            )

    # 5b. Wrap bare ``_\op`` / ``^\op`` math operators in braces. Runs
    # after table-conversion (step 5) because operator-bearing math
    # commonly sits inside table cells that have already been flattened
    # and must be scanned as plain tex.
    n_wrapped = [0]

    def _wrap_op(match: re.Match) -> str:
        n_wrapped[0] += 1
        return f"{match.group('pos')}{{\\{match.group('op')}}}"

    out = _BARE_MATH_OP_RE.sub(_wrap_op, out)
    if n_wrapped[0]:
        warnings.append(
            f"wrapped {n_wrapped[0]} bare ``_\\op`` / ``^\\op`` math-"
            "operator subscript(s) in braces (xelatex requires "
            "``_{\\op}`` for \\DeclareMathOperator* macros)"
        )

    # 6. Horizontal-rule output cleanup
    hr_out = _HR_OUTPUT_RE.sub("", out)
    if hr_out != out:
        warnings.append(
            "stripped \\begin{center}\\rule{...}\\end{center} horizontal "
            "rule output (F5)"
        )
        out = hr_out

    # 6b. Strip MD-authored numeric prefix from section titles so LaTeX's
    # \thesection counter doesn't double-print ("1 1. 서론" → "1 서론").
    if cfg.strip_section_number_prefix:
        n_stripped = [0]

        def _strip_num(match: re.Match) -> str:
            n_stripped[0] += 1
            return match.group(1) + match.group("rest").lstrip()

        out = _SECTION_NUM_RE.sub(_strip_num, out)
        if n_stripped[0]:
            warnings.append(
                f"stripped MD-authored numeric prefix from {n_stripped[0]} "
                "section title(s) to avoid double-numbering; set "
                "strip_section_number_prefix=False to preserve"
            )

    # 6c. Unwrap blockquote "callouts" per user Round 4.5 request.
    if cfg.unwrap_blockquotes:
        out, n_unwrapped = _unwrap_blockquotes(out)
        if n_unwrapped:
            warnings.append(
                f"unwrapped {n_unwrapped} ``\\begin{{quote}}`` blockquote(s) "
                "(callout frame stripped; source preserved)"
            )

    # 6d. Strip prose-emphasis ``\textbf{...}``.
    if cfg.strip_prose_bold:
        out, n_bold = _strip_prose_bold(out, max_len=cfg.prose_bold_max_len)
        if n_bold:
            warnings.append(
                f"stripped {n_bold} ``\\textbf{{...}}`` wrapping prose "
                f"(>{cfg.prose_bold_max_len} chars OR sentence punctuation); "
                "short labels preserved. Disable via strip_prose_bold=False."
            )

    # 6e. Attach trailing italic caption lines to table*/figure* floats.
    if cfg.attach_trailing_captions:
        out, n_cap = _attach_trailing_captions(out)
        if n_cap:
            warnings.append(
                f"attached {n_cap} trailing ``\\emph{{(Figure|Table|표|"
                "그림) N: ...}}`` caption(s) into enclosing float"
            )

    # 6f. Shrink wide display math so it fits the column. Round 4.6.
    if cfg.shrink_wide_display_math:
        out, n_shrunk = _shrink_wide_display_math(
            out, threshold=cfg.display_math_shrink_threshold
        )
        if n_shrunk:
            warnings.append(
                f"wrapped {n_shrunk} ``\\[...\\]`` display-math block(s) "
                f"longer than {cfg.display_math_shrink_threshold} chars in "
                "``\\adjustbox{max width=\\columnwidth}`` so they fit the "
                "2-column layout"
            )

    # 7. Image path rewrites
    out = _apply_image_rewrites(out, cfg.image_path_rewrites)

    # 8. Drop stray document envs
    out = _DOCENV_RE.sub("", out)

    # 9. Strip \newcommand/\renewcommand
    out, w = _strip_newcommands(out)
    warnings.extend(w)

    # Trim excess blank lines
    out = re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"

    # 10. Required-package detection (over the FINAL fragment so we catch
    #     substitutions we ourselves introduced in step 3/5)
    required = detect_required_packages(out)

    # 10b. Preamble snippet emission: emit the lstset defensive config
    # when the fragment actually uses lstlisting. This keeps preamble
    # bloat zero-cost for code-free fragments.
    preamble_snippets: list[str] = []
    if "\\begin{lstlisting}" in out:
        preamble_snippets.append(_LSTSET_SNIPPET)

    # 11. Sentinels
    if cfg.include_sentinels:
        hash_short = (cfg.source_sha1 or "")[:12]
        header = (
            f"% ─── BEGIN auto-injected from {cfg.source_relpath} "
            f"(sha1={hash_short}) ───\n"
        )
        footer = f"\n% ─── END auto-injected from {cfg.source_relpath} ───\n"
        out = header + out + footer

    return PostprocessResult(
        text=out,
        warnings=warnings,
        required_packages=required,
        preamble_snippets=preamble_snippets,
        n_longtable_converted=n_lt_to_tbl,
    )


def sha1_short(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

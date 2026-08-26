r"""Template-preset mappings for custom LaTeX templates.

The default conversion pipeline emits stock LaTeX (`\begin{quote}`,
`lstlisting`, `\textbf{}`) which works in any class. When the target
project uses a richer template (e.g. `gist-preprint.sty` with
`researchquestion` / `highlightbox` / `algorithm` environments), the
author can opt in to a **preset** that makes the skill emit the richer
constructs instead.

Detection modes:
  1. Explicit: `PostprocessConfig.template_preset = "gist-preprint"`.
  2. Auto: `detect_preset(main_tex_path)` scans the main.tex preamble
     for `\usepackage{gist-preprint}` — if present, the preset is
     enabled automatically.

Each preset is a pair of transforms:
  * A preprocess transform (MD-level), applied BEFORE pandoc.
  * A postprocess transform (tex-level), applied AFTER pandoc.

This module only ships the preprocess side for the ``gist-preprint``
preset so far:
  * ``algorithm`` fenced code blocks → ``\begin{algorithm}[t]
    \begin{algorithmic}[1]...\end{algorithmic}\end{algorithm}``.

Other mappings (highlightbox, researchquestion, \val{}, \tokenred{})
are documented in ``references/template-items.md`` and can be added
here without touching the orchestrator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "PresetName",
    "detect_preset",
    "apply_preset_preprocess",
]


PresetName = str  # "gist-preprint" | "none" | ...


_PRESET_MARKERS: dict[PresetName, re.Pattern] = {
    "gist-preprint": re.compile(r"^\s*\\usepackage\{gist-preprint\}", re.MULTILINE),
}


def detect_preset(main_tex_path: Path | str | None) -> PresetName:
    """Read ``main.tex`` and return a known preset name if one of the
    distinctive ``\\usepackage`` lines is present; otherwise ``"none"``.

    Silent on I/O errors — downstream code should treat ``"none"`` as
    "run the default pipeline".
    """
    if not main_tex_path:
        return "none"
    try:
        text = Path(main_tex_path).read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return "none"
    for name, pat in _PRESET_MARKERS.items():
        if pat.search(text):
            return name
    return "none"


# ── gist-preprint: algorithm fenced block ─────────────────────────

_ALGO_FENCE_RE = re.compile(
    r"^```algorithm\s*\n(?P<body>.*?)\n```\s*$",
    re.DOTALL | re.MULTILINE,
)

# Minimal pseudocode grammar — handles Require/Ensure, For/EndFor,
# If/Else/EndIf, While/EndWhile, Return, plus `caption:` / `label:`
# metadata lines. Anything else becomes `\State <line>`.
_CAPTION_RE = re.compile(r"^\s*caption\s*:\s*(?P<text>.+)$", re.IGNORECASE)
_LABEL_RE = re.compile(r"^\s*label\s*:\s*(?P<id>\S+)\s*$", re.IGNORECASE)


def _render_algorithmic(body: str) -> str:
    """Render pseudocode body lines into an ``algorithmic`` block.

    Recognised keywords (case-insensitive, leading whitespace ignored):
      * ``Require:`` / ``Input:`` → ``\\Require``
      * ``Ensure:`` / ``Output:`` → ``\\Ensure``
      * ``For ... do`` / ``For ...`` → ``\\For{...}``   (paired with
        ``End For`` / ``EndFor`` → ``\\EndFor``)
      * ``While ... do`` → ``\\While{...}`` … ``\\EndWhile``
      * ``If ... then`` → ``\\If{...}`` … ``\\ElsIf{...}`` / ``\\Else``
        … ``\\EndIf``
      * ``Return X`` → ``\\State \\Return X``
      * other lines → ``\\State <line>``
    """
    out: list[str] = []
    for raw in body.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        lower = s.lower()
        if lower.startswith(("require:", "input:")):
            arg = s.split(":", 1)[1].strip()
            out.append(f"    \\Require {arg}")
        elif lower.startswith(("ensure:", "output:")):
            arg = s.split(":", 1)[1].strip()
            out.append(f"    \\Ensure {arg}")
        elif lower.startswith("for ") and lower.endswith(" do"):
            arg = s[4:-3].strip()
            out.append(f"    \\For{{{arg}}}")
        elif lower.startswith("for "):
            arg = s[4:].strip()
            out.append(f"    \\For{{{arg}}}")
        elif lower in {"end for", "endfor"}:
            out.append("    \\EndFor")
        elif lower.startswith("while ") and lower.endswith(" do"):
            arg = s[6:-3].strip()
            out.append(f"    \\While{{{arg}}}")
        elif lower.startswith("while "):
            arg = s[6:].strip()
            out.append(f"    \\While{{{arg}}}")
        elif lower in {"end while", "endwhile"}:
            out.append("    \\EndWhile")
        elif lower.startswith("if ") and lower.endswith(" then"):
            arg = s[3:-5].strip()
            out.append(f"    \\If{{{arg}}}")
        elif lower.startswith("if "):
            arg = s[3:].strip()
            out.append(f"    \\If{{{arg}}}")
        elif lower.startswith("elsif ") or lower.startswith("elseif "):
            tok = "elsif" if lower.startswith("elsif ") else "elseif"
            arg = s[len(tok) + 1 :].strip()
            out.append(f"    \\ElsIf{{{arg}}}")
        elif lower == "else":
            out.append("    \\Else")
        elif lower in {"end if", "endif"}:
            out.append("    \\EndIf")
        elif lower.startswith("return "):
            arg = s[7:].strip()
            out.append(f"    \\State \\Return {arg}")
        elif lower == "return":
            out.append("    \\State \\Return")
        else:
            out.append(f"    \\State {s}")
    return "\n".join(out)


def _convert_algorithm_fence(md_text: str) -> tuple[str, int]:
    """Replace every ` ```algorithm ... ``` ` fenced block with a full
    ``algorithm`` + ``algorithmic`` environment.

    The first line matching ``caption: X`` becomes ``\\caption{X}``; the
    first line matching ``label: Y`` becomes ``\\label{Y}``. Both are
    removed from the pseudocode body before rendering.
    """
    count = 0

    def _sub(match: re.Match) -> str:
        nonlocal count
        body = match.group("body")

        caption: str | None = None
        label: str | None = None
        kept: list[str] = []
        for line in body.splitlines():
            mc = _CAPTION_RE.match(line)
            ml = _LABEL_RE.match(line)
            if mc and caption is None:
                caption = mc.group("text").strip()
            elif ml and label is None:
                label = ml.group("id").strip()
            else:
                kept.append(line)
        body_kept = "\n".join(kept)
        code = _render_algorithmic(body_kept)

        count += 1
        parts = ["\\begin{algorithm}[t]"]
        if caption:
            parts.append(f"  \\caption{{{caption}}}")
        if label:
            parts.append(f"  \\label{{{label}}}")
        parts.append("  \\begin{algorithmic}[1]")
        parts.append(code)
        parts.append("  \\end{algorithmic}")
        parts.append("\\end{algorithm}")
        return "\n".join(parts)

    out = _ALGO_FENCE_RE.sub(_sub, md_text)
    return out, count


@dataclass
class PresetPreprocessResult:
    text: str
    warnings: list[str]
    required_packages: list[str]


def apply_preset_preprocess(md_text: str, preset: PresetName) -> PresetPreprocessResult:
    """Apply the preset's MD-level transformations. For ``"none"`` this
    is a no-op.

    Returns updated text, warnings, and any LaTeX packages the
    transformations require (so the caller can add them to
    ``required_packages``).
    """
    warnings: list[str] = []
    required: list[str] = []
    out = md_text

    if preset == "gist-preprint":
        out, n_algo = _convert_algorithm_fence(out)
        if n_algo:
            warnings.append(
                f"converted {n_algo} ``` ```algorithm ``` `` fenced block(s) "
                "to ``\\begin{algorithm}\\begin{algorithmic}...`` "
                "(gist-preprint preset)"
            )
            required.extend(["algorithm", "algpseudocode"])

    return PresetPreprocessResult(text=out, warnings=warnings, required_packages=required)

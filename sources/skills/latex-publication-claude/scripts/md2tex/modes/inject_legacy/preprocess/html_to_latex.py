r"""Convert inline HTML tags common in Squid-Game-style Korean MD to LaTeX.

Handles:
  <font color="#HHHHHH">X</font> -> \textcolor{<gist-name>}{X} or \textcolor[HTML]{HHHHHH}{X}
  <sub>X</sub>                    -> \textsubscript{X}
  <sup>X</sup>                    -> \textsuperscript{X}
  <u>X</u>                         -> \underline{X}
  <br>, <br/>                      -> \\ (line break inside paragraphs)

Pure-functional. No filesystem I/O. Palette map is passed in as a dict, so
the caller can override per-project without module state.
"""

from __future__ import annotations

import re
from typing import Iterable

__all__ = ["convert", "normalize_color"]


_FONT_RE = re.compile(
    r"<font\s+color\s*=\s*\"([^\"]+)\"\s*>(.*?)</font>",
    re.DOTALL | re.IGNORECASE,
)
_SUB_RE = re.compile(r"<sub>(.*?)</sub>", re.DOTALL | re.IGNORECASE)
_SUP_RE = re.compile(r"<sup>(.*?)</sup>", re.DOTALL | re.IGNORECASE)
_U_RE = re.compile(r"<u>(.*?)</u>", re.DOTALL | re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def normalize_color(raw: str) -> str:
    """Normalize a color spec to uppercase hex WITHOUT the leading '#'."""
    s = raw.strip().lstrip("#").upper()
    # Accept short-form like F00 → FF0000
    if re.fullmatch(r"[0-9A-F]{3}", s):
        s = "".join(ch * 2 for ch in s)
    return s


def _inline_safe_escape(text: str) -> str:
    r"""Minimal LaTeX escape for captured body text.

    Runs BEFORE pandoc sees the content. We only escape chars that would
    prematurely terminate the \textcolor{...} argument: braces.
    Other special chars stay as-is so pandoc handles them.
    """
    return text.replace("\\", "\\\\").replace("{", r"\{").replace("}", r"\}")


def convert(
    text: str,
    palette: dict[str, str] | None = None,
    *,
    escape_body: bool = False,
) -> tuple[str, list[str]]:
    """Convert inline HTML tags to LaTeX.

    Args:
      text: Markdown source.
      palette: maps uppercase hex (no '#') → gist palette name, e.g.
               {"0000FF": "gistblue", "CC1100": "gistred"}.
               If None, all colors fall back to \textcolor[HTML]{...}.
      escape_body: if True, escapes { and } inside captured body text.
                    Default False because pandoc handles most chars; escaping
                    can break inline markup like `**bold**`.

    Returns:
      (new_text, warnings)
    """
    palette = palette or {}
    warnings: list[str] = []
    unmapped: set[str] = set()

    def _font_sub(match: re.Match) -> str:
        raw_color, body = match.group(1), match.group(2)
        hex_code = normalize_color(raw_color)
        if not re.fullmatch(r"[0-9A-F]{6}", hex_code):
            warnings.append(f"unknown color spec '{raw_color}' kept as raw")
            return match.group(0)
        gist_name = palette.get(hex_code)
        payload = _inline_safe_escape(body) if escape_body else body
        if gist_name:
            return rf"\textcolor{{{gist_name}}}{{{payload}}}"
        unmapped.add(hex_code)
        return rf"\textcolor[HTML]{{{hex_code}}}{{{payload}}}"

    out = _FONT_RE.sub(_font_sub, text)
    if unmapped:
        warnings.append(
            "unmapped <font color=#HEX>: "
            + ", ".join(sorted(unmapped))
            + " (add to color-palette-map.yaml to route to gist palette)"
        )

    out = _SUB_RE.sub(lambda m: rf"\textsubscript{{{m.group(1)}}}", out)
    out = _SUP_RE.sub(lambda m: rf"\textsuperscript{{{m.group(1)}}}", out)
    out = _U_RE.sub(lambda m: rf"\underline{{{m.group(1)}}}", out)
    out = _BR_RE.sub(r"\\\\", out)

    return out, warnings


def load_palette_from_yaml(path: str) -> dict[str, str]:
    """Load a palette YAML and return {HEX: name} with normalized keys.

    Tolerates the missing PyYAML case by implementing a minimal flat parser
    for `HEX: name` lines only (our palette file format).
    """
    try:
        import yaml  # type: ignore

        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except ImportError:
        raw = _load_flat_yaml(path)

    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        out[normalize_color(k)] = v.strip()
    return out


def _load_flat_yaml(path: str) -> dict[str, str]:
    """Trivial flat k: v parser used when PyYAML isn't available."""
    out: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            s = line.split("#", 1)[0].strip()
            if not s or ":" not in s:
                continue
            k, v = s.split(":", 1)
            out[k.strip().strip('"').strip("'")] = v.strip().strip('"').strip("'")
    return out


def iter_font_hexes(text: str) -> Iterable[str]:
    """Yield normalized HEX codes appearing in <font color="..."> tags.

    Useful for pre-scanning a corpus to build a palette candidate list.
    """
    for m in _FONT_RE.finditer(text):
        hex_code = normalize_color(m.group(1))
        if re.fullmatch(r"[0-9A-F]{6}", hex_code):
            yield hex_code

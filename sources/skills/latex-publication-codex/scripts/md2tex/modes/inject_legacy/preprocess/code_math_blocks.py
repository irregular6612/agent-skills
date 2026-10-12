r"""Convert GitHub/Obsidian ```math fenced blocks into $$...$$ display math.

Some authors write:
    ```math
    \int_0^\infty e^{-x^2} dx = \tfrac{\sqrt{\pi}}{2}
    ```
instead of the LaTeX-native $$...$$ form. Pandoc's `tex_math_dollars`
extension only understands the dollar-delimiter form, so we normalize.

This is deliberately narrow: we do NOT touch ``` (no language),
```latex, ```python etc. We only rewrite blocks whose info-string is
exactly `math`.
"""

from __future__ import annotations

import re

__all__ = ["convert"]


_MATH_FENCE_RE = re.compile(
    r"```math[^\n]*\n(.*?)\n```",
    re.DOTALL,
)


def convert(text: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    count = 0

    def _sub(match: re.Match) -> str:
        nonlocal count
        count += 1
        body = match.group(1).rstrip()
        return f"$$\n{body}\n$$"

    out = _MATH_FENCE_RE.sub(_sub, text)
    if count:
        warnings.append(f"converted {count} ```math fenced block(s) to $$...$$")
    return out, warnings

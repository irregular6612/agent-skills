#!/usr/bin/env python3
"""build.py — MD → 독립 PDF용 .tex 변환 (build mode).

구 academic-latex-pipeline/scripts/build_template.py를 wrapping.
명세서 R1 위험 회피: rule 자체는 변경하지 않고 entry point만 통일.

사용법:
    build.py <input.tex> <output.tex> [refs.bib]

입력 .tex는 일반적으로 pandoc 변환 결과. 이 스크립트가:
- Obsidian artifact strip (wikilinks, tags, frontmatter)
- XeLaTeX preamble 주입 (한글 폰트)
- Mermaid → TikZ placeholder
- Examples → tcolorbox 래핑
- Citation 매칭 (refs.bib 있을 때)
- Wide table 포맷 수정

전체 MD → PDF 빌드 워크플로:
    1. pandoc input.md -f markdown -t latex -o raw.tex
    2. build.py raw.tex final.tex refs.bib    ← 이 스크립트
    3. compile.sh final.tex                    ← 별도 스크립트
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    # legacy 모듈을 직접 호출
    here = Path(__file__).resolve().parent
    legacy = here / 'build_legacy.py'

    if not legacy.is_file():
        print(f"ERROR: build_legacy.py 없음: {legacy}", file=sys.stderr)
        return 3

    # build_legacy.py가 표준 CLI를 노출하므로 그대로 위임
    # sys.argv[0]만 build.py로 치환해서 도움말 메시지 깔끔하게
    import runpy
    sys.argv = [str(legacy), *sys.argv[1:]]
    runpy.run_path(str(legacy), run_name='__main__')
    return 0


if __name__ == '__main__':
    sys.exit(main())

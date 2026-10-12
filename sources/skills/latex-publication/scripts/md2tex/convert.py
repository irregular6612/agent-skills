#!/usr/bin/env python3
"""convert.py — md2tex 통합 entry point.

명세서 5.2 원칙: rule 자체는 통합하지 않고 entry point만 통합.
modes/build.py와 modes/inject.py가 각각 legacy 로직을 wrapping.

사용법:
    convert.py --mode=build <input.md> <output_dir> [--bib refs.bib]
    convert.py --mode=inject <project_dir> [inject 옵션들]

라우팅:
    --mode=build  → modes/build.py (구 academic-latex-pipeline 로직)
    --mode=inject → modes/inject.py (구 latex-korean-setup md_inject 로직)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="md2tex 통합 entry point. mode별 분기."
    )
    parser.add_argument(
        '--mode',
        choices=['build', 'inject'],
        required=True,
        help="build: MD → 독립 PDF용 .tex / inject: MD → 기존 .tex 템플릿에 주입",
    )
    args, rest = parser.parse_known_args()

    here = Path(__file__).resolve().parent
    if args.mode == 'build':
        target = here / 'modes' / 'build.py'
    elif args.mode == 'inject':
        target = here / 'modes' / 'inject.py'
    else:
        print(f"ERROR: 알 수 없는 mode: {args.mode}", file=sys.stderr)
        return 3

    if not target.is_file():
        print(f"ERROR: mode wrapper 없음: {target}", file=sys.stderr)
        return 3

    # 서브프로세스 대신 직접 exec (인자 그대로 전달)
    os.execvp(sys.executable, [sys.executable, str(target), *rest])


if __name__ == '__main__':
    sys.exit(main())

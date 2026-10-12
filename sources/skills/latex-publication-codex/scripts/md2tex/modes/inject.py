#!/usr/bin/env python3
"""inject.py — MD → 기존 TeX 템플릿에 sentinel marker 주입 (inject mode).

구 latex-korean-setup/scripts/md_inject/md_inject.sh를 wrapping.
명세서 R1 위험 회피: rule 자체는 변경하지 않고 entry point만 통일.

사용법:
    inject.py <project_dir> [--target main.tex] [--md-root docs] [--workers N]
              [--manifest md-inject.yaml] [--no-auto-cite] [--dry-run]
              [--no-verify] [--force]

워크플로 (4단계, Phase 8 LLM 감사는 별도 skill 호출 시 추가):
    Phase 6  plan        — InjectionPlan JSON 생성
    Phase 7  convert     — pandoc 병렬 변환
    Phase 9  apply       — atomic main.tex 갱신
    Phase 10 verify      — verify_build.sh 호출
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    here = Path(__file__).resolve().parent  # modes/
    legacy_sh = here / 'inject_legacy' / 'md_inject.sh'

    if not legacy_sh.is_file():
        print(f"ERROR: inject_legacy/md_inject.sh 없음: {legacy_sh}", file=sys.stderr)
        return 3

    # bash로 위임
    cmd = ['bash', str(legacy_sh), *sys.argv[1:]]
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError:
        print("ERROR: bash 미설치", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\n[inject] 사용자 중단", file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())

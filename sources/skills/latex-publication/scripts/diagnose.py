#!/usr/bin/env python3
"""
diagnose.py — Phase 1 diagnostic for latex-publication skill.

Scans a LaTeX project directory and reports what is needed to enable
Korean rendering with Overleaf round-trip compatibility.

Usage:
    python diagnose.py [project_dir]

If project_dir is omitted, the current directory is used.

Read-only: makes no changes to the filesystem.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# ─── Marker patterns ────────────────────────────────────────────
# Note: LaTeX commands are case-sensitive.
#   \usepackage{...}       — used in document preamble (lowercase)
#   \RequirePackage{...}   — used inside .sty files (CamelCase)
PKG_CMD = r"\\(?:RequirePackage|usepackage)"

KOREAN_PACKAGE_PATTERNS = [
    (PKG_CMD + r"(?:\[[^\]]*\])?\{kotex\}", "kotex"),
    (PKG_CMD + r"(?:\[[^\]]*\])?\{xeCJK\}", "xeCJK"),
    (PKG_CMD + r"(?:\[[^\]]*\])?\{ucharclasses\}", "ucharclasses"),
    (PKG_CMD + r"(?:\[[^\]]*\])?\{CJKutf8\}", "CJKutf8"),
    # skill's own wrapper packages — recognized so Part 1 patch-applied
    # projects don't false-negative on re-diagnose.
    (PKG_CMD + r"(?:\[[^\]]*\])?\{korean-patch\}", "korean-patch"),
    (PKG_CMD + r"(?:\[[^\]]*\])?\{korean-patch-xecjk\}", "korean-patch-xecjk"),
]

FONTSPEC_PATTERN = PKG_CMD + r"(?:\[[^\]]*\])?\{fontspec\}"

PDFLATEX_ONLY_MARKERS = [
    (PKG_CMD + r"\[utf8\]\{inputenc\}", "inputenc"),
    (PKG_CMD + r"\[T1\]\{fontenc\}", "fontenc[T1]"),
    (PKG_CMD + r"\{tgpagella\}", "tgpagella (Type1 Palatino)"),
    (PKG_CMD + r"\{mathpazo\}", "mathpazo (Type1)"),
    (PKG_CMD + r"(?:\[[^\]]*\])?\{lmodern\}", "lmodern"),
]

MAGIC_PROGRAM = re.compile(r"%\s*!TEX\s+program\s*=\s*(\S+)", re.IGNORECASE)
MAGIC_ROOT = re.compile(r"%\s*!TEX\s+root\s*=\s*(\S+)", re.IGNORECASE)
DOCUMENTCLASS = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{[^}]+\}")
HANGUL_RANGE = re.compile(r"[\uAC00-\uD7A3]")  # Korean Hangul syllables block
DOTPATH_RE = re.compile(r"(?:/Users/|/home/|~/)[\w./-]+")


# ─── Status helpers ─────────────────────────────────────────────
class Status:
    OK = "\033[32m✅\033[0m"
    WARN = "\033[33m⚠️ \033[0m"
    FAIL = "\033[31m❌\033[0m"
    INFO = "\033[36mℹ️ \033[0m"


def header(text: str) -> None:
    print(f"\n\033[1m{text}\033[0m")
    print("─" * len(text))


def line(status: str, text: str) -> None:
    print(f"  {status} {text}")


# ─── Tool discovery ─────────────────────────────────────────────
def _resolved_texlive_bin(project_dir: str | None = None) -> str | None:
    """scripts/texlive_env.sh 가 해석한 TeX Live bin 디렉토리.

    엔진과 연도는 프로젝트가 정한다 (CLAUDE.md 의 latex-engine /
    latex-texlive, 또는 override 환경변수). 진단도 실제 빌드와 같은 배포판을
    봐야 한다 — 시스템 PATH 의 다른 연도를 보면 '있다/없다' 판정이 빌드와
    어긋난다.

    프로젝트에 설정이 없으면 texlive_env.sh 가 exit 4 로 끝난다. 그때는
    None 을 돌려주고, 호출부가 "설정 없음"으로 보고한다. 임의의 배포판을
    골라 대신 진단하지 않는다.
    """
    global TL_ENGINE
    TL_ENGINE = None
    env_sh = Path(__file__).resolve().parent / "texlive_env.sh"
    if not env_sh.is_file():
        return None
    env = dict(os.environ)
    if project_dir:
        env["PROJECT_DIR"] = str(project_dir)
    try:
        out = subprocess.run(
            ["bash", str(env_sh), "--print-env"],
            capture_output=True, text=True, timeout=20, env=env,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0:
        return None
    values = dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)
    TL_ENGINE = values.get("LATEX_ENGINE")
    return values.get("TL_BIN") or None


def available_engines() -> str:
    """이 머신에서 쓸 수 있는 엔진/연도 조합 목록 (사람이 읽는 표)."""
    env_sh = Path(__file__).resolve().parent / "texlive_env.sh"
    try:
        out = subprocess.run(
            ["bash", str(env_sh), "--list"],
            capture_output=True, text=True, timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return out.stdout or out.stderr


TL_BIN: str | None = None
TL_ENGINE: str | None = None


def check_tool(name: str) -> str | None:
    """고정된 TeX Live에서만 찾는다. 시스템 PATH로 넘어가지 않는다."""
    if TL_BIN:
        cand = Path(TL_BIN) / name
        return str(cand) if cand.is_file() and os.access(cand, os.X_OK) else None
    return shutil.which(name)


def kpsewhich(pkg: str) -> str | None:
    kpse = check_tool("kpsewhich") or shutil.which("kpsewhich")
    if not kpse:
        return None
    try:
        out = subprocess.run(
            [kpse, pkg], capture_output=True, text=True, timeout=5
        )
        path = out.stdout.strip()
        return path if path else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def fc_list_korean() -> list[str]:
    if not shutil.which("fc-list"):
        return []
    try:
        out = subprocess.run(
            ["fc-list", ":lang=ko", "family"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        families = sorted(set(out.stdout.strip().splitlines()))
        return families
    except (subprocess.TimeoutExpired, OSError):
        return []


# ─── Project scan ───────────────────────────────────────────────
def find_main_tex(root: Path) -> Path | None:
    """Find the main .tex file: % !TEX root preferred, else first \\documentclass."""
    tex_files = sorted(root.rglob("*.tex"))
    # Filter out common non-main files
    tex_files = [f for f in tex_files if "build" not in f.parts and ".git" not in f.parts]

    # Pass 1: look for % !TEX root references — they POINT to the main file
    referenced_main: Path | None = None
    for f in tex_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")[:1000]
        except OSError:
            continue
        m = MAGIC_ROOT.search(text)
        if m:
            target = (f.parent / m.group(1)).resolve()
            if target.exists():
                referenced_main = target
                break
    if referenced_main:
        return referenced_main

    # Pass 2: first .tex with \documentclass
    for f in tex_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if DOCUMENTCLASS.search(text):
            return f
    return None


def _scan_text(text: str) -> dict:
    """Scan a single .tex/.sty body for Korean/pdfLaTeX-only markers."""
    korean = [name for pat, name in KOREAN_PACKAGE_PATTERNS if re.search(pat, text)]
    pdflatex_only = [name for pat, name in PDFLATEX_ONLY_MARKERS if re.search(pat, text)]
    has_fontspec = bool(re.search(FONTSPEC_PATTERN, text))
    return {
        "korean_packages": korean,
        "pdflatex_only_markers": pdflatex_only,
        "has_fontspec": has_fontspec,
    }


def _find_local_sty_deps(text: str, base_dir: Path) -> list[Path]:
    """Find .sty files referenced by \\usepackage{...} that exist locally."""
    deps: list[Path] = []
    pat = PKG_CMD + r"(?:\[[^\]]*\])?\{([^}]+)\}"
    for m in re.finditer(pat, text):
        # \usepackage can take comma-separated list: {a,b,c}
        for pkg in (p.strip() for p in m.group(1).split(",")):
            sty_path = base_dir / f"{pkg}.sty"
            if sty_path.exists() and sty_path not in deps:
                deps.append(sty_path)
    return deps


def scan_preamble(tex_path: Path) -> dict:
    """Scan main .tex preamble AND any locally-shipped .sty files it loads.

    pdfLaTeX-only markers are often hidden inside wrapper .sty packages
    (e.g. journal/lab templates), not in main.tex itself.
    """
    text = tex_path.read_text(encoding="utf-8", errors="replace")

    # Extract preamble (everything before \begin{document})
    preamble_end = text.find(r"\begin{document}")
    preamble = text[:preamble_end] if preamble_end > 0 else text

    main_scan = _scan_text(preamble)
    custom_sty = _find_local_sty_deps(preamble, tex_path.parent)

    # Recursively merge findings from custom .sty files
    sty_findings: dict[str, list[str]] = {}
    for sty in custom_sty:
        sty_text = sty.read_text(encoding="utf-8", errors="replace")
        sub = _scan_text(sty_text)
        for name in sub["korean_packages"]:
            if name not in main_scan["korean_packages"]:
                main_scan["korean_packages"].append(name)
        for name in sub["pdflatex_only_markers"]:
            if name not in main_scan["pdflatex_only_markers"]:
                main_scan["pdflatex_only_markers"].append(name)
        if sub["has_fontspec"]:
            main_scan["has_fontspec"] = True
        if sub["pdflatex_only_markers"] or sub["korean_packages"]:
            sty_findings[sty.name] = (
                sub["pdflatex_only_markers"] + sub["korean_packages"]
            )

    program_match = MAGIC_PROGRAM.search(text[:500])
    program = program_match.group(1).lower() if program_match else None

    has_korean_text = bool(HANGUL_RANGE.search(text))

    return {
        "tex_path": tex_path,
        "korean_packages": main_scan["korean_packages"],
        "pdflatex_only_markers": main_scan["pdflatex_only_markers"],
        "has_fontspec": main_scan["has_fontspec"],
        "magic_program": program,
        "custom_sty_files": custom_sty,
        "sty_findings": sty_findings,
        "has_korean_in_source": has_korean_text,
    }


def scan_bib_for_korean(root: Path) -> list[Path]:
    return [
        f
        for f in root.rglob("*.bib")
        if ".git" not in f.parts
        and HANGUL_RANGE.search(f.read_text(encoding="utf-8", errors="replace"))
    ]


def scan_log_for_missing_chars(root: Path) -> int:
    count = 0
    for log in root.rglob("*.log"):
        if ".git" in log.parts or "build" in log.parts:
            # Still check build/ logs since those are the most recent
            if "build" not in log.parts:
                continue
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        count += len(re.findall(r"Missing character", text))
    return count


def scan_absolute_paths(root: Path) -> list[tuple[Path, str]]:
    hits: list[tuple[Path, str]] = []
    for ext in ("*.tex", "*.sty", "*.bib", "*.cls"):
        for f in root.rglob(ext):
            if ".git" in f.parts or "build" in f.parts:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in DOTPATH_RE.finditer(text):
                hits.append((f, m.group(0)))
    return hits


# ─── Recommendation engine ──────────────────────────────────────
def recommend(report: dict, env: dict) -> list[str]:
    recs: list[str] = []
    pre = report["preamble"]

    engine = env.get("engine")
    if not engine:
        recs.append("프로젝트 engine/TeX Live를 먼저 확인한다. 임의로 엔진을 전환하지 않는다.")
    elif not env.get("engine_tool"):
        recs.append(f"선택된 엔진 {engine}이 해석된 TeX Live에 없다. 배포판을 확인한다.")

    if pre["korean_packages"]:
        recs.append(
            f"✅ 한글 패키지 이미 있음: {', '.join(pre['korean_packages'])}. "
            "magic comment만 점검하면 됨."
        )
    else:
        recs.append(
            "→ Phase 3a-d 적용 필요: korean-patch.sty 주입 + magic comment 추가."
        )

    if pre["pdflatex_only_markers"]:
        recs.append(
            f"⚠️  pdfLaTeX 전용 marker 검출: {', '.join(pre['pdflatex_only_markers'])}. "
            "선택된 프로젝트 엔진과 패키지 호환성을 확인한다. 이 탐지만으로 엔진 변경을 결정하지 않는다."
        )

    if pre["custom_sty_files"]:
        sty_names = [s.name for s in pre["custom_sty_files"]]
        recs.append(
            f"⚠️  Custom .sty 파일 발견: {', '.join(sty_names)}. "
            "이 파일들을 직접 수정하지 말고 korean-patch.sty wrapper로 주입할 것."
        )

    if engine and not pre["magic_program"]:
        recs.append(
            f"main.tex의 로컬 magic comment를 `% !TEX program = {engine}`으로 맞춘다."
        )
    elif engine and pre["magic_program"] != engine:
        recs.append(
            f"magic comment `{pre['magic_program']}`가 선택 engine `{engine}`와 다르다. 설정을 확인한다."
        )

    if report["bib_with_korean"]:
        recs.append(
            f"ℹ️  .bib 파일에 한글 있음 ({len(report['bib_with_korean'])}개). "
            "`biber` + `\\usepackage{biblatex}` 권장."
        )

    if report["missing_char_warnings"] > 0:
        recs.append(
            f"❌ 마지막 빌드 .log에서 'Missing character' 경고 {report['missing_char_warnings']}건. "
            "이게 'PDF 변경 안 반영됨'의 직접 증거."
        )

    if report["abs_path_hits"]:
        recs.append(
            f"❌ 시스템 절대경로가 source에 박힘 ({len(report['abs_path_hits'])}개). "
            "Overleaf 라운드트립 시 깨짐."
        )

    if env["kotex"] is None and env["xecjk"] is None:
        recs.append(
            "⚠️  kotex/xeCJK 둘 다 설치 안됨. `tlmgr install kotex-utf` 또는 MacTeX full 설치."
        )

    if not env["fonts_korean"] and pre["korean_packages"] == ["xeCJK"]:
        recs.append(
            "⚠️  시스템에 한글 폰트 없음. xeCJK 모드 쓰려면 "
            "`brew install --cask font-noto-sans-cjk-kr` 필요."
        )

    return recs


# ─── Main ───────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project_dir", nargs="?", default=".", help="Project root (default: cwd)"
    )
    args = parser.parse_args()
    root = Path(args.project_dir).resolve()

    if not root.exists():
        print(f"❌ Directory not found: {root}", file=sys.stderr)
        return 2

    print(f"\n\033[1mlatex-publication — Phase 1 Diagnostic\033[0m")
    print(f"Project: {root}")

    # 엔진·배포판은 프로젝트가 정한다. 진단도 그 배포판을 본다.
    global TL_BIN
    TL_BIN = _resolved_texlive_bin(root)

    header("Engine")
    if TL_BIN:
        line(Status.OK, f"해석된 TeX Live bin: {TL_BIN}")
    else:
        line(
            Status.WARN,
            "이 프로젝트의 엔진·TeX Live 설정을 찾지 못함 "
            "(CLAUDE.md 의 latex-engine / latex-texlive)",
        )
        print(
            "      설정이 없으면 compile.sh 는 빌드하지 않고 exit 4 로 끝난다.\n"
            "      아래에서 하나를 골라 CLAUDE.md 에 두 줄로 적을 것."
        )
        listing = available_engines()
        if listing:
            print("".join(f"      {ln}\n" for ln in listing.rstrip().splitlines()))

    # Environment checks
    header("Environment")
    env = {
        "engine": TL_ENGINE,
        "engine_tool": check_tool(TL_ENGINE) if TL_ENGINE else None,
        "xelatex": check_tool("xelatex"),
        "lualatex": check_tool("lualatex"),
        "latexmk": check_tool("latexmk"),
        "kotex": kpsewhich("kotex.sty"),
        "xecjk": kpsewhich("xeCJK.sty"),
        "fonts_korean": fc_list_korean(),
    }
    line(Status.OK if env["engine_tool"] else Status.WARN, f"selected engine {TL_ENGINE or '(unresolved)'}: {env['engine_tool'] or '(not found)'}")
    line(Status.OK if env["latexmk"] else Status.WARN, f"latexmk: {env['latexmk'] or '(not found — latexmkrc will be ignored)'}")
    line(Status.OK if env["kotex"] else Status.WARN, f"kotex.sty: {env['kotex'] or '(not in TeX Live)'}")
    line(Status.OK if env["xecjk"] else Status.INFO, f"xeCJK.sty: {env['xecjk'] or '(not installed)'}")
    if env["fonts_korean"]:
        line(Status.OK, f"Korean fonts: {len(env['fonts_korean'])} family/families")
        for f in env["fonts_korean"][:5]:
            line(" " * 3, f"- {f}")
    else:
        line(Status.WARN, "Korean fonts: none detected (fc-list :lang=ko empty)")

    # Project scan
    header("Project structure")
    main_tex = find_main_tex(root)
    if not main_tex:
        line(Status.FAIL, "No .tex file with \\documentclass found.")
        return 1
    line(Status.OK, f"Main .tex: {main_tex.relative_to(root) if main_tex.is_relative_to(root) else main_tex}")

    pre = scan_preamble(main_tex)
    bib_korean = scan_bib_for_korean(root)
    missing_chars = scan_log_for_missing_chars(root)
    abs_paths = scan_absolute_paths(root)

    # Preamble report
    header("Preamble analysis")
    line(
        Status.OK if pre["magic_program"] == "xelatex" else Status.WARN,
        f"Magic program: {pre['magic_program'] or '(none)'}",
    )
    line(
        Status.OK if pre["korean_packages"] else Status.FAIL,
        f"Korean packages: {pre['korean_packages'] or '(none — Korean cannot render)'}",
    )
    line(
        Status.WARN if pre["pdflatex_only_markers"] else Status.OK,
        f"pdfLaTeX-only markers: {pre['pdflatex_only_markers'] or '(clean)'}",
    )
    line(
        Status.INFO,
        f"Custom .sty files: {[s.name for s in pre['custom_sty_files']] or '(none)'}",
    )
    if pre["sty_findings"]:
        for sty_name, findings in pre["sty_findings"].items():
            line(
                Status.WARN,
                f"  └ {sty_name} contains: {findings}",
            )
    line(
        Status.INFO,
        f"Korean text in source: {'yes' if pre['has_korean_in_source'] else 'no'}",
    )

    # Bib + log + paths
    header("Other checks")
    line(
        Status.WARN if bib_korean else Status.OK,
        f".bib files with Korean: {len(bib_korean)}",
    )
    line(
        Status.FAIL if missing_chars > 0 else Status.OK,
        f"'Missing character' warnings in .log: {missing_chars}",
    )
    line(
        Status.FAIL if abs_paths else Status.OK,
        f"System absolute paths in source: {len(abs_paths)}",
    )
    if abs_paths:
        for f, p in abs_paths[:5]:
            line(" " * 3, f"- {f.name}: {p}")

    # Recommendations
    report = {
        "preamble": pre,
        "bib_with_korean": bib_korean,
        "missing_char_warnings": missing_chars,
        "abs_path_hits": abs_paths,
    }
    recs = recommend(report, env)

    header("Recommendations")
    if not recs:
        print("  ✅ 셋업 완료 상태. 추가 패치 불필요.")
    for r in recs:
        print(f"  {r}")

    print()
    print(f"Next: review recommendations above, then run Phase 3-4 (apply patches).")
    print(f"      Templates at: {Path(__file__).resolve().parent.parent / 'templates'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

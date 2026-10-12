#!/usr/bin/env python3
"""paper-frontmatter 훅 설치기 — settings.json에 이름 붙은 훅 항목만 멱등 병합한다.

    install-paper-frontmatter-hooks.py --setup-venv                 # PyYAML 전용 venv 생성 (1회 네트워크)
    install-paper-frontmatter-hooks.py --merge-settings --dry-run   # 병합 결과만 출력 (파일 미변경)
    install-paper-frontmatter-hooks.py --merge-settings             # ~/.claude/settings.json 병합 (백업 후 원자적 교체)
    install-paper-frontmatter-hooks.py --merge-settings --settings PATH   # 다른 파일에 병합 (테스트용)
    install-paper-frontmatter-hooks.py --uninstall [--settings PATH]      # 우리 항목만 제거
    install-paper-frontmatter-hooks.py --verify [--settings PATH]         # 설치 여부·다른 항목 보존 확인

안전 규칙:
  * 우리 항목은 command에 `paper-frontmatter-hook.sh`가 들어 있는 것으로만 식별한다.
  * 다른 이벤트·matcher·훅 항목과 최상위 키는 손대지 않는다. 병합 전후에 "우리 항목을 뺀 나머지"가
    완전히 같은지 검증하고, 다르면 쓰지 않는다.
  * settings 내용을 stdout에 통째로 출력하지 않는다 (비밀이 들어 있을 수 있다). 훅 항목 요약만 보여 준다.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
WRAPPER = HOOKS_DIR / "paper-frontmatter-hook.sh"
VENV_DIR = HOOKS_DIR / "paper-frontmatter-venv"
DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"
MARK = "paper-frontmatter-hook.sh"
TOOL_MATCHER = "Write|Edit|MultiEdit"


def our_entries() -> dict[str, list[dict]]:
    w = str(WRAPPER)
    return {
        "PreToolUse": [{"matcher": TOOL_MATCHER, "hooks": [
            {"type": "command", "command": f"bash \"{w}\" pre", "timeout": 20}]}],
        "PostToolUse": [{"matcher": TOOL_MATCHER, "hooks": [
            {"type": "command", "command": f"bash \"{w}\" post", "timeout": 20}]}],
        "Stop": [{"matcher": "", "hooks": [
            {"type": "command", "command": f"bash \"{w}\" stop", "timeout": 60}]}],
    }


def _is_ours(hook: dict) -> bool:
    return isinstance(hook, dict) and MARK in str(hook.get("command", ""))


def strip_ours(settings: dict) -> dict:
    """우리 훅 항목만 제거한 사본. 비게 된 matcher 그룹은 우리 것이었을 때만 지운다."""
    s = copy.deepcopy(settings)
    hooks = s.get("hooks")
    if not isinstance(hooks, dict):
        return s
    for event, groups in list(hooks.items()):
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for g in groups:
            if not isinstance(g, dict):
                kept_groups.append(g)
                continue
            inner = g.get("hooks")
            if not isinstance(inner, list):
                kept_groups.append(g)
                continue
            had_ours = any(_is_ours(h) for h in inner)
            remaining = [h for h in inner if not _is_ours(h)]
            if remaining or not had_ours:
                g2 = dict(g)
                g2["hooks"] = remaining
                kept_groups.append(g2)
        hooks[event] = kept_groups
    return s


def merge(settings: dict) -> dict:
    base = strip_ours(settings)
    hooks = base.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SystemExit("settings.hooks가 객체가 아니다 — 수동 확인 필요")
    for event, groups in our_entries().items():
        lst = hooks.setdefault(event, [])
        if not isinstance(lst, list):
            raise SystemExit(f"settings.hooks.{event}가 리스트가 아니다 — 수동 확인 필요")
        for g in groups:
            lst.append(copy.deepcopy(g))
    return base


def summarize(settings: dict) -> str:
    hooks = settings.get("hooks", {}) if isinstance(settings.get("hooks"), dict) else {}
    lines = []
    for event, groups in hooks.items():
        ours = others = 0
        for g in groups if isinstance(groups, list) else []:
            for h in (g.get("hooks") if isinstance(g, dict) else []) or []:
                if _is_ours(h):
                    ours += 1
                else:
                    others += 1
        lines.append(f"  {event}: 우리 항목 {ours}, 기타 항목 {others}")
    return "\n".join(lines) or "  (hooks 없음)"


def load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("settings.json 최상위가 객체가 아니다")
    return data


def write_settings(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-paper-frontmatter-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, backup)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".settings-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return backup


def _normalize_for_compare(settings: dict) -> dict:
    """비교용 정규화: 우리 항목을 뺀 뒤, 설치 과정에서 생길 수 있는 빈 컨테이너(hooks.<event>: [] / hooks: {})를
    없는 것과 같게 본다. 실제 파일에는 손대지 않고 비교에만 쓴다."""
    s = strip_ours(settings)
    hooks = s.get("hooks")
    if isinstance(hooks, dict):
        for event in list(hooks):
            if hooks[event] == []:
                del hooks[event]
        if not hooks:
            del s["hooks"]
    return s


def verify_preserved(before: dict, after: dict) -> bool:
    """우리 항목과 빈 컨테이너를 제외한 나머지 설정이 완전히 같은가."""
    return _normalize_for_compare(before) == _normalize_for_compare(after)


def setup_venv() -> int:
    if (VENV_DIR / "bin" / "python").exists():
        rc = subprocess.run([str(VENV_DIR / "bin" / "python"), "-c", "import yaml"], capture_output=True).returncode
        if rc == 0:
            print(f"venv 이미 준비됨: {VENV_DIR}")
            return 0
    uv = shutil.which("uv") or (str(Path.home() / ".local" / "bin" / "uv") if (Path.home() / ".local" / "bin" / "uv").exists() else None)
    try:
        if uv:
            subprocess.run([uv, "venv", "--quiet", str(VENV_DIR)], check=True)
            subprocess.run([uv, "pip", "install", "--quiet", "--python", str(VENV_DIR / "bin" / "python"), "pyyaml>=6"], check=True)
        else:
            subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
            subprocess.run([str(VENV_DIR / "bin" / "python"), "-m", "pip", "install", "--quiet", "pyyaml>=6"], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"venv 생성 실패: {exc}", file=sys.stderr)
        return 2
    rc = subprocess.run([str(VENV_DIR / "bin" / "python"), "-c", "import yaml; print('pyyaml', yaml.__version__)"]).returncode
    return 0 if rc == 0 else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    ap.add_argument("--setup-venv", action="store_true")
    ap.add_argument("--merge-settings", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not (args.setup_venv or args.merge_settings or args.uninstall or args.verify):
        ap.error("--setup-venv, --merge-settings, --uninstall, --verify 중 하나가 필요하다")
    rc = 0
    if args.setup_venv:
        rc = setup_venv()
        if rc:
            return rc
    path = Path(args.settings).expanduser()
    if args.merge_settings or args.uninstall:
        if not WRAPPER.exists() and args.merge_settings:
            print(f"래퍼가 없다: {WRAPPER}", file=sys.stderr)
            return 2
        before = load_settings(path)
        after = merge(before) if args.merge_settings else strip_ours(before)
        if not verify_preserved(before, after):
            print("검증 실패: 우리 항목 외의 설정이 달라진다 — 쓰지 않는다", file=sys.stderr)
            return 2
        print(f"settings: {path}")
        print("병합 전:\n" + summarize(before))
        print("병합 후:\n" + summarize(after))
        if after == before:
            print("변경 없음 (이미 같은 상태)")
            return 0
        if args.dry_run:
            print("dry-run: 파일을 바꾸지 않았다")
            return 0
        backup = write_settings(path, after)
        reread = load_settings(path)
        if reread != after or not verify_preserved(before, reread):
            print("쓰기 후 검증 실패 — 백업에서 복구하라: " + str(backup), file=sys.stderr)
            return 2
        print(f"완료. 백업: {backup}")
    if args.verify:
        s = load_settings(path)
        hooks = s.get("hooks", {}) if isinstance(s.get("hooks"), dict) else {}
        want = our_entries()
        ok = True
        for event, groups in want.items():
            present = [g for g in hooks.get(event, []) if isinstance(g, dict)
                       and any(_is_ours(h) for h in g.get("hooks", []))]
            print(f"  {event}: {'설치됨' if present else '미설치'}")
            ok = ok and bool(present)
        print("훅 요약:\n" + summarize(s))
        return 0 if ok else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())

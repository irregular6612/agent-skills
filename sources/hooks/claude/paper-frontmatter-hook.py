#!/usr/bin/env python3
"""Claude Code hook — `type: paper` 노트 frontmatter 스키마 강제 (v4, 13키).

사용:  paper-frontmatter-hook.py pre|post|stop   (stdin = Claude Code hook JSON)

  pre  (PreToolUse Write|Edit|MultiEdit)  예방: 쓰기 전에 결과물을 계산해 검증. 위반이면 exit 2 (차단).
       - 새 내용이 paper면 13키 계약을 만족해야 한다.
       - 기존 파일이 paper였는데 새 내용이 paper가 아니면(type 제거/변경) 차단 — type 삭제로 검증을 우회할 수 없다.
       - 비-paper(.md라도 type≠paper)는 통과. 비-.md는 통과.
  post (PostToolUse Write|Edit|MultiEdit) 탐지: 실제 파일을 다시 읽어 검증. 되돌릴 수는 없고 exit 2로 모델에 피드백.
  stop (Stop)                              탐지: vault 전체 감사. Bash 등 다른 경로로 쓴 파일을 잡는다.
       stop_hook_active=true 이면 즉시 exit 0 (무한 루프 방지). 자동 수정은 하지 않는다.

fail-closed 원칙: 엔진(paper_frontmatter.py)이나 PyYAML을 못 찾으면, 대상(기존 파일 또는 새 내용)에
frontmatter 여는 줄이 있는 한 차단한다 — 좁은 정규식으로 "paper가 아니다"를 확정할 수 없기 때문이다.
frontmatter가 전혀 없는 평범한 .md만 통과한다. 엔진이 있어도 YAML을 해석할 수 없는(kind=error) 후보는 차단한다.

적용 범위: 설정된 vault($PAPER_VAULT_ROOT 또는 기본 경로) 안의 .md만 검사한다. 다른 저장소의 파일은 검사하지
않는다. vault 안이라도 경로 구성요소에 심볼릭 링크가 있으면 외부로 새는 것을 막기 위해 차단한다.

엔진 위치: $PAPER_FRONTMATTER_TOOLS_DIR(운영자 명시 재정의) → 설정된 vault의 Public/_tools. 대상 파일의 상위
디렉터리를 거슬러 올라가며 찾지 않는다 (신뢰할 수 없는 저장소의 코드를 실행하지 않기 위해).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

DEFAULT_VAULT = Path(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes"
)
ENGINE_REL = Path("Public") / "_tools" / "paper_frontmatter.py"
HOOK_TOOLS = ("Write", "Edit", "MultiEdit")
_FM_OPEN_RE = re.compile(r"^\ufeff?---[ \t]*(?:\r?\n|\Z)")
STOP_MAX_LIST = 40
CACHE_PATH = Path.home() / ".claude" / "hooks" / ".paper-frontmatter-stop-cache.json"


def _log(msg: str) -> None:
    sys.stderr.write(msg.rstrip("\n") + "\n")


def _vault_root() -> Path:
    env = os.environ.get("PAPER_VAULT_ROOT")
    return Path(env).expanduser() if env else DEFAULT_VAULT


def find_engine(start: Path | None = None) -> Path | None:
    """신뢰하는 위치에서만 엔진을 찾는다. `start`는 호환용으로 남겨 두었고 무시한다."""
    env = os.environ.get("PAPER_FRONTMATTER_TOOLS_DIR")
    cands: list[Path] = []
    if env:
        cands.append(Path(env).expanduser() / "paper_frontmatter.py")
    cands.append(_vault_root() / ENGINE_REL)
    for c in cands:
        if c.is_file():
            return c
    return None


def load_engine(start: Path | None = None):
    """(module, error_message). 로드 실패는 문자열로 돌려주고 호출자가 fail-closed 판단한다."""
    path = find_engine(start)
    if path is None:
        return None, "paper_frontmatter.py 엔진을 찾을 수 없다 (PAPER_FRONTMATTER_TOOLS_DIR 또는 vault의 Public/_tools)"
    try:
        spec = importlib.util.spec_from_file_location("paper_frontmatter", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules["paper_frontmatter"] = mod  # dataclass가 모듈을 sys.modules에서 찾는다
        spec.loader.exec_module(mod)
    except Exception as exc:  # 어떤 import 오류도 보고한다
        return None, f"엔진 로드 실패 {path}: {type(exc).__name__}: {exc}"
    if not getattr(mod, "_yaml_available", lambda: False)():
        return None, f"PyYAML이 없다 (interpreter={sys.executable}). paper-frontmatter-venv를 설치하거나 PAPER_FRONTMATTER_PYTHON을 지정하라"
    return mod, None


def has_frontmatter_opening(text: str | None) -> bool:
    """엔진 없이 판단할 수 있는 유일한 사실: 여는 `---` 줄이 있는가 (BOM/CRLF 포함). 있으면 paper일 수 있다."""
    return bool(text) and bool(_FM_OPEN_RE.match(text))


def looks_like_paper(text: str | None) -> bool:
    """호환용 이름. 엔진이 없을 때 '검사가 필요한가'의 보수적 판정 = frontmatter 여는 줄 존재 여부."""
    return has_frontmatter_opening(text)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _resolve_target(payload: dict, tool_input: dict) -> tuple[Path | None, str | None]:
    """(검사할 경로, 건너뛰거나 차단할 사유).

    반환 (None, None)         : 검사 대상 아님 (경로 없음, .md 아님, 설정된 vault 밖) → 통과.
    반환 (None, "BLOCK: ...")  : vault 안이지만 심볼릭 링크 구성요소가 있어 외부로 샐 수 있다 → 차단.
    반환 (path, None)          : vault 안의 일반 경로.
    """
    fp = tool_input.get("file_path") or tool_input.get("path") or ""
    if not isinstance(fp, str) or not fp:
        return None, None
    path = Path(fp).expanduser()
    if not path.is_absolute():
        path = Path(payload.get("cwd") or os.getcwd()) / path
    path = Path(os.path.normpath(str(path)))  # `..` 를 어휘적으로 정리 (심볼릭 링크는 따라가지 않는다)
    if path.suffix.lower() != ".md":
        return None, None
    vault = _vault_root()
    roots = {vault}
    try:
        roots.add(vault.resolve())
    except OSError:
        pass
    inside = False
    for root in roots:
        try:
            relp = path.relative_to(root)
            inside = True
            break
        except ValueError:
            continue
    if not inside:
        return None, None
    cur = root
    for part in relp.parts:
        cur = cur / part
        if cur.is_symlink():
            return None, f"BLOCK: vault 안 경로의 구성요소가 심볼릭 링크다 ({cur}). 외부 대상을 조용히 읽거나 바꾸지 않는다"
    return path, None


def candidate_after_edit(current: str | None, tool: str, tool_input: dict) -> tuple[str | None, str | None]:
    """(새 내용, 계산 불가 사유). Write/Edit/MultiEdit 의미론을 그대로 흉내 낸다."""
    if tool == "Write":
        content = tool_input.get("content")
        return (content if isinstance(content, str) else None), (None if isinstance(content, str) else "content 없음")
    if current is None:
        return None, "기존 파일을 읽을 수 없다 (Edit는 기존 파일이 필요) — 도구 자체가 실패할 것"
    edits = [tool_input] if tool == "Edit" else list(tool_input.get("edits") or [])
    text = current
    for e in edits:
        old = e.get("old_string")
        new = e.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str):
            return None, "old_string/new_string 없음"
        if old == "":
            return None, "빈 old_string"
        if old not in text:
            return None, "old_string이 파일에 없다 — 도구 자체가 실패할 것"
        if e.get("replace_all"):
            text = text.replace(old, new)
        else:
            if text.count(old) > 1:
                return None, "old_string이 여러 번 나온다 — 도구 자체가 실패할 것"
            text = text.replace(old, new, 1)
    return text, None


def _format_issues(engine, path: Path, issues) -> str:
    lines = [f"PAPER_FRONTMATTER_VIOLATION: {path}",
             f"type: paper 노트의 frontmatter는 정확히 다음 13개 키를 이 순서로 가져야 한다 (빈 값 `Key:` 허용, 그 외 키 금지):",
             "  " + ", ".join(engine.PAPER_KEYS), "위반:"]
    for i in issues:
        lines.append(f"  - {i}")
    lines.append("값을 추측해 채우지 말고, 금지 키는 제거하고, 없는 키는 빈 값으로 두라. 기존 노트라면 "
                 "`python3 Public/_tools/paper_frontmatter.py fix --dry-run <file>`로 계획을 먼저 확인하라.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# pre / post
# ---------------------------------------------------------------------------

def _current_text(path: Path) -> tuple[str | None, str | None]:
    """(기존 내용, 읽기 오류). 파일이 없으면 (None, None)."""
    if not path.exists():
        return None, None
    text = _read_text(path)
    if text is None:
        return None, "기존 파일을 읽거나 UTF-8로 디코드할 수 없다"
    return text, None


def run_pre(payload: dict) -> int:
    tool = payload.get("tool_name", "")
    if tool not in HOOK_TOOLS:
        return 0
    ti = payload.get("tool_input") or {}
    path, block = _resolve_target(payload, ti)
    if block:
        _log(f"PAPER_FRONTMATTER_HOOK_ERROR (fail-closed): {block}")
        return 2
    if path is None:
        return 0
    current, read_err = _current_text(path)
    new_text, why = candidate_after_edit(current, tool, ti)
    engine, err = load_engine()
    if engine is None:
        # 엔진/PyYAML 없음: frontmatter가 있는 후보는 paper일 수 있으므로 판정을 확정하지 않고 차단한다.
        if has_frontmatter_opening(new_text) or has_frontmatter_opening(current) or read_err:
            _log(f"PAPER_FRONTMATTER_HOOK_ERROR (fail-closed): {err}\n대상: {path}"
                 + (f"\n추가: {read_err}" if read_err else ""))
            return 2
        return 0
    if read_err:
        _log(f"PAPER_FRONTMATTER_HOOK_ERROR (fail-closed): {read_err}\n대상: {path}")
        return 2
    if new_text is None:
        # 결과를 계산할 수 없는 편집(old_string 불일치 등)은 도구가 스스로 실패한다.
        # 다만 기존 paper 파일이라면 PostToolUse/Stop이 다시 본다.
        return 0
    old_info = engine.classify_text(current) if current is not None else None
    new_info = engine.classify_text(new_text)
    old_paper = old_info is not None and old_info.is_paper_candidate
    if old_paper and not new_info.is_paper_candidate:
        _log(f"PAPER_FRONTMATTER_VIOLATION: {path}\n기존 노트는 `type: paper`인데 이 편집은 type을 제거하거나 바꾼다 "
             f"(새 분류: {new_info.kind}). type 삭제로 검증을 우회할 수 없다. 재분류가 정말 필요하면 사용자에게 확인하고 "
             "Bash/CLI로 진행하라 (Stop 감사에 기록된다).")
        return 2
    if new_info.kind == "paper":
        issues = engine.validate_paper(new_info.parsed) + list(new_info.encoding_issues)
        if issues:
            _log(_format_issues(engine, path, issues))
            return 2
        return 0
    if new_info.kind == "paper-broken":
        _log(_format_issues(engine, path, list(new_info.issues) + list(new_info.encoding_issues)))
        return 2
    if new_info.kind == "error":
        _log(f"PAPER_FRONTMATTER_HOOK_ERROR (fail-closed): {path}\n새 내용의 frontmatter를 해석할 수 없어 "
             f"paper 여부를 판정할 수 없다: " + "; ".join(str(i) for i in list(new_info.issues) + list(new_info.encoding_issues)))
        return 2
    return 0


def run_post(payload: dict) -> int:
    tool = payload.get("tool_name", "")
    if tool not in HOOK_TOOLS:
        return 0
    ti = payload.get("tool_input") or {}
    path, block = _resolve_target(payload, ti)
    if block:
        _log(f"PAPER_FRONTMATTER_HOOK_ERROR (fail-closed): {block}")
        return 2
    if path is None or not path.exists():
        return 0
    text, read_err = _current_text(path)
    engine, err = load_engine()
    if engine is None:
        if has_frontmatter_opening(text) or read_err:
            _log(f"PAPER_FRONTMATTER_HOOK_ERROR (fail-closed): {err}\n대상: {path}"
                 + (f"\n추가: {read_err}" if read_err else ""))
            return 2
        return 0
    info = engine.classify_file(path)
    if info.kind == "paper":
        issues = engine.validate_paper(info.parsed) + list(info.encoding_issues)
        if issues:
            _log(_format_issues(engine, path, issues) + "\n(PostToolUse: 이미 기록됐다. 되돌릴 수 없으니 지금 고쳐라.)")
            return 2
    elif info.kind == "paper-broken":
        _log(_format_issues(engine, path, list(info.issues) + list(info.encoding_issues)))
        return 2
    elif info.kind == "error":
        _log(f"PAPER_FRONTMATTER_HOOK_ERROR (PostToolUse, 판정 불가): {path}\n"
             + "; ".join(str(i) for i in list(info.issues) + list(info.encoding_issues)))
        return 2
    return 0


# ---------------------------------------------------------------------------
# stop — vault 전체 감사 (내용 sha256 캐시: 파일은 매번 읽고 해시하되, 파싱만 생략한다)
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        os.replace(tmp, CACHE_PATH)
    except OSError:
        pass


def _classify_bytes(engine, raw: bytes):
    """엔진의 classify_raw가 있으면 쓰고, 없으면(구버전 엔진) 텍스트 경로로 대체한다."""
    if hasattr(engine, "classify_raw"):
        return engine.classify_raw(raw)
    text, issues = engine.decode_bytes(raw)
    if text is None:
        return engine.NoteInfo("error", None, issues=issues)
    return engine.classify_text(text, encoding_issues=[i for i in issues if i.code.startswith("ENC-")])


def audit_vault(engine, vault: Path, *, use_cache: bool = True) -> tuple[list[tuple[str, list[str]]], int]:
    """[(relpath, [issue strings])], scanned_count.

    캐시 키 = 내용 sha256 (+ engine sha). size/mtime은 믿지 않는다 — 같은 크기·mtime으로 바뀐 내용도 잡는다.
    읽기/파싱 오류(kind=error)는 조용히 건너뛰지 않고 발견 항목으로 보고한다.
    """
    engine_sig = hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest()[:16]
    cache = _load_cache() if use_cache else {}
    if not isinstance(cache, dict) or cache.get("engine") != engine_sig or cache.get("v") != 2:
        cache = {"engine": engine_sig, "v": 2, "files": {}}
    files = cache.setdefault("files", {})
    seen = set()
    findings: list[tuple[str, list[str]]] = []
    n = 0
    for p in engine.iter_vault_notes(vault):
        n += 1
        key = str(p)
        seen.add(key)
        try:
            raw = p.read_bytes()
        except OSError as exc:
            findings.append((engine.rel(p, vault), [f"PATH-READ: 읽기 실패: {exc}"]))
            files.pop(key, None)
            continue
        sig = hashlib.sha256(raw).hexdigest()
        entry = files.get(key)
        if isinstance(entry, dict) and entry.get("sig") == sig and isinstance(entry.get("issues"), list):
            if entry["issues"]:
                findings.append((engine.rel(p, vault), entry["issues"]))
            continue
        try:
            info = _classify_bytes(engine, raw)
        except Exception as exc:  # 파일 하나의 예외가 감사 전체를 멈추지 않게, 그러나 보고한다
            findings.append((engine.rel(p, vault), [f"INTERNAL: 분류 중 예외: {type(exc).__name__}: {exc}"]))
            files.pop(key, None)
            continue
        issues: list[str] = []
        if info.kind == "paper":
            issues = [str(i) for i in engine.validate_paper(info.parsed) + list(info.encoding_issues)]
        elif info.kind in ("paper-broken", "error"):
            issues = [str(i) for i in list(info.issues) + list(info.encoding_issues)] or [f"{info.kind}: 사유 없음"]
        files[key] = {"sig": sig, "issues": issues}
        if issues:
            findings.append((engine.rel(p, vault), issues))
    for key in list(files):
        if key not in seen:
            del files[key]
    if use_cache:
        _save_cache(cache)
    return findings, n


def run_stop(payload: dict) -> int:
    if payload.get("stop_hook_active"):
        return 0
    vault = _vault_root()
    if not vault.is_dir():
        if os.environ.get("PAPER_VAULT_ROOT"):
            _log(f"PAPER_FRONTMATTER_HOOK_ERROR (Stop 감사 불가, fail-closed): PAPER_VAULT_ROOT가 디렉터리가 아니다: {vault}")
            return 2
        return 0  # 이 머신에 기본 vault가 없으면 감사할 대상이 없다 (설정하지 않은 환경)
    engine, err = load_engine()
    if engine is None:
        _log(f"PAPER_FRONTMATTER_HOOK_ERROR (Stop 감사 불가, fail-closed): {err}")
        return 2
    t0 = time.time()
    findings, n = audit_vault(engine, vault, use_cache=os.environ.get("PAPER_FRONTMATTER_NO_CACHE") != "1")
    if not findings:
        return 0
    lines = [f"PAPER_FRONTMATTER_AUDIT: vault 전체 감사에서 위반·판정불가 {len(findings)}건 (스캔 {n}개, {time.time()-t0:.1f}s)",
             "type: paper 노트는 정확히 13개 키만 가져야 한다: " + ", ".join(engine.PAPER_KEYS),
             "읽기/YAML 오류(판정 불가)도 함께 보고한다. 자동 수정은 하지 않는다. 각 파일을 고치거나 "
             "`paper_frontmatter.py fix --dry-run`으로 계획을 확인하라."]
    for r, issues in findings[:STOP_MAX_LIST]:
        lines.append(f"- {r}")
        for i in issues[:6]:
            lines.append(f"    · {i}")
        if len(issues) > 6:
            lines.append(f"    · … 외 {len(issues)-6}건")
    if len(findings) > STOP_MAX_LIST:
        lines.append(f"- … 외 {len(findings)-STOP_MAX_LIST}개 파일 (전체 목록: paper_frontmatter.py check --report-md)")
    _log("\n".join(lines))
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in ("pre", "post", "stop"):
        _log("usage: paper-frontmatter-hook.py pre|post|stop  (stdin: hook JSON)")
        return 2
    mode = argv[0]
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        # 입력이 없으면 검사할 것도 없다. 단, 깨진 JSON은 알린다.
        raw_err = f"{type(exc).__name__}: {exc}"
        if mode == "stop":
            payload = {}
        else:
            _log(f"PAPER_FRONTMATTER_HOOK: stdin JSON을 읽지 못했다 ({raw_err}) — 검사 없이 통과하지 않고 종료 코드 0으로 두되 기록한다")
            return 0
    if not isinstance(payload, dict):
        return 0
    try:
        if mode == "pre":
            return run_pre(payload)
        if mode == "post":
            return run_post(payload)
        return run_stop(payload)
    except Exception as exc:  # 예기치 못한 예외도 조용히 통과시키지 않는다
        _log(f"PAPER_FRONTMATTER_HOOK_ERROR ({mode}): {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

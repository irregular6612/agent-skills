"""Astra core review(astra-core.md) 9건 + 부모 추가 발견에 대한 회귀 테스트.

배포된 라이브 코드(~/.claude/hooks의 훅·설치기, 설정/기본 vault의 Public/_tools/paper_frontmatter.py)를 동적으로
로드한다. 원본은 corrected-core/test_core_corrections.py (2026-09-22)이며, 로더 경로 상수만 라이브 위치로 바꿨다.
실제 vault·~/.claude·settings.json에는 아무것도 쓰지 않는다:
  * vault = tmp_path 아래 합성 fixture (PAPER_VAULT_ROOT로 hook에 전달)
  * 엔진 = 라이브 vault의 Public/_tools/paper_frontmatter.py (PAPER_FRONTMATTER_TOOLS_DIR로 hook에 전달, 읽기 전용)
  * Stop 캐시 = tmp_path (hook.CACHE_PATH monkeypatch)
  * 설치기 = tmp settings 파일 + WRAPPER monkeypatch

실행:
  env PATH="$HOME/.local/bin:$PATH" uv run --with pytest --with pyyaml python -m pytest ~/.claude/hooks/tests -q -p no:cacheprovider
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr
from pathlib import Path

import pytest

# 로더 경로 상수 — 배포된 라이브 코드만 가리킨다 (스테이징/스냅샷 없음).
HOOKS_DIR = Path.home() / ".claude" / "hooks"
HOOK_PATH = HOOKS_DIR / "paper-frontmatter-hook.py"
INSTALLER_PATH = HOOKS_DIR / "install-paper-frontmatter-hooks.py"
# HERE = 설정된($PAPER_VAULT_ROOT) 또는 기본 vault의 Public/_tools. 엔진 로드와 fixture의 PAPER_FRONTMATTER_TOOLS_DIR에 쓴다.
_VAULT_ROOT = Path(os.environ["PAPER_VAULT_ROOT"]).expanduser() if os.environ.get("PAPER_VAULT_ROOT") else Path(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes")
HERE = _VAULT_ROOT / "Public" / "_tools"
ENGINE_PATH = HERE / "paper_frontmatter.py"
PY = sys.executable


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod  # dataclass가 모듈을 sys.modules에서 찾는다
    spec.loader.exec_module(mod)
    return mod


pf = _load("pf_live", ENGINE_PATH)
hook = _load("pf_hook_live", HOOK_PATH)
inst = _load("pf_installer_live", INSTALLER_PATH)
assert HERE == hook.DEFAULT_VAULT / "Public" / "_tools" or os.environ.get("PAPER_VAULT_ROOT"), "HERE는 훅의 기본 vault와 같아야 한다"

VALID = "---\ntype: paper\n" + "".join(f"{k}:\n" for k in pf.PAPER_KEYS[1:]) + "---\n# 제목\n\n본문\n"
VALID_EXTRA = VALID.replace("Lab:\n", "Lab:\nDOI: 10.1/x\n")


def w(path: Path, text: str | None = None, *, binary: bytes | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary is not None:
        path.write_bytes(binary)
    else:
        path.write_text(text or "", encoding="utf-8")
    return path


def codes(issues) -> set[str]:
    return {i.code if hasattr(i, "code") else i["code"] for i in issues}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def vault(tmp_path, monkeypatch):
    v = tmp_path / "vault with space"
    (v / "Public" / "AI" / "Papers").mkdir(parents=True)
    monkeypatch.setenv("PAPER_VAULT_ROOT", str(v))
    monkeypatch.setenv("PAPER_FRONTMATTER_TOOLS_DIR", str(HERE))
    monkeypatch.setattr(hook, "CACHE_PATH", tmp_path / "stop-cache.json")
    return v


def pre(path: Path, content: str | None = None, *, tool: str = "Write", **edit) -> tuple[int, str]:
    ti = {"file_path": str(path)}
    if tool == "Write":
        ti["content"] = content
    else:
        ti.update(edit)
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = hook.run_pre({"tool_name": tool, "tool_input": ti, "cwd": str(path.parent)})
    return rc, buf.getvalue()


def post(path: Path) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = hook.run_post({"tool_name": "Write", "tool_input": {"file_path": str(path)}})
    return rc, buf.getvalue()


def stop(payload: dict | None = None) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = hook.run_stop(payload or {})
    return rc, buf.getvalue()


def cli(vault: Path, *args, env: dict | None = None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([PY, str(ENGINE_PATH), "--vault", str(vault), *args], capture_output=True, text=True, env=e)


# ============================================================================
# #1 restore: manifest 경로 신뢰 금지 (탈출·절대·심볼릭 링크), 레코드 형식 검증
# ============================================================================

def _manifest(backup: Path, records: list) -> None:
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "manifest.jsonl").write_text(
        "\n".join(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


def test_1_restore_rejects_dotdot_escape_before_any_write(vault, tmp_path):
    backup = tmp_path / "bk"
    evil = b"pwned\n"
    w(backup / "outside.md", binary=evil)                      # = files/../outside.md
    _manifest(backup, [{"path": "../outside.md", "sha256_before": sha(evil), "sha256_after": sha(b"x")}])
    target = vault.parent / "outside.md"                         # = vault/../outside.md
    assert not target.exists()
    res, code = pf.run_restore(vault, backup, None, apply=True, force=True)
    assert code == 2 and res[0]["status"] == "error" and ".." in res[0]["message"]
    assert not target.exists()


def test_1_restore_rejects_absolute_paths_and_bad_record_types(vault, tmp_path):
    backup = tmp_path / "bk"
    _manifest(backup, [
        {"path": "/etc/passwd.md", "sha256_before": "0" * 64, "sha256_after": "0" * 64},
        {"path": 42, "sha256_before": "0" * 64, "sha256_after": "0" * 64},
        {"path": "Public/x.md", "sha256_before": "nothex", "sha256_after": "0" * 64},
        {"path": "Public/x.md"},
        "not json {",
        "[1, 2]",
        {"path": "Public/y.txt", "sha256_before": "0" * 64, "sha256_after": "0" * 64},
    ])
    res, code = pf.run_restore(vault, backup, None, apply=True, force=True)   # traceback 없이 보고
    assert code == 2 and len(res) == 7 and all(r["status"] == "error" for r in res)
    assert list(vault.rglob("*.md")) == []


def test_1_restore_rejects_symlink_components_on_both_sides(vault, tmp_path):
    good = VALID_EXTRA.encode()
    # (a) vault 목적지 쪽: Public/link → 외부 디렉터리
    ext = tmp_path / "ext"; ext.mkdir()
    (vault / "Public" / "link").symlink_to(ext)
    backup = tmp_path / "bk"
    w(backup / "files" / "Public" / "link" / "n.md", binary=good)
    _manifest(backup, [{"path": "Public/link/n.md", "sha256_before": sha(good), "sha256_after": sha(b"y")}])
    res, code = pf.run_restore(vault, backup, None, apply=True, force=True)
    assert code == 2 and res[0]["status"] == "error" and "심볼릭" in res[0]["message"]
    assert not (ext / "n.md").exists()
    # (b) 백업 원본 쪽: files/Public → 외부 디렉터리 (외부 내용을 vault로 끌어오지 않는다)
    backup2 = tmp_path / "bk2"
    ext2 = tmp_path / "ext2"; w(ext2 / "n.md", binary=good)
    (backup2 / "files").mkdir(parents=True)
    (backup2 / "files" / "Public").symlink_to(ext2)
    _manifest(backup2, [{"path": "Public/n.md", "sha256_before": sha(good), "sha256_after": sha(b"y")}])
    res, code = pf.run_restore(vault, backup2, None, apply=True, force=True)
    assert code == 2 and res[0]["status"] == "error" and "심볼릭" in res[0]["message"]
    assert not (vault / "Public" / "n.md").exists()


def test_1_legitimate_restore_still_works_including_deleted_note(vault, tmp_path):
    p = w(vault / "Public/AI/Papers/a.md", VALID_EXTRA)
    backup = tmp_path / "bk"
    outcomes, code = pf.run_fix(vault, None, apply=True, backup_dir=backup)
    assert code == 0 and outcomes[0].status == "changed"
    res, code = pf.run_restore(vault, backup, None, apply=True)
    assert code == 0 and res[0]["status"] == "restored" and p.read_text() == VALID_EXTRA
    # 노트가 삭제된 뒤에도 복원 가능 (force)
    pf.run_fix(vault, None, apply=True, backup_dir=backup)
    p.unlink()
    res, code = pf.run_restore(vault, backup, None, apply=True, force=True)
    assert res[0]["status"] == "restored" and p.read_text() == VALID_EXTRA
    r = cli(vault, "restore", "--backup-dir", str(backup))
    assert r.returncode == 0 and json.loads(r.stdout.splitlines()[0])["status"] == "already-restored"


# ============================================================================
# #2 미종결 frontmatter / CRLF / BOM — 조용한 no-frontmatter 금지
# ============================================================================

UNCLOSED_PAPER = "---\ntype: paper\nDOI: x\n"
UNCLOSED_NONPAPER = "---\ntype: concept\n"


def test_2_unclosed_frontmatter_is_not_absent_frontmatter(vault, tmp_path):
    info = pf.classify_text(UNCLOSED_PAPER)
    assert info.kind == "paper-broken" and codes(info.issues) == {"FM-UNCLOSED"}
    assert pf.classify_text(UNCLOSED_NONPAPER).kind == "error"
    assert pf.classify_text("# plain\n").kind == "no-frontmatter"
    assert pf.split_frontmatter_state(UNCLOSED_PAPER)[0] == pf.FM_UNCLOSED
    assert pf.split_frontmatter(UNCLOSED_PAPER) == (None, UNCLOSED_PAPER)  # 호환 API 유지

    p = w(vault / "Public/AI/Papers/u.md", UNCLOSED_PAPER)
    q = w(vault / "Public/AI/Papers/c.md", UNCLOSED_NONPAPER)
    res = pf.scan(vault)
    assert res.exit_code() == 1 and {i["path"] for i in res.invalid} == {"Public/AI/Papers/u.md"}  # 위반(1)이 오류(2)보다 우선
    assert {i["path"] for i in res.errors} == {"Public/AI/Papers/c.md"} and res.counts["no_frontmatter"] == 0
    assert pf.scan(vault, [q]).exit_code() == 2
    outcomes, code = pf.run_fix(vault, [p], apply=False, backup_dir=None)
    assert code == 1 and outcomes[0].status == "skipped" and codes(outcomes[0].issues) == {"FM-UNCLOSED"}
    # hook: 새 Write / Post / Stop 모두 놓치지 않는다
    assert pre(vault / "Public/AI/Papers/new.md", UNCLOSED_PAPER)[0] == 2
    assert post(p)[0] == 2
    rc, err = stop()
    assert rc == 2 and "u.md" in err and "c.md" in err


def test_2_crlf_and_bom_paper_are_classified_validated_and_not_migrated(vault, tmp_path):
    crlf_ok = VALID.replace("\n", "\r\n").encode()
    crlf_bad = VALID_EXTRA.replace("\n", "\r\n").encode()
    bom_bad = b"\xef\xbb\xbf" + VALID_EXTRA.encode()
    a = w(vault / "Public/AI/Papers/crlf-ok.md", binary=crlf_ok)
    b = w(vault / "Public/AI/Papers/crlf-bad.md", binary=crlf_bad)
    c = w(vault / "Public/AI/Papers/bom-bad.md", binary=bom_bad)
    for p in (a, b, c):
        assert pf.classify_file(p).kind == "paper"
    res = pf.scan(vault)
    by = {i["path"]: codes(i["issues"]) for i in res.invalid}
    assert res.exit_code() == 1 and res.counts["no_frontmatter"] == 0
    assert by["Public/AI/Papers/crlf-ok.md"] == {"ENC-CRLF"}
    assert by["Public/AI/Papers/crlf-bad.md"] == {"ENC-CRLF", "KEY-FORBIDDEN"}
    assert by["Public/AI/Papers/bom-bad.md"] == {"ENC-BOM", "KEY-FORBIDDEN"}
    outcomes, code = pf.run_fix(vault, None, apply=False, backup_dir=None)
    assert code == 1 and all(o.status == "skipped" for o in outcomes)
    # 텍스트 경로(hook 후보)에서도 BOM/CRLF는 인코딩 이슈로 잡힌다
    for text in (crlf_bad.decode(), bom_bad.decode("utf-8")):
        info = pf.classify_text(text)
        assert info.kind == "paper" and codes(info.encoding_issues) & {"ENC-CRLF", "ENC-BOM"}
        assert "KEY-FORBIDDEN" in codes(pf.validate_paper(info.parsed))
        assert pre(vault / "Public/AI/Papers/new.md", text)[0] == 2
    assert post(b)[0] == 2 and post(c)[0] == 2
    rc, err = stop()
    assert rc == 2 and "crlf-bad.md" in err and "bom-bad.md" in err
    assert not pf.plan_migration(crlf_bad.decode()).fixable   # enc 이슈를 안 넘겨도 텍스트에서 감지


# ============================================================================
# #3 YAML 의미 분류 vs 세그먼트 마이그레이션 지원 분리
# ============================================================================

QUOTED_PAPER_BAD = VALID_EXTRA.replace("type: paper", '"type": paper')
QUOTED_PAPER_OK = VALID.replace("type: paper", '"type": paper')
QUOTED_NONPAPER = '---\n"type": concept\nx: 1\n---\n# c\n'
BLOCK_TYPE = VALID.replace("type: paper", "type: |-\n  paper")
ANCHOR_NONPAPER = "---\ntype: concept\na: &x 1\nb: *x\n---\n"


def test_3_valid_quoted_key_and_anchor_nonpaper_are_not_blocked(vault):
    for text in (QUOTED_NONPAPER, ANCHOR_NONPAPER):
        info = pf.classify_text(text)
        assert info.kind == "nonpaper" and info.issues == [] and info.parsed.layout_issues
    q = w(vault / "Public/AI/Papers/q.md", QUOTED_NONPAPER)
    w(vault / "Public/AI/Papers/a.md", ANCHOR_NONPAPER)
    res = pf.scan(vault)
    assert res.exit_code() == 0 and res.counts["nonpaper"] == 2
    assert pre(vault / "Public/AI/Papers/new.md", QUOTED_NONPAPER)[0] == 0
    assert post(q)[0] == 0 and stop()[0] == 0
    assert cli(vault, "check", "--quiet").returncode == 0


def test_3_quoted_and_block_scalar_type_paper_remain_paper_candidates(vault, tmp_path):
    assert pf.classify_text(BLOCK_TYPE).kind == "paper" and pf.validate_paper(pf.classify_text(BLOCK_TYPE).parsed) == []
    info = pf.classify_text(QUOTED_PAPER_BAD)
    assert info.kind == "paper" and "KEY-FORBIDDEN" in codes(pf.validate_paper(info.parsed))
    # 새 Write / 기존 파일 Post / Stop / check / fix 어느 경로도 조용히 통과하지 않는다
    assert pre(vault / "Public/AI/Papers/new.md", QUOTED_PAPER_BAD)[0] == 2
    p = w(vault / "Public/AI/Papers/qp.md", QUOTED_PAPER_BAD)
    assert post(p)[0] == 2
    assert "qp.md" in stop()[1]
    assert cli(vault, "check", "--quiet").returncode == 1
    outcomes, code = pf.run_fix(vault, None, apply=False, backup_dir=None)
    assert code == 1 and outcomes[0].status == "skipped" and "YAML-LAYOUT" in codes(outcomes[0].issues)
    # 의미상 유효한 따옴표 키 paper는 통과(검증 OK), 마이그레이션은 필요 없음(unchanged)
    ok = w(vault / "Public/AI/Papers/qok.md", QUOTED_PAPER_OK)
    assert pf.validate_paper(pf.classify_file(ok).parsed) == [] and post(ok)[0] == 0
    outcomes, _ = pf.run_fix(vault, [ok], apply=False, backup_dir=None)
    assert outcomes[0].status == "unchanged"
    # 기존 quoted paper의 type 삭제는 차단
    rc, err = pre(ok, tool="Edit", old_string='"type": paper\n', new_string="")
    assert rc == 2 and "type을 제거" in err


def test_3_unknown_parse_errors_visible_nonzero_and_batch_continues(vault, tmp_path):
    w(vault / "Public/AI/Papers/ok.md", VALID)
    bad = w(vault / "Public/AI/Papers/bad.md", "---\ntype: concept\nx: [\n---\n")
    w(vault / "Public/AI/Papers/bin.md", binary=b"---\ntype: paper\n\xff\xfe\n---\n")
    res = pf.scan(vault)
    assert res.scanned == 3 and res.counts["error"] == 2 and res.exit_code() == 2
    assert {e["path"] for e in res.errors} == {"Public/AI/Papers/bad.md", "Public/AI/Papers/bin.md"}
    js = tmp_path / "r.json"
    r = cli(vault, "check", "--quiet", "--report-json", str(js))
    assert r.returncode == 2 and len(json.loads(js.read_text())["errors"]) == 2
    # hook: 해석 불가 새 내용은 차단, 기존 파일 Post·Stop도 보고
    assert pre(vault / "Public/AI/Papers/new.md", "---\ntype: concept\nx: [\n---\n")[0] == 2
    assert post(bad)[0] == 2
    rc, err = stop()
    assert rc == 2 and "bad.md" in err and "bin.md" in err


# ============================================================================
# #4 backup-dir 재사용 시 기존 백업 보존
# ============================================================================

def test_4_reused_backup_dir_never_overwrites_different_bytes(vault, tmp_path):
    p = w(vault / "Public/AI/Papers/a.md", VALID_EXTRA)
    backup = tmp_path / "bk"
    outcomes, code = pf.run_fix(vault, None, apply=True, backup_dir=backup)
    assert code == 0 and outcomes[0].status == "changed"
    first_backup = (backup / "files/Public/AI/Papers/a.md").read_bytes()
    first_manifest = (backup / "manifest.jsonl").read_bytes()
    assert first_backup == VALID_EXTRA.encode()
    # 사용자가 마이그레이션 결과에 다시 금지 키를 넣음 → 같은 backup-dir로 재시도
    edited = p.read_text().replace("Lab:\n", "Lab:\nDOI: again\n")
    p.write_text(edited, encoding="utf-8")
    outcomes, code = pf.run_fix(vault, None, apply=True, backup_dir=backup)
    assert code == 1 and outcomes[0].status == "backup-conflict" and codes(outcomes[0].issues) == {"BACKUP-CONFLICT"}
    assert p.read_text() == edited                                        # 노트 미변경
    assert (backup / "files/Public/AI/Papers/a.md").read_bytes() == first_backup   # 첫 백업 보존
    assert (backup / "manifest.jsonl").read_bytes() == first_manifest    # manifest 보존
    # 첫 백업으로 복원 가능 (--force)
    res, code = pf.run_restore(vault, backup, None, apply=True, force=True)
    assert res[0]["status"] == "restored" and p.read_text() == VALID_EXTRA
    # 새 backup-dir로는 정상 진행
    p.write_text(edited, encoding="utf-8")
    outcomes, code = pf.run_fix(vault, None, apply=True, backup_dir=tmp_path / "bk2")
    assert code == 0 and outcomes[0].status == "changed"


def test_4_astra_race_scenario_keeps_first_backup_recoverable(vault, tmp_path, monkeypatch):
    p = w(vault / "Public/AI/Papers/a.md", VALID_EXTRA)
    backup = tmp_path / "bk"
    pf.run_fix(vault, None, apply=True, backup_dir=backup)
    migrated = p.read_text()
    p.write_text(migrated.replace("Lab:\n", "Lab:\nDOI: again\n"), encoding="utf-8")
    real_backup = pf._backup_write

    def racy(backup_dir, rel_path, raw):
        dest = real_backup(backup_dir, rel_path, raw)
        p.write_text(migrated.replace("Comment:\n", "Comment: concurrent\n"), encoding="utf-8")
        return dest

    monkeypatch.setattr(pf, "_backup_write", racy)
    outcomes, code = pf.run_fix(vault, None, apply=True, backup_dir=backup)
    assert outcomes[0].status == "backup-conflict"
    monkeypatch.setattr(pf, "_backup_write", real_backup)
    res, code = pf.run_restore(vault, backup, None, apply=True, force=True)
    assert code == 0 and res[0]["status"] == "restored" and p.read_text() == VALID_EXTRA


def test_4_same_bytes_reuse_and_idempotent_rerun_still_allowed(vault, tmp_path):
    p = w(vault / "Public/AI/Papers/a.md", VALID_EXTRA)
    backup = tmp_path / "bk"
    pf.run_fix(vault, None, apply=True, backup_dir=backup)
    pf.run_restore(vault, backup, None, apply=True)
    outcomes, code = pf.run_fix(vault, None, apply=True, backup_dir=backup)   # 같은 원본 재백업 = 허용
    assert code == 0 and outcomes[0].status == "changed"
    outcomes, code = pf.run_fix(vault, None, apply=True, backup_dir=backup)
    assert code == 0 and outcomes[0].status == "unchanged"
    r = cli(vault, "fix", "--apply", "--backup-dir", str(backup), "--quiet")
    assert r.returncode == 0 and "재사용" in r.stderr


# ============================================================================
# #5 엔진/PyYAML 없음 → fail-closed (좁은 정규식으로 nonpaper 확정 금지)
# ============================================================================

MISSING_DEP_CASES = {
    "block-scalar": BLOCK_TYPE.replace("Lab:\n", "Lab:\nDOI: x\n"),
    "quoted-key": QUOTED_PAPER_BAD,
    "bom": "﻿" + VALID_EXTRA,
    "crlf": VALID_EXTRA.replace("\n", "\r\n"),
    "plain-fm-nonpaper": "---\ntype: concept\n---\n",   # 엔진 없이는 판정 불가 → 차단
}


def test_5_missing_engine_blocks_any_frontmatter_but_not_plain_md(vault, monkeypatch):
    monkeypatch.setattr(hook, "load_engine", lambda start=None: (None, "PyYAML 없음 (시뮬레이션)"))
    for name, text in MISSING_DEP_CASES.items():
        rc, err = pre(vault / "Public/AI/Papers/new.md", text)
        assert rc == 2 and "fail-closed" in err, name
    assert pre(vault / "Public/AI/Papers/plain.md", "# 제목\n\n본문\n")[0] == 0
    assert pre(vault / "Public/AI/Papers/plain.md", "본문에 --- 구분선\n---\n")[0] == 0
    # 기존 paper 파일의 Edit도 차단; 기존 파일 Post도 차단
    p = w(vault / "Public/AI/Papers/p.md", BLOCK_TYPE)
    assert pre(p, tool="Edit", old_string="Lab:\n", new_string="Lab:\nDOI: x\n")[0] == 2
    assert post(p)[0] == 2
    plain = w(vault / "Public/AI/Papers/plain.md", "# 제목\n")
    assert post(plain)[0] == 0
    assert stop()[0] == 2


def test_5_real_interpreter_without_pyyaml_blocks_block_scalar_paper(vault, tmp_path):
    """Astra 재현: python -S (site-packages 없음 → PyYAML 없음)에서 block-scalar paper의 잘못된 Write."""
    env = dict(os.environ, PAPER_VAULT_ROOT=str(vault), PAPER_FRONTMATTER_TOOLS_DIR=str(HERE))
    probe = subprocess.run([PY, "-S", "-c", "import yaml"], capture_output=True, env=env)
    if probe.returncode == 0:
        pytest.skip("python -S 에서도 PyYAML이 import 된다 — 의존성 부재를 재현할 수 없음")

    def run(text: str) -> subprocess.CompletedProcess:
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(vault / "Public/AI/Papers/n.md"), "content": text}}
        return subprocess.run([PY, "-S", str(HOOK_PATH), "pre"], input=json.dumps(payload), capture_output=True, text=True, env=env)

    for name, text in MISSING_DEP_CASES.items():
        r = run(text)
        assert r.returncode == 2 and "fail-closed" in r.stderr, (name, r.stderr)
    assert run("# plain\n").returncode == 0
    assert run(VALID_EXTRA).returncode == 2


# ============================================================================
# #6 Stop 감사: mtime+size 캐시 불신, stop_hook_active, 오류 보고
# ============================================================================

def test_6_stop_cache_uses_content_hash_not_mtime_size(vault, tmp_path):
    p = w(vault / "Public/AI/Papers/a.md", VALID)
    assert stop()[0] == 0                       # 캐시 생성 (유효)
    st = p.stat()
    p.write_text(VALID.replace("Lab:\n", "DOI:\n"), encoding="utf-8")   # 같은 크기
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))                    # 같은 mtime
    assert p.stat().st_size == st.st_size and p.stat().st_mtime_ns == st.st_mtime_ns
    rc, err = stop()
    assert rc == 2 and "KEY-MISSING" in err and "KEY-FORBIDDEN" in err
    engine, _ = hook.load_engine()
    findings, n = hook.audit_vault(engine, vault, use_cache=True)
    assert n == 1 and len(findings) == 1 and len(findings[0][1]) == 2


def test_6_stop_honors_active_guard_and_reports_read_and_parse_errors(vault, tmp_path, monkeypatch):
    w(vault / "Public/AI/Papers/bad.md", "---\ntype: concept\nx: [\n---\n")
    unreadable = w(vault / "Public/AI/Papers/bin.md", binary=b"---\n\xff\n---\n")
    assert stop({"stop_hook_active": True})[0] == 0
    rc, err = stop()
    assert rc == 2 and "bad.md" in err and "bin.md" in err and "판정불가" in err
    unreadable.chmod(0)
    try:
        rc, err = stop()
        assert rc == 2 and ("PATH-READ" in err or "bin.md" in err)
    finally:
        unreadable.chmod(0o644)
    monkeypatch.setenv("PAPER_VAULT_ROOT", str(tmp_path / "nope"))
    assert stop()[0] == 2                        # 설정된 vault가 없으면 조용히 0이 아니다


# ============================================================================
# #7 비해시 YAML 키 → 파일별 오류, 배치 계속
# ============================================================================

def test_7_unhashable_mapping_keys_are_per_file_errors(vault, tmp_path):
    texts = {
        "dictkey": "---\ntype: paper\n? {a: b}\n: value\n---\n",
        "listkey": "---\ntype: paper\n? [a, b]\n: value\n---\n",
        "nested": "---\ntype: concept\nk:\n  ? [x]\n  : y\n---\n",
        "flow": "---\ntype: paper\n{[a]: b}: c\n---\n",
    }
    for name, t in texts.items():
        info = pf.classify_text(t)                              # 예외 없음
        assert info.kind in ("paper-broken", "error"), name
        assert "YAML-BROKEN" in codes(info.issues), name
        w(vault / f"Public/AI/Papers/{name}.md", t)
    w(vault / "Public/AI/Papers/ok.md", VALID)
    res = pf.scan(vault)
    assert res.scanned == 5 and res.exit_code() == 1            # paper-broken 위반(1)이 오류(2)보다 우선
    assert len(res.invalid) == 3 and len(res.errors) == 1 and res.counts["paper_valid"] == 1
    assert pf.scan(vault, [vault / "Public/AI/Papers/nested.md"]).exit_code() == 2
    outcomes, code = pf.run_fix(vault, None, apply=False, backup_dir=None)
    assert code == 1 and [o.status for o in outcomes].count("skipped") == 3
    js = tmp_path / "r.json"
    assert cli(vault, "check", "--quiet", "--report-json", str(js)).returncode == 1
    data = json.loads(js.read_text())
    assert len(data["invalid"]) + len(data["errors"]) == 4


# ============================================================================
# #8 설치기: 빈 컨테이너 정규화, 무관 설정 보존, 멱등
# ============================================================================

SETTINGS_SAMPLES = [
    {},
    {"hooks": {}},
    {"hooks": {"PreToolUse": []}},
    {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo other"}]}]}},
    {"env": {"SECRET": "x"}, "permissions": {"allow": ["Bash"]},
     "hooks": {"Notification": [{"matcher": "", "hooks": [{"type": "command", "command": "notify"}]}],
               "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "other-stop"}]}]}},
]


@pytest.mark.parametrize("before", SETTINGS_SAMPLES)
def test_8_installer_preserves_unrelated_settings_and_is_idempotent(before):
    import copy
    snapshot = copy.deepcopy(before)
    after = inst.merge(before)
    assert before == snapshot                                   # 입력 불변
    assert inst.verify_preserved(before, after)
    assert inst.merge(after) == after                           # 멱등
    assert inst.verify_preserved(before, inst.merge(after))
    for event in ("PreToolUse", "PostToolUse", "Stop"):
        ours = [g for g in after["hooks"][event] if any(inst._is_ours(h) for h in g["hooks"])]
        assert len(ours) == 1
    # 무관 항목·최상위 키는 그대로
    for k, v in before.items():
        if k != "hooks":
            assert after[k] == v
    for event, groups in (before.get("hooks") or {}).items():
        others_before = [g for g in groups]
        others_after = [g for g in after["hooks"][event] if not any(inst._is_ours(h) for h in g.get("hooks", []))]
        assert others_before == others_after
    # uninstall → 원래와 (정규화 기준) 같다
    assert inst.verify_preserved(before, inst.strip_ours(after))
    assert inst._normalize_for_compare(inst.strip_ours(after)) == inst._normalize_for_compare(before)


def test_8_installer_cli_merge_dry_run_and_apply_on_tmp_settings(tmp_path, monkeypatch, capsys):
    wrapper = tmp_path / "paper-frontmatter-hook.sh"; wrapper.write_text("#!/bin/sh\n")
    monkeypatch.setattr(inst, "WRAPPER", wrapper)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(SETTINGS_SAMPLES[4]), encoding="utf-8")
    assert inst.main(["--merge-settings", "--dry-run", "--settings", str(settings)]) == 0
    assert json.loads(settings.read_text()) == SETTINGS_SAMPLES[4]
    assert inst.main(["--merge-settings", "--settings", str(settings)]) == 0
    written = json.loads(settings.read_text())
    assert written["env"] == {"SECRET": "x"} and inst.verify_preserved(SETTINGS_SAMPLES[4], written)
    assert inst.main(["--merge-settings", "--settings", str(settings)]) == 0     # 두 번째: 변경 없음
    assert json.loads(settings.read_text()) == written
    assert inst.main(["--verify", "--settings", str(settings)]) == 0
    assert inst.main(["--uninstall", "--settings", str(settings)]) == 0
    assert inst.verify_preserved(SETTINGS_SAMPLES[4], json.loads(settings.read_text()))
    out = capsys.readouterr().out
    assert "SECRET" not in out                                  # settings 내용을 통째로 출력하지 않는다
    # 처음 설치(빈 파일 없음)도 성공
    fresh = tmp_path / "fresh.json"
    assert inst.main(["--merge-settings", "--settings", str(fresh)]) == 0 and fresh.exists()


# ============================================================================
# #9 classify 종료 코드
# ============================================================================

def test_9_classify_exit_codes(vault, monkeypatch):
    w(vault / "Public/AI/Papers/ok.md", VALID)
    w(vault / "Public/AI/Papers/bad.md", VALID_EXTRA)
    w(vault / "Public/AI/Papers/broken.md", "---\ntype: paper\nx: [\n---\n")
    w(vault / "Public/AI/Papers/err.md", "---\ntype: concept\nx: [\n---\n")
    w(vault / "Public/AI/Papers/concept.md", "---\ntype: concept\n---\n")
    w(vault / "Public/AI/Papers/unclosed.md", UNCLOSED_PAPER)
    monkeypatch.chdir(vault)
    expect = {"ok.md": 0, "concept.md": 0, "bad.md": 1, "broken.md": 1, "unclosed.md": 1, "err.md": 2}
    for name, rc in expect.items():
        r = cli(vault, "classify", f"Public/AI/Papers/{name}")
        assert r.returncode == rc, (name, r.stdout, r.stderr)
        assert json.loads(r.stdout)["kind"]


# ============================================================================
# 부모 추가 발견: 엔진 고정(상위 디렉터리 탐색 금지), vault 범위, 심볼릭 링크
# ============================================================================

def test_engine_is_pinned_and_untrusted_ancestor_engine_never_executes(vault, tmp_path, monkeypatch):
    project = tmp_path / "untrusted-project"
    marker = tmp_path / "PWNED"
    w(project / "Public" / "_tools" / "paper_frontmatter.py",
      f"from pathlib import Path\nPath({str(marker)!r}).write_text('x')\nPAPER_KEYS=()\ndef _yaml_available(): return True\n")
    note = project / "Public" / "AI" / "Papers" / "n.md"
    # (a) vault 밖 파일: 검사하지 않고 통과, 상위 엔진도 실행하지 않는다
    assert pre(note, VALID_EXTRA)[0] == 0 and not marker.exists()
    w(note, VALID_EXTRA)
    assert post(note)[0] == 0 and not marker.exists()
    assert hook.find_engine(note) == HERE / "paper_frontmatter.py"
    # (b) 명시 override 없음 → 설정된 vault의 Public/_tools만 본다 (없으면 None; 상위 탐색 없음)
    monkeypatch.delenv("PAPER_FRONTMATTER_TOOLS_DIR")
    assert hook.find_engine(note) is None and not marker.exists()
    (vault / "Public" / "_tools").mkdir(parents=True)
    (vault / "Public" / "_tools" / "paper_frontmatter.py").write_bytes(ENGINE_PATH.read_bytes())
    assert hook.find_engine(note) == vault / "Public" / "_tools" / "paper_frontmatter.py"
    assert not marker.exists()


def test_hook_scope_is_configured_vault_and_symlink_escapes_are_rejected(vault, tmp_path):
    outside = w(tmp_path / "elsewhere" / "n.md", VALID_EXTRA)
    assert pre(outside, VALID_EXTRA)[0] == 0 and post(outside)[0] == 0
    # vault 안 상대 경로(cwd 기준) + `..` 정리
    inside_rel = Path("Public/AI/Papers/../Papers/new.md")
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = hook.run_pre({"tool_name": "Write", "tool_input": {"file_path": str(inside_rel), "content": VALID_EXTRA}, "cwd": str(vault)})
    assert rc == 2
    # `..`로 vault 밖으로 나가는 경로는 vault 밖 = 범위 밖
    with redirect_stderr(buf):
        rc = hook.run_pre({"tool_name": "Write", "tool_input": {"file_path": str(vault / "Public" / ".." / ".." / "x.md"), "content": VALID_EXTRA}, "cwd": str(vault)})
    assert rc == 0
    # vault 안 심볼릭 링크(파일·디렉터리) → 차단 (외부 대상을 읽거나 바꾸지 않는다)
    ext = w(tmp_path / "ext" / "target.md", VALID_EXTRA)
    link = vault / "Public/AI/Papers/link.md"; link.symlink_to(ext)
    ldir = vault / "Public/linked"; ldir.symlink_to(tmp_path / "ext")
    for p in (link, ldir / "target.md"):
        rc, err = pre(p, VALID)
        assert rc == 2 and "심볼릭" in err
        rc, err = post(p)
        assert rc == 2 and "심볼릭" in err
    assert ext.read_text() == VALID_EXTRA


# ============================================================================
# 계약 유지: 13키·값 보존·본문 보존·멱등 (부모 731 리허설과 같은 성질을 합성 fixture로)
# ============================================================================

def test_contract_migration_preserves_segments_body_and_is_idempotent(vault, tmp_path):
    text = (
        "---\n"
        "title: T\n"
        "Reading-Status:\n  - ▶️ In progress\n"
        "Author: [A, B]\n"
        "Comment: |\n  여러 줄\n  코멘트\n"
        "Review-Date: 2026-09-22\n"
        "Published Year: 2024\n"
        "linked-bases:\n- '[[X.base]]'\n"
        "DOI: 10.1/x\n"
        "isTargetPaper: true\n"
        "type: paper\n"
        "---\n"
        "body line\r\n?? no — LF only\n\n---\nnot frontmatter\n"
    ).replace("\r\n", "\n")
    p = w(vault / "Public/AI/Papers/a.md", text)
    old = pf.parse_note(text)
    outcomes, code = pf.run_fix(vault, None, apply=True, backup_dir=tmp_path / "bk")
    assert code == 0 and outcomes[0].status == "changed"
    new = pf.parse_note(p.read_text())
    assert new.keys == list(pf.PAPER_KEYS) and new.body == old.body
    for k in old.keys:
        if k in pf.PAPER_KEY_SET:
            assert new.segment(k) == old.segment(k)
    assert new.data["Published Year"] == 2024 and new.data["Author"] == ["A", "B"]
    assert new.data["URL"] is None and new.data["Category"] is None      # 추론 없음, 빈 값
    assert pf.validate_paper(new) == []
    rec = json.loads((tmp_path / "bk/manifest.jsonl").read_text().splitlines()[0])
    assert set(rec["removed"]) == {"title", "DOI", "isTargetPaper"}
    again, code = pf.run_fix(vault, None, apply=True, backup_dir=tmp_path / "bk")
    assert code == 0 and again[0].status == "unchanged"

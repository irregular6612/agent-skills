"""paper-frontmatter-hook.py / install-paper-frontmatter-hooks.py 테스트.

엔진은 실제 vault의 Public/_tools/paper_frontmatter.py를 tmp vault에 복사해 쓴다 (walk-up 탐색 검증).
"""
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


hook = _load("paper_frontmatter_hook", HOOKS / "paper-frontmatter-hook.py")
installer = _load("paper_frontmatter_installer", HOOKS / "install-paper-frontmatter-hooks.py")
ENGINE_SRC = hook.DEFAULT_VAULT / hook.ENGINE_REL
pytestmark = pytest.mark.skipif(not ENGINE_SRC.exists(), reason="엔진(vault Public/_tools/paper_frontmatter.py) 없음")

VALID = (
    "---\ntype: paper\nReading-Status:\nRead-Depth:\nAuthor: A\nJournal/Conference: V\nPublished Year: 2026\n"
    "Topic: t\nReview-Date: 2026-09-22\nComment: c\nURL: https://example.com/p\nCategory:\nlinked-bases:\nLab:\n---\n# T\n\nbody\n"
)


@pytest.fixture
def vault(tmp_path, monkeypatch):
    v = tmp_path / "vault"
    (v / "Public" / "AI" / "Papers").mkdir(parents=True)
    (v / "Public" / "_tools").mkdir()
    shutil.copy(ENGINE_SRC, v / "Public" / "_tools" / "paper_frontmatter.py")
    monkeypatch.setenv("PAPER_VAULT_ROOT", str(v))
    monkeypatch.delenv("PAPER_FRONTMATTER_TOOLS_DIR", raising=False)
    monkeypatch.setenv("PAPER_FRONTMATTER_NO_CACHE", "1")
    monkeypatch.setattr(hook, "CACHE_PATH", tmp_path / "cache.json")
    return v


def run(mode, payload, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    rc = hook.main([mode])
    return rc, capsys.readouterr().err


def write_payload(path, content, tool="Write"):
    return {"tool_name": tool, "tool_input": {"file_path": str(path), "content": content}, "cwd": str(path.parent)}


def edit_payload(path, old, new, replace_all=False):
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path), "old_string": old, "new_string": new, "replace_all": replace_all}}


# --- PreToolUse --------------------------------------------------------------

def test_pre_denies_invalid_write_and_allows_valid(vault, monkeypatch, capsys):
    p = vault / "Public/AI/Papers/new.md"
    rc, err = run("pre", write_payload(p, VALID.replace("Lab:\n", "Lab:\nDOI: N/A\n")), monkeypatch, capsys)
    assert rc == 2 and "KEY-FORBIDDEN" in err and "DOI" in err
    rc, err = run("pre", write_payload(p, VALID), monkeypatch, capsys)
    assert rc == 0 and err == ""
    assert not p.exists()  # pre 훅은 아무것도 쓰지 않는다


def test_pre_blank_fields_valid_but_missing_key_denied(vault, monkeypatch, capsys):
    p = vault / "Public/AI/Papers/new.md"
    rc, _ = run("pre", write_payload(p, VALID.replace("Author: A\n", "Author:\n")), monkeypatch, capsys)
    assert rc == 0
    rc, err = run("pre", write_payload(p, VALID.replace("Read-Depth:\n", "")), monkeypatch, capsys)
    assert rc == 2 and "KEY-MISSING" in err and "Read-Depth" in err


def test_pre_nonpaper_and_non_md_pass_even_under_papers(vault, monkeypatch, capsys):
    p = vault / "Public/AI/Papers/concept.md"
    rc, _ = run("pre", write_payload(p, "---\ntype: concept\nDOI: x\nfoo: bar\n---\n# c\n"), monkeypatch, capsys)
    assert rc == 0
    rc, _ = run("pre", write_payload(p, "# no frontmatter\n"), monkeypatch, capsys)
    assert rc == 0
    rc, _ = run("pre", write_payload(vault / "Public/AI/Papers/data.json", '{"type": "paper"}'), monkeypatch, capsys)
    assert rc == 0
    rc, _ = run("pre", {"tool_name": "Bash", "tool_input": {"command": "echo"}}, monkeypatch, capsys)
    assert rc == 0


def test_pre_edit_computes_result_including_replace_all_and_repeats(vault, monkeypatch, capsys):
    p = vault / "Public/AI/Papers/a.md"
    p.write_text(VALID + "note c\nnote c\n", encoding="utf-8")
    rc, _ = run("pre", edit_payload(p, "Author: A", "Author: B"), monkeypatch, capsys)
    assert rc == 0
    rc, err = run("pre", edit_payload(p, "Lab:\n", "Lab:\nisTargetPaper: true\n"), monkeypatch, capsys)
    assert rc == 2 and "isTargetPaper" in err
    # 반복 문자열: replace_all 없이 → 도구가 실패할 편집이므로 훅은 통과(도구 오류가 알린다)
    rc, _ = run("pre", edit_payload(p, "note c", "note d"), monkeypatch, capsys)
    assert rc == 0
    # replace_all로 frontmatter의 키를 여러 번 바꾸는 경우까지 계산한다
    p.write_text(VALID.replace("Comment: c\n", "Comment: c\n"), encoding="utf-8")
    rc, err = run("pre", edit_payload(p, ":\n", ":\nDOI: x\n", replace_all=True), monkeypatch, capsys)
    assert rc == 2 and "DOI" in err
    # MultiEdit
    payload = {"tool_name": "MultiEdit", "tool_input": {"file_path": str(p), "edits": [
        {"old_string": "Author: A", "new_string": "Author: Z"},
        {"old_string": "Lab:\n", "new_string": "Lab:\nBenchmark-Type: x\n"}]}}
    rc, err = run("pre", payload, monkeypatch, capsys)
    assert rc == 2 and "Benchmark-Type" in err


def test_pre_blocks_type_removal_or_change_on_known_paper(vault, monkeypatch, capsys):
    p = vault / "Public/AI/Papers/a.md"
    p.write_text(VALID, encoding="utf-8")
    rc, err = run("pre", edit_payload(p, "type: paper\n", ""), monkeypatch, capsys)
    assert rc == 2 and "type" in err
    rc, err = run("pre", edit_payload(p, "type: paper", "type: concept"), monkeypatch, capsys)
    assert rc == 2
    rc, err = run("pre", write_payload(p, "# rewritten without frontmatter\n"), monkeypatch, capsys)
    assert rc == 2
    # 기존 파일이 (아직 마이그레이션 안 된) paper라도 type을 유지하면 새 내용으로 판단한다
    p.write_text(VALID.replace("Lab:\n", "Lab:\nDOI: x\n"), encoding="utf-8")
    rc, _ = run("pre", write_payload(p, VALID), monkeypatch, capsys)
    assert rc == 0


def test_pre_relative_path_uses_cwd(vault, monkeypatch, capsys):
    payload = {"tool_name": "Write", "tool_input": {"file_path": "Public/AI/Papers/r.md", "content": VALID.replace("Lab:\n", "Lab:\nx: 1\n")}, "cwd": str(vault)}
    rc, err = run("pre", payload, monkeypatch, capsys)
    assert rc == 2 and "x" in err


# 엔진/PyYAML 없이 좁은 정규식으로 "paper가 아니다"를 확정할 수 없는 후보들. 여는 `---`가 있으면 전부 차단 대상.
MISSING_DEP_CANDIDATES = {
    "plain-paper": VALID,
    "paper-with-extra-key": VALID.replace("Lab:\n", "Lab:\nDOI: x\n"),
    "quoted-type-key": VALID.replace("type: paper", '"type": paper'),
    "block-scalar-type": VALID.replace("type: paper", "type: |-\n  paper"),
    "bom": "\ufeff" + VALID,
    "crlf": VALID.replace("\n", "\r\n"),
    "concept-frontmatter": "---\ntype: concept\n---\n# c\n",   # 분류 불가 → nonpaper라고 단정하지 않는다
}


def test_fail_closed_when_engine_or_yaml_missing(vault, monkeypatch, capsys, tmp_path):
    # (a) 설정된 vault 루트가 존재하지 않음: vault 밖 파일은 검사 범위가 아니므로 개입하지 않는다 (엔진 탐색도 없음)
    monkeypatch.setenv("PAPER_VAULT_ROOT", str(tmp_path / "nowhere"))
    monkeypatch.setenv("PAPER_FRONTMATTER_TOOLS_DIR", str(tmp_path / "nowhere"))
    p = tmp_path / "loose" / "paper.md"
    rc, err = run("pre", write_payload(p, VALID.replace("Lab:\n", "Lab:\nDOI: x\n")), monkeypatch, capsys)
    assert rc == 0 and err == ""
    rc, err = run("pre", write_payload(p, "---\ntype: concept\n---\n# c\n"), monkeypatch, capsys)
    assert rc == 0 and err == ""
    # 명시적으로 설정된 vault가 디렉터리가 아니면 Stop 감사는 조용히 0이 아니라 fail-closed
    rc, err = run("stop", {}, monkeypatch, capsys)
    assert rc == 2 and "HOOK_ERROR" in err and "PAPER_VAULT_ROOT" in err
    # (b) vault 안 + 의존성 없음: frontmatter 여는 줄이 있는 후보는 종류를 가리지 않고 전부 차단
    monkeypatch.setenv("PAPER_VAULT_ROOT", str(vault))
    monkeypatch.delenv("PAPER_FRONTMATTER_TOOLS_DIR")
    monkeypatch.setattr(hook, "load_engine", lambda start=None: (None, "PyYAML 없음"))
    target = vault / "Public/AI/Papers/a.md"
    for name, text in MISSING_DEP_CANDIDATES.items():
        rc, err = run("pre", write_payload(target, text), monkeypatch, capsys)
        assert rc == 2 and "PyYAML" in err and "fail-closed" in err, name
        assert not target.exists(), name
    # frontmatter가 전혀 없는 평범한 .md만 통과한다 (본문 중간의 `---` 구분선은 frontmatter가 아니다)
    rc, err = run("pre", write_payload(target, "# plain\n\nbody\n---\nrule\n"), monkeypatch, capsys)
    assert rc == 0 and err == ""
    # 기존 paper 파일의 Edit·PostToolUse·Stop도 같은 규칙으로 차단
    target.write_text(VALID, encoding="utf-8")
    rc, err = run("pre", edit_payload(target, "Author: A", "Author: B"), monkeypatch, capsys)
    assert rc == 2 and "PyYAML" in err
    rc, err = run("post", {"tool_name": "Write", "tool_input": {"file_path": str(target)}}, monkeypatch, capsys)
    assert rc == 2 and "PyYAML" in err
    plain = vault / "Public/AI/Papers/plain.md"
    plain.write_text("# plain\n", encoding="utf-8")
    rc, err = run("post", {"tool_name": "Write", "tool_input": {"file_path": str(plain)}}, monkeypatch, capsys)
    assert rc == 0 and err == ""
    rc, err = run("stop", {}, monkeypatch, capsys)
    assert rc == 2 and "PyYAML" in err


# --- PostToolUse -------------------------------------------------------------

def test_post_reports_actual_file_state(vault, monkeypatch, capsys):
    p = vault / "Public/AI/Papers/a.md"
    p.write_text(VALID.replace("Lab:\n", "Lab:\nDOI: x\n"), encoding="utf-8")
    rc, err = run("post", {"tool_name": "Edit", "tool_input": {"file_path": str(p)}}, monkeypatch, capsys)
    assert rc == 2 and "PostToolUse" in err and "DOI" in err
    p.write_text(VALID, encoding="utf-8")
    rc, err = run("post", {"tool_name": "Write", "tool_input": {"file_path": str(p)}}, monkeypatch, capsys)
    assert rc == 0
    rc, _ = run("post", {"tool_name": "Write", "tool_input": {"file_path": str(vault / "gone.md")}}, monkeypatch, capsys)
    assert rc == 0


# --- Stop --------------------------------------------------------------------

def test_stop_audits_whole_vault_honours_stop_hook_active_and_never_fixes(vault, monkeypatch, capsys):
    good = vault / "Public/AI/Papers/good.md"
    good.write_text(VALID, encoding="utf-8")
    rc, err = run("stop", {}, monkeypatch, capsys)
    assert rc == 0 and err == ""
    bad = vault / "Research Ideas" / "bash written.md"
    bad.parent.mkdir()
    before = VALID.replace("Lab:\n", "Lab:\narXiv-ID: 1\n")
    bad.write_text(before, encoding="utf-8")
    concept = vault / "Public/AI/Papers/concept.md"
    concept_before = "---\ntype: concept\nx: [\n---\n"
    concept.write_text(concept_before, encoding="utf-8")
    rc, err = run("stop", {}, monkeypatch, capsys)
    assert rc == 2 and "bash written.md" in err and "arXiv-ID" in err
    # 깨진 YAML은 nonpaper를 입증할 수 없으므로 조용히 건너뛰지 않고 판정불가로 보고한다
    assert "concept.md" in err and "YAML-BROKEN" in err and "판정불가" in err
    assert bad.read_text(encoding="utf-8") == before  # 자동 수정 없음
    assert concept.read_text(encoding="utf-8") == concept_before
    rc, err = run("stop", {"stop_hook_active": True}, monkeypatch, capsys)
    assert rc == 0 and err == ""


def test_stop_cache_invalidates_on_change(vault, monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("PAPER_FRONTMATTER_NO_CACHE")
    p = vault / "Public/AI/Papers/a.md"
    p.write_text(VALID, encoding="utf-8")
    assert run("stop", {}, monkeypatch, capsys)[0] == 0
    p.write_text(VALID.replace("Lab:\n", "Lab:\nDOI: x\n"), encoding="utf-8")
    os.utime(p, (1, 1))  # mtime을 과거로 두어도 size가 달라 재검사한다
    assert run("stop", {}, monkeypatch, capsys)[0] == 2
    p.write_text(VALID, encoding="utf-8")
    assert run("stop", {}, monkeypatch, capsys)[0] == 0
    assert (tmp_path / "cache.json").exists()


# --- wrapper (실제 인터프리터 선택 경로) ------------------------------------------

def test_wrapper_selects_interpreter_with_yaml_and_forwards_exit_code(vault):
    p = vault / "Public/AI/Papers/a.md"
    payload = json.dumps(write_payload(p, VALID.replace("Lab:\n", "Lab:\nDOI: x\n")))
    env = {**os.environ, "PAPER_VAULT_ROOT": str(vault)}
    r = subprocess.run(["bash", str(HOOKS / "paper-frontmatter-hook.sh"), "pre"], input=payload, capture_output=True, text=True, env=env)
    assert r.returncode == 2 and "DOI" in r.stderr
    r = subprocess.run(["bash", str(HOOKS / "paper-frontmatter-hook.sh"), "pre"], input=json.dumps(write_payload(p, VALID)), capture_output=True, text=True, env=env)
    assert r.returncode == 0


# --- installer ---------------------------------------------------------------

@pytest.fixture
def settings(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps({
        "permissions": {"allow": ["Bash(ls:*)"]},
        "secretish": "do-not-print",
        "hooks": {
            "PreToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "/x/cc-status"}]}],
            "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "bash /x/cursor-notify.sh stop", "timeout": 10}]},
                     {"matcher": "", "hooks": [{"type": "command", "command": "/x/agentcat --event Stop"}]}],
            "SessionStart": [{"hooks": [{"type": "command", "command": "/x/cleanup"}]}],
        },
    }, indent=2), encoding="utf-8")
    return s


def _has_ours(settings_obj):
    hooks = settings_obj.get("hooks") if isinstance(settings_obj.get("hooks"), dict) else {}
    return any(installer._is_ours(h) for groups in hooks.values() if isinstance(groups, list)
               for g in groups if isinstance(g, dict) for h in (g.get("hooks") or []))


def test_installer_merges_idempotently_preserves_others_and_uninstalls(settings, capsys):
    original = json.loads(settings.read_text())
    assert installer.main(["--merge-settings", "--dry-run", "--settings", str(settings)]) == 0
    assert json.loads(settings.read_text()) == original
    out = capsys.readouterr().out
    assert "do-not-print" not in out and "cc-status" not in out
    assert installer.main(["--merge-settings", "--settings", str(settings)]) == 0
    merged = json.loads(settings.read_text())
    assert installer.strip_ours(original) == original  # 원본에는 우리 항목이 없다
    assert installer.verify_preserved(original, merged)  # 우리 항목·빈 컨테이너를 뺀 나머지는 동일
    assert not _has_ours(installer.strip_ours(merged))
    assert {e for e in merged["hooks"]} >= {"PreToolUse", "PostToolUse", "Stop", "SessionStart"}
    pre = [g for g in merged["hooks"]["PreToolUse"] if any("paper-frontmatter-hook.sh" in h["command"] for h in g["hooks"])]
    assert pre[0]["matcher"] == "Write|Edit|MultiEdit" and pre[0]["hooks"][0]["command"].endswith('" pre')
    assert len(list(settings.parent.glob("settings.json.bak-*"))) == 1
    assert installer.main(["--merge-settings", "--settings", str(settings)]) == 0
    assert json.loads(settings.read_text()) == merged
    assert len(list(settings.parent.glob("settings.json.bak-*"))) == 1  # 변경 없으면 백업도 없음
    assert installer.main(["--verify", "--settings", str(settings)]) == 0
    assert installer.main(["--uninstall", "--settings", str(settings)]) == 0
    restored = json.loads(settings.read_text())
    # strip_ours는 원본의 빈 이벤트 컨테이너를 보존하므로, 병합 때 새로 생긴 PostToolUse는 빈 리스트로 남을 수 있다.
    # 원시 dict 동등 대신: 정규화 기준 보존 + 우리 항목 없음 + 사용자 설정 원문 그대로.
    assert installer.verify_preserved(original, restored)
    assert not _has_ours(restored)
    assert restored.get("hooks", {}).get("PostToolUse", []) == []
    assert restored["permissions"] == original["permissions"] and restored["secretish"] == original["secretish"]
    for event in ("PreToolUse", "Stop", "SessionStart"):
        assert restored["hooks"][event] == original["hooks"][event]
    assert installer.main(["--verify", "--settings", str(settings)]) == 1


def test_installer_refuses_when_hooks_shape_is_unexpected(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text(json.dumps({"hooks": {"PreToolUse": {"not": "a list"}}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        installer.main(["--merge-settings", "--settings", str(s)])
    assert json.loads(s.read_text()) == {"hooks": {"PreToolUse": {"not": "a list"}}}

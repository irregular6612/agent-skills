"""paper-format-validator.py 통합 회귀: 엔진은 신뢰 위치에서만 로드한다.

검사 대상 노트의 상위 디렉터리에 있는 Public/_tools/paper_frontmatter.py는
절대 import하지 않는다 (임의 저장소 코드 실행 방지).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "paper-format-validator.py"
spec = importlib.util.spec_from_file_location("paper_format_validator_integration", MODULE_PATH)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

UNTRUSTED_ENGINE = '''\
from pathlib import Path
Path(__file__).with_name("EXECUTED-UNTRUSTED").write_text("pwned")
PAPER_KEYS = ("type",)
def _yaml_available():
    return True
'''

PAPER_NOTE = "---\ntype: paper\n---\n# x\n"


@pytest.fixture
def untrusted_repo(tmp_path):
    """노트 상위에 악성 엔진이 놓인 '다른 저장소'."""
    repo = tmp_path / "other-repo"
    tools = repo / "Public" / "_tools"
    tools.mkdir(parents=True)
    (tools / "paper_frontmatter.py").write_text(UNTRUSTED_ENGINE, encoding="utf-8")
    note = repo / "Public" / "AI" / "Papers" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text(PAPER_NOTE, encoding="utf-8")
    return repo, note, tools / "EXECUTED-UNTRUSTED"


@pytest.fixture
def fresh_engine_state(monkeypatch):
    """캐시된 엔진과 sys.modules 단축 경로를 비워 실제 탐색이 일어나게 한다."""
    monkeypatch.setattr(validator, "_ENGINE", None)
    monkeypatch.setattr(validator, "_ENGINE_ERROR", None)
    monkeypatch.delitem(sys.modules, "paper_frontmatter", raising=False)
    monkeypatch.delenv("PAPER_FRONTMATTER_TOOLS_DIR", raising=False)
    monkeypatch.delenv("PAPER_VAULT_ROOT", raising=False)


def test_find_engine_ignores_note_ancestors(untrusted_repo, fresh_engine_state, monkeypatch, tmp_path):
    repo, note, sentinel = untrusted_repo
    monkeypatch.setenv("PAPER_VAULT_ROOT", str(tmp_path / "no-such-vault"))
    assert validator.find_engine(note) is None
    assert validator.find_engine(note.parent) is None
    assert validator.find_engine(repo) is None
    assert not sentinel.exists()


def test_load_engine_is_fail_closed_without_trusted_engine(untrusted_repo, fresh_engine_state, monkeypatch, tmp_path):
    repo, note, sentinel = untrusted_repo
    monkeypatch.setenv("PAPER_VAULT_ROOT", str(tmp_path / "no-such-vault"))
    engine, err = validator.load_engine(note)
    assert engine is None
    assert "PAPER_FRONTMATTER_TOOLS_DIR" in err
    assert not sentinel.exists(), "상위 디렉터리의 엔진 코드가 실행됐다"
    res = validator.validate_note(note, cli=True)
    assert any("fail-closed" in v for v in res.violations)
    assert not sentinel.exists()


def test_explicit_tools_dir_wins_over_configured_vault(fresh_engine_state, monkeypatch, tmp_path):
    trusted = tmp_path / "trusted-tools"
    trusted.mkdir()
    (trusted / "paper_frontmatter.py").write_text("PAPER_KEYS = ()\n", encoding="utf-8")
    vault = tmp_path / "vault"
    vtools = vault / "Public" / "_tools"
    vtools.mkdir(parents=True)
    (vtools / "paper_frontmatter.py").write_text("PAPER_KEYS = ()\n", encoding="utf-8")

    monkeypatch.setenv("PAPER_VAULT_ROOT", str(vault))
    assert validator.find_engine() == vtools / "paper_frontmatter.py"
    monkeypatch.setenv("PAPER_FRONTMATTER_TOOLS_DIR", str(trusted))
    assert validator.find_engine() == trusted / "paper_frontmatter.py"
    # start 인자는 어떤 값이든 결과를 바꾸지 않는다
    assert validator.find_engine(tmp_path / "elsewhere" / "n.md") == trusted / "paper_frontmatter.py"


def test_configured_vault_engine_is_used_for_notes_outside_it(untrusted_repo, fresh_engine_state, monkeypatch, tmp_path):
    """노트가 다른 저장소 안에 있어도 설정된 vault의 엔진만 후보다."""
    repo, note, sentinel = untrusted_repo
    vault = tmp_path / "vault"
    vtools = vault / "Public" / "_tools"
    vtools.mkdir(parents=True)
    (vtools / "paper_frontmatter.py").write_text("PAPER_KEYS = ()\n", encoding="utf-8")
    monkeypatch.setenv("PAPER_VAULT_ROOT", str(vault))
    assert validator.find_engine(note) == vtools / "paper_frontmatter.py"
    assert not sentinel.exists()

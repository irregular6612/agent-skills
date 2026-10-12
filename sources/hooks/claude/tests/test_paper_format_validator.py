"""paper-format-validator.py 테스트 (schema v4: 13키 frontmatter + DRILLER:meta 본문 블록)."""
import importlib.util
import io
import json
import os
import shutil
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "paper-format-validator.py"
spec = importlib.util.spec_from_file_location("paper_format_validator", MODULE_PATH)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

REAL_GENERAL_TEMPLATE = validator.TEMPLATES_DIR / "general-v1.md"
GENERAL_H2 = ["개요", "배경과 문제", "지표", "방법과 벤치마크 구성", "주요 결과", "Take-home", "본문 도표"]
ENGINE_OK = validator.load_engine()[0] is not None
pytestmark = pytest.mark.skipif(not ENGINE_OK, reason="frontmatter 엔진(vault Public/_tools/paper_frontmatter.py) 없음")

FM = {
    "type": "paper",
    "Reading-Status": '"☑️ Not Started"',
    "Read-Depth": "",
    "Author": "A et al.",
    "Journal/Conference": "Venue",
    "Published Year": "2026",
    "Topic": "test",
    "Review-Date": "2026-09-22",
    "Comment": "c",
    "URL": "https://arxiv.org/abs/2601.15380v2",
    "Category": "Reasoning",
    "linked-bases": '"[[Papers.base]]"',
    "Lab": "",
}
META = {
    "template-version": "paper-note-v3",
    "template-id": "general-v1",
    "summary-mode": "preread",
    "profile": "empirical",
    "source-coverage": "fulltext",
    "quality-status": "ready",
    "visual-check": "viewed",
    "visual-scope": "main-body",
}
META_KEYS = validator.META_KEYS_ALL


def _split(overrides, drop):
    fm_o = {k: v for k, v in (overrides or {}).items() if k not in META_KEYS}
    meta_o = {k: v for k, v in (overrides or {}).items() if k in META_KEYS}
    fm_d = tuple(k for k in drop if k not in META_KEYS)
    meta_d = tuple(k for k in drop if k in META_KEYS)
    return fm_o, meta_o, fm_d, meta_d


def _fm_text(overrides=None, drop=()):
    fm_o, _, fm_d, _ = _split(overrides, drop)
    fm = dict(FM)
    fm.update(fm_o)
    for key in fm_d:
        fm.pop(key, None)
    return "---\n" + "".join(f"{k}: {v}\n" if v != "" else f"{k}:\n" for k, v in fm.items()) + "---\n"


def _meta_text(overrides=None, drop=()):
    _, meta_o, _, meta_d = _split(overrides, drop)
    meta = dict(META)
    meta.update(meta_o)
    for key in meta_d:
        meta.pop(key, None)
    if not meta:
        return ""
    return "<!-- BEGIN DRILLER:meta\n" + "".join(f"{k}: {v}\n" for k, v in meta.items()) + "END DRILLER:meta -->\n"


def _visual_block(ids):
    out = ""
    for vid in ids:
        vid, ev = (vid if isinstance(vid, tuple) else (vid, "viewed"))
        out += f"### {vid}\n- 무엇을 보여주는가: 설명\n- 확인 상태: {ev}\n\n"
    return out or "본문 도표 없음 (전체 목록 확인 완료)\n\n"


def v3_note(
    *, fm_overrides=None, drop=(), h2s=GENERAL_H2, visual_ids=("Figure 1", "Table 1"), visual_h2="본문 도표",
    before_auto="# 제목\n\n", after_auto="\n<!-- BEGIN USER:notes -->\n내 메모\n<!-- END USER:notes -->\n",
    begin="<!-- BEGIN AUTO:body template-id=general-v1 -->\n", end="<!-- END AUTO:body -->\n", pad=300, meta=True,
):
    body = ""
    for h in h2s:
        if h == visual_h2:
            body += f"## {h}\n{_visual_block(visual_ids)}"
        else:
            body += f"## {h}\n내용 (Section 1) author-stated\n\n"
    body += "충분한 본문 " * pad
    meta_text = _meta_text(fm_overrides, drop) if meta else ""
    return _fm_text(fm_overrides, drop) + meta_text + before_auto + begin + body + "\n" + end + after_auto


def legacy_note(fm_overrides=None, drop=(), body="# 옛 노트\n\n## 핵심 개념\n" + "본문 " * 300):
    return _fm_text(fm_overrides, drop) + body


PREREAD_V2_META = {
    "template-version": "paper-preread-v2", "summary-mode": "preread", "profile": "empirical",
    "source-coverage": "fulltext", "quality-status": "ready", "reading-decision": "read", "decision-confidence": "high",
}
PREREAD_V2_BODY = (
    "# 제목\n\n## 읽기 판단\n**읽기** — 이유\n\n> [!summary] 1분 요약\n> summary\n\n## 핵심 아이디어\nidea\n\n"
    "## 무엇을 했나\nmethod\n\n## 핵심 근거\nevidence\n\n## 어디까지 믿을까\nlimits\n\n## 원문 읽기 지도\nmap\n\n" + "본문 " * 300
)


def v2_note(meta_overrides=None, fm_overrides=None, body=PREREAD_V2_BODY):
    meta = dict(PREREAD_V2_META)
    meta.update(meta_overrides or {})
    block = "<!-- BEGIN DRILLER:meta\n" + "".join(f"{k}: {v}\n" for k, v in meta.items()) + "END DRILLER:meta -->\n"
    return _fm_text(fm_overrides) + block + body


def manifest(items=None, **top):
    m = {
        "manifest_version": 1, "doc_id": "arxiv:2601.15380", "source": "pdf:/tmp/cached.pdf", "scan": "complete",
        "items": items if items is not None else [
            {"id": "Figure 1", "main_body": True, "evidence": "viewed"},
            {"id": "Table 1", "main_body": True, "evidence": "viewed"},
            {"id": "Figure 7", "main_body": False, "evidence": "not-seen", "note": "Appendix"},
        ],
    }
    m.update(top)
    return m


@pytest.fixture
def note_dir(tmp_path):
    d = tmp_path / "Public" / "AI" / "Papers"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def templates(tmp_path, monkeypatch):
    d = tmp_path / "templates"
    d.mkdir()
    shutil.copy(REAL_GENERAL_TEMPLATE, d / "general-v1.md")
    monkeypatch.setattr(validator, "TEMPLATES_DIR", d)
    return d


def write(path, text=None, data=None):
    if data is not None:
        text = json.dumps(data, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- frontmatter contract (engine) ------------------------------------------

def test_schema_keys_match_engine_and_schema_json():
    engine, _ = validator.load_engine()
    assert tuple(validator.PAPER_KEYS) == engine.PAPER_KEYS
    assert validator.PAPER_SCHEMA["schema_version"] == 4
    assert validator.PAPER_SCHEMA["frontmatter"]["keys"] == list(engine.PAPER_KEYS)


def test_legacy_manual_note_needs_only_the_13_keys_and_old_values_are_not_rejected(note_dir):
    plain = write(note_dir / "plain.md", legacy_note({"Reading-Status": "reading", "Category": "LLMs", "Published Year": "2017-05", "Review-Date": "언젠가", "URL": "N/A"}))
    v, w = validator.validate(plain)
    assert v == [] and w == []
    listy = write(note_dir / "listy.md", legacy_note().replace("Reading-Status: \"☑️ Not Started\"\n", "Reading-Status:\n  - ▶️ In progress\n"))
    assert validator.validate(listy)[0] == []
    blank = write(note_dir / "blank.md", "---\ntype: paper\n" + "".join(f"{k}:\n" for k in validator.PAPER_KEYS[1:]) + "---\n# 제목\n" + "본문 " * 300)
    assert validator.validate(blank)[0] == []


def test_forbidden_keys_missing_keys_and_order_are_frontmatter_violations(note_dir):
    v, _ = validator.validate(write(note_dir / "extra.md", legacy_note({"arXiv-ID": "2601.15380", "DOI": "N/A", "tags": "[x]"})))
    assert any("KEY-FORBIDDEN" in x and "arXiv-ID" in x for x in v)
    assert any("KEY-FORBIDDEN" in x and "tags" in x for x in v)
    v, _ = validator.validate(write(note_dir / "missing.md", legacy_note(drop=("Lab", "Read-Depth"))))
    assert any("KEY-MISSING" in x and "Lab" in x for x in v) and any("Read-Depth" in x for x in v)
    v, _ = validator.validate(write(note_dir / "order.md", legacy_note().replace("type: paper\n", "").replace("Lab:\n", "Lab:\ntype: paper\n")))
    assert any("KEY-ORDER" in x for x in v)
    # template keys leaked into YAML are forbidden even for a v3 note
    v, _ = validator.validate(write(note_dir / "leak.md", v3_note().replace("Lab:\n", "Lab:\ntemplate-version: paper-note-v3\n")))
    assert any("KEY-FORBIDDEN" in x and "template-version" in x for x in v)


def test_duplicate_and_broken_yaml_are_violations(note_dir):
    v, _ = validator.validate(write(note_dir / "dup.md", legacy_note().replace("Lab:\n", "Lab:\nAuthor: B\n")))
    assert any("YAML-DUPLICATE-KEY" in x for x in v)
    v, _ = validator.validate(write(note_dir / "broken.md", legacy_note({"Comment": "[unclosed"})))
    assert any("YAML-BROKEN" in x for x in v)


def test_engine_missing_is_fail_closed(note_dir, monkeypatch, capsys):
    note = write(note_dir / "n.md", legacy_note())
    monkeypatch.setattr(validator, "_ENGINE", None)
    monkeypatch.setattr(validator, "find_engine", lambda start=None: None)
    monkeypatch.delitem(validator.sys.modules, "paper_frontmatter", raising=False)
    assert validator.main(["--path", str(note)]) == 2
    assert "SCHEMA: frontmatter 엔진" in capsys.readouterr().err


def test_generated_note_must_not_claim_human_reading_fields(note_dir, templates):
    v, _ = validator.validate(write(note_dir / "depth.md", v3_note(fm_overrides={"Read-Depth": "📖 Full paper"})))
    assert any("Read-Depth is the human reading depth" in x for x in v)
    v, _ = validator.validate(write(note_dir / "done.md", v3_note(fm_overrides={"Reading-Status": '"✅ Done"'})))
    assert any("may only be blank or Not Started" in x for x in v)
    assert validator.validate(write(note_dir / "blank.md", v3_note(fm_overrides={"Reading-Status": ""})))[0] == []
    # on update, the user's values are simply preserved (not re-judged as a fresh note)
    old = write(note_dir / "old.md", v3_note(fm_overrides={"Read-Depth": "📖 Full paper", "Reading-Status": '"✅ Done"'}))
    res = validator.validate_note(old, previous_path=old, cli=True)
    assert res.violations == []
    # legacy human notes are never judged on these fields
    assert validator.validate(write(note_dir / "human.md", legacy_note({"Read-Depth": "📖 Full paper", "Reading-Status": '"✅ Done"'})))[0] == []


def test_driller_note_value_formats_are_checked_but_legacy_are_not(note_dir, templates):
    v, _ = validator.validate(write(note_dir / "a.md", v3_note(fm_overrides={"Published Year": "26", "Review-Date": "2026/09/22", "Category": "LLMs", "URL": "arxiv.org/abs/1"})))
    joined = "\n".join(v)
    assert "Published Year=`26`" in joined and "Review-Date=`2026/09/22`" in joined and "Category=`LLMs`" in joined and "URL=" in joined
    assert validator.validate(write(note_dir / "b.md", v3_note(fm_overrides={"Category": "", "URL": ""})))[0] == []


# --- DRILLER:meta block --------------------------------------------------------

def test_meta_block_rules(note_dir, templates):
    two = v3_note().replace("# 제목", _meta_text() + "# 제목", 1)
    v, _ = validator.validate(write(note_dir / "two.md", two))
    assert any("정확히 하나" in x for x in v)
    late = v3_note(meta=False).replace("<!-- END AUTO:body -->\n", "<!-- END AUTO:body -->\n" + _meta_text())
    v, _ = validator.validate(write(note_dir / "late.md", late))
    assert any("AUTO:body 앞" in x for x in v)
    unknown = v3_note().replace("visual-scope: main-body\n", "visual-scope: main-body\nfoo: bar\n")
    v, _ = validator.validate(write(note_dir / "unknown.md", unknown))
    assert any("unknown keys in DRILLER:meta" in x and "foo" in x for x in v)
    fenced = v3_note(meta=False).replace("# 제목", "```\n" + _meta_text() + "```\n# 제목", 1)
    v, _ = validator.validate(write(note_dir / "fenced.md", fenced))
    assert any("cannot downgrade" in x for x in v)  # fenced block is text; note is then v3-shaped without version


def test_meta_sidecar_argument(note_dir, templates, capsys):
    note = write(note_dir / "v2.md", _fm_text() + PREREAD_V2_BODY)
    assert validator.main(["--path", str(note)]) == 0  # legacy path: passes on structure alone
    side = write(note_dir / "v2.meta.json", data=dict(PREREAD_V2_META))
    assert validator.main(["--path", str(note), "--meta", str(side)]) == 0
    assert "driller-meta" in capsys.readouterr().out
    bad = write(note_dir / "bad.meta.json", data={"template-version": "paper-preread-v2", "summary-mode": "deep"})
    assert validator.main(["--path", str(note), "--meta", str(bad)]) == 2
    assert "requires summary-mode=`preread`" in capsys.readouterr().err
    conflict = write(note_dir / "c.md", v3_note())
    side2 = write(note_dir / "c.meta.json", data={"template-id": "other-v1"})
    assert validator.main(["--path", str(conflict), "--meta", str(side2)]) == 2
    assert "differs between DRILLER:meta block" in capsys.readouterr().err
    assert validator.main(["--path", str(note), "--meta", str(note_dir / "nope.json")]) == 2


# --- legacy v2 -----------------------------------------------------------------

def test_valid_preread_v2_passes_and_its_rules_still_apply(note_dir):
    path = write(note_dir / "valid.md", v2_note())
    v, w = validator.validate(path)
    assert v == [] and w == []
    v, _ = validator.validate(write(note_dir / "nomap.md", v2_note(body=PREREAD_V2_BODY.replace("## 원문 읽기 지도\nmap\n\n", ""))))
    assert any("section missing: `## 원문 읽기 지도`" in x for x in v)
    v, _ = validator.validate(write(note_dir / "nodecision.md", v2_note({"reading-decision": ""})))
    assert any("requires `reading-decision`" in x for x in v)
    v, _ = validator.validate(write(note_dir / "long.md", v2_note(body=PREREAD_V2_BODY + "가" * 6000)))
    assert any("길이 상한 초과" in x for x in v)


def test_legacy_paper_deep_v2_is_accepted_with_its_own_rules(note_dir):
    deep_meta = dict(PREREAD_V2_META, **{"template-version": "paper-deep-v2", "summary-mode": "deep"})
    long_deep = "\n\n## 상세 독해 노트\n```mermaid\ngraph TD; A-->B\n```\n" + "가" * 6000
    v, w = validator.validate(write(note_dir / "deep.md", v2_note(deep_meta, body=PREREAD_V2_BODY + long_deep)))
    assert v == [] and w == []
    v, _ = validator.validate(write(note_dir / "deep-no-extra.md", v2_note(deep_meta)))
    assert any("paper-deep-v2 requires `## 상세 독해 노트`" in x for x in v), v
    v, _ = validator.validate(write(note_dir / "deep-wrong-mode.md", v2_note(dict(deep_meta, **{"summary-mode": "preread"}), body=PREREAD_V2_BODY + long_deep)))
    assert any("paper-deep-v2 requires summary-mode=`deep`" in x for x in v), v
    assert "paper-deep-v2" in validator.KNOWN_TEMPLATE_VERSIONS


# --- template files --------------------------------------------------------------

def test_real_general_v1_template_passes_static_check():
    meta, errors = validator.check_template_file(REAL_GENERAL_TEMPLATE)
    assert errors == []
    assert meta["required_h2"] == GENERAL_H2 and meta["visual_section"] == "본문 도표"


def test_template_check_rejects_traversal_symlink_and_bad_metadata(tmp_path, templates):
    outside = write(tmp_path / "outside-v1.md", (templates / "general-v1.md").read_text().replace("general-v1", "outside-v1"))
    _, errors = validator.check_template_file(outside)
    assert any("inside" in e for e in errors)
    link = templates / "linked-v1.md"
    link.symlink_to(outside)
    _, errors = validator.check_template_file(link)
    assert any("symbolic" in e for e in errors)
    _, errors = validator.check_template_file(write(templates / "Bad_ID.md", (templates / "general-v1.md").read_text()))
    assert any("filename" in e for e in errors)
    _, errors = validator.check_template_file(write(templates / "other-v1.md", (templates / "general-v1.md").read_text()))
    assert any("!= filename" in e for e in errors)
    _, errors = validator.check_template_file(write(templates / "dup-v1.md", '```json\n{"id":"dup-v1","id":"dup-v1","title":"t","description":"d","required_h2":["A"],"visual_section":"A"}\n```\n안내\n'))
    assert any("duplicate JSON key" in e for e in errors)
    _, errors = validator.check_template_file(write(templates / "novis-v1.md", '```json\n{"id":"novis-v1","title":"t","description":"d","required_h2":["A","A"],"visual_section":"B"}\n```\n안내\n'))
    assert any("duplicate headings" in e for e in errors) and any("visual_section" in e for e in errors)
    _, errors = validator.check_template_file(write(templates / "type-v1.md", '```json\n{"id":"type-v1","title":"","description":"d","required_h2":"A","visual_section":"A"}\n```\n안내\n'))
    assert any("`title`" in e for e in errors) and any("required_h2" in e for e in errors)
    _, errors = validator.load_template("../general-v1")
    assert errors and "must match" in errors[0]


def test_template_metadata_type_errors_do_not_raise(templates):
    for name, meta in {
        "objs-v1": '{"id":"objs-v1","title":"t","description":"d","required_h2":[{}],"optional_h2":[],"visual_section":"A"}',
        "opt-v1": '{"id":"opt-v1","title":"t","description":"d","required_h2":["A"],"optional_h2":[1],"visual_section":"A"}',
        "req-str-v1": '{"id":"req-str-v1","title":"t","description":"d","required_h2":"A","optional_h2":{},"visual_section":"A"}',
    }.items():
        _, errors = validator.check_template_file(write(templates / f"{name}.md", f"```json\n{meta}\n```\n안내\n"))
        assert any("list of non-empty strings" in e for e in errors), (name, errors)


# --- v3 structure ----------------------------------------------------------------

def test_v3_general_note_passes_with_no_length_cap(note_dir, templates):
    path = write(note_dir / "v3.md", v3_note(pad=3000))
    v, w = validator.validate(path)
    assert v == [] and w == [] and len(path.read_text(encoding="utf-8")) > 6000


def test_v3_deep_has_no_mermaid_warning_but_legacy_deep_still_warns(note_dir, templates):
    _, w = validator.validate(write(note_dir / "deep3.md", v3_note(fm_overrides={"summary-mode": "deep"}, h2s=GENERAL_H2 + ["상세 독해 노트"])))
    assert w == []
    legacy = write(note_dir / "legacy-deep.md", _fm_text() + "<!-- BEGIN DRILLER:meta\nsummary-mode: deep\nEND DRILLER:meta -->\n# 제목\n\n## 아무 절\n" + "본문 " * 300)
    v, w = validator.validate(legacy)
    assert v == [] and any("mermaid" in x for x in w)


def test_v3_missing_duplicate_and_out_of_order_sections_fail(note_dir, templates):
    v, _ = validator.validate(write(note_dir / "missing.md", v3_note(h2s=[h for h in GENERAL_H2 if h != "지표"])))
    assert any("missing" in x and "지표" in x for x in v)
    v, _ = validator.validate(write(note_dir / "dup.md", v3_note(h2s=GENERAL_H2 + ["지표"])))
    assert any("duplicated" in x and "지표" in x for x in v)
    reordered = list(GENERAL_H2)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    v, _ = validator.validate(write(note_dir / "order.md", v3_note(h2s=reordered)))
    assert any("out of template order" in x for x in v)


def test_v3_unknown_template_or_version_fails_but_versionless_note_is_lenient(note_dir, templates):
    v, _ = validator.validate(write(note_dir / "tid.md", v3_note(fm_overrides={"template-id": "nope-v9"})))
    assert any("TEMPLATE: file not found" in x for x in v)
    v, _ = validator.validate(write(note_dir / "tver.md", v3_note(fm_overrides={"template-version": "paper-note-v4"})))
    assert any("template-version=`paper-note-v4`" in x for x in v)
    assert validator.validate(write(note_dir / "old.md", legacy_note()))[0] == []


def test_custom_template_with_different_headings_passes(note_dir, templates):
    write(templates / "theory-v1.md", '```json\n{"id":"theory-v1","title":"이론","description":"d","required_h2":["개요","가정","정리","증명 구조","도표"],"visual_section":"도표"}\n```\n\n작성 안내.\n')
    note = v3_note(fm_overrides={"template-id": "theory-v1"}, h2s=["개요", "가정", "정리", "증명 구조", "도표"], visual_h2="도표", begin="<!-- BEGIN AUTO:body template-id=theory-v1 -->\n")
    assert validator.validate(write(note_dir / "theory.md", note))[0] == []


def test_headings_in_code_user_blocks_or_outside_auto_do_not_count(note_dir, templates):
    note = v3_note(h2s=[h for h in GENERAL_H2 if h != "지표"], before_auto="# 제목\n\n## 지표\n밖에 있는 절\n\n")
    note = note.replace("## 주요 결과", "```\n## 지표\n```\n<!-- BEGIN USER:extra -->\n## 지표\n<!-- END USER:extra -->\n## 주요 결과", 1)
    v, _ = validator.validate(write(note_dir / "fake.md", note))
    assert any("missing" in x and "지표" in x for x in v), v


def test_auto_marker_problems_fail(note_dir, templates):
    cases = {
        "no-begin": v3_note(begin=""),
        "no-end": v3_note(end=""),
        "double-begin": v3_note(before_auto="# 제목\n<!-- BEGIN AUTO:body template-id=general-v1 -->\n"),
        "reversed": v3_note(begin="<!-- END AUTO:body -->\n", end="<!-- BEGIN AUTO:body template-id=general-v1 -->\n"),
        "nested": v3_note().replace("## 지표", "<!-- BEGIN AUTO:preread -->\n## 지표", 1),
        "id-mismatch": v3_note(begin="<!-- BEGIN AUTO:body template-id=other-v1 -->\n"),
    }
    for name, text in cases.items():
        v, _ = validator.validate(write(note_dir / f"{name}.md", text))
        assert any(x.startswith("MARKER:") for x in v), (name, v)


def test_v3_meta_rules(note_dir, templates):
    v, _ = validator.validate(write(note_dir / "a.md", v3_note(fm_overrides={"visual-check": "seen"})))
    assert any("visual-check=`seen`" in x for x in v)
    v, _ = validator.validate(write(note_dir / "b.md", v3_note(fm_overrides={"visual-scope": "user-narrowed"})))
    assert any("visual-scope-note" in x for x in v)
    v, _ = validator.validate(write(note_dir / "c.md", v3_note(fm_overrides={"source-coverage": "abstract-only"})))
    assert any("abstract-only|unknown" in x for x in v)
    v, _ = validator.validate(write(note_dir / "d.md", v3_note(fm_overrides={"visual-check": "caption-only"})))
    assert any("ready` not allowed with visual-check=`caption-only`" in x for x in v)
    v, _ = validator.validate(write(note_dir / "e.md", v3_note(fm_overrides={"visual-check": "none"})))
    assert any("visual-check=`none` but the visual section lists items" in x for x in v)
    v, _ = validator.validate(write(note_dir / "f.md", v3_note(drop=("visual-scope",))))
    assert any("requires `visual-scope`" in x for x in v)
    v, _ = validator.validate(write(note_dir / "g.md", v3_note(fm_overrides={"reading-decision": "maybe"})))
    assert any("reading-decision=`maybe`" in x for x in v)
    assert validator.validate(write(note_dir / "h.md", v3_note(fm_overrides={"reading-decision": "read", "decision-confidence": "high"})))[0] == []


def test_versionless_v3_shaped_note_fails_but_plain_legacy_note_passes(note_dir, templates):
    v, _ = validator.validate(write(note_dir / "dropped.md", v3_note(drop=("template-version",))))
    assert any("cannot downgrade to the legacy path" in x and "template-id" in x for x in v), v
    markers_only = write(note_dir / "markers.md", _fm_text() + "# 제목\n\n<!-- BEGIN AUTO:body template-id=general-v1 -->\n## 절\n" + "본문 " * 300 + "\n<!-- END AUTO:body -->\n")
    v, _ = validator.validate(markers_only)
    assert any("AUTO:body markers" in x and "cannot downgrade" in x for x in v), v
    assert validator.validate(write(note_dir / "plain.md", legacy_note()))[0] == []


def test_markers_inside_code_fences_and_missing_template_id_fail(note_dir, templates):
    fenced = v3_note(begin="```markdown\n<!-- BEGIN AUTO:body template-id=general-v1 -->\n", end="<!-- END AUTO:body -->\n```\n")
    v, _ = validator.validate(write(note_dir / "fenced.md", fenced))
    assert any("expected exactly one `<!-- BEGIN AUTO:body" in x and "found 0" in x for x in v), v
    example = v3_note().replace("## 지표", "## 지표\n```markdown\n<!-- BEGIN AUTO:body template-id=general-v1 -->\n<!-- END AUTO:body -->\n```\n", 1)
    assert validator.validate(write(note_dir / "example.md", example))[0] == []
    v, _ = validator.validate(write(note_dir / "noid.md", v3_note(begin="<!-- BEGIN AUTO:body -->\n")))
    assert any("must carry `template-id=general-v1`" in x for x in v), v


def test_v3_deep_requires_nonempty_extra_section_after_template(note_dir, templates):
    v, _ = validator.validate(write(note_dir / "deep-missing.md", v3_note(fm_overrides={"summary-mode": "deep"})))
    assert any("summary-mode=`deep` requires `## 상세 독해 노트`" in x for x in v), v
    empty = v3_note(fm_overrides={"summary-mode": "deep"}).replace("<!-- END AUTO:body -->", "## 상세 독해 노트\n\n<!-- END AUTO:body -->")
    v, _ = validator.validate(write(note_dir / "deep-empty.md", empty))
    assert any("is empty" in x for x in v), v
    early = v3_note(fm_overrides={"summary-mode": "deep"}, h2s=["상세 독해 노트"] + GENERAL_H2)
    v, _ = validator.validate(write(note_dir / "deep-early.md", early))
    assert any("must come after all required template sections" in x for x in v), v
    assert validator.validate(write(note_dir / "deep-ok.md", v3_note(fm_overrides={"summary-mode": "deep"}, h2s=GENERAL_H2 + ["상세 독해 노트"])))[0] == []
    assert validator.validate(write(note_dir / "preread.md", v3_note()))[0] == []


# --- identity (URL only) -------------------------------------------------------------

def test_doc_ids_are_derived_from_url_only():
    d = validator.derive_doc_ids
    assert d({"URL": "https://arxiv.org/abs/2601.15380v2"}) == {"url": ("arxiv.org/abs/2601.15380v2", None), "arxiv": ("2601.15380", "v2")}
    assert d({"URL": "http://www.arxiv.org/pdf/2601.15380.pdf"})["arxiv"] == ("2601.15380", None)
    assert d({"URL": "https://arxiv.org/abs/cs/0112017"})["arxiv"] == ("cs/0112017", None)
    assert d({"URL": "https://doi.org/10.1000/ABC"})["doi"] == ("10.1000/abc", None)
    assert d({"URL": "https://dx.doi.org/10.1000/ABC"})["doi"] == ("10.1000/abc", None)
    assert "arxiv" not in d({"URL": "https://openreview.net/forum?id=A"}) and "doi" not in d({"URL": "https://openreview.net/forum?id=A"})
    assert d({"URL": "N/A"}) == {} and d({"URL": ""}) == {}
    assert d({"URL": "not a url"})["__invalid__"] == {"url": "not a url"}
    assert d({"URL": "https://arxiv.org/abs/not-an-id"}) == {"url": ("arxiv.org/abs/not-an-id", None)}


def test_url_identity_is_conservative():
    n = validator._norm_url
    assert n("https://openreview.net/forum?id=PAPER_A") != n("https://openreview.net/forum?id=PAPER_B")
    assert n("https://example.org/Paper") != n("https://example.org/paper")
    assert n("HTTP://WWW.Example.org/Paper/#sec") == n("https://example.org/Paper")
    assert n("https://openreview.net/forum?id=A") == n("http://www.openreview.net/forum?id=A")
    assert n("not-a-url") is None and n("ftp://x.org/a") is None
    e = validator.check_manifest_binding({"doc_id": "url:https://openreview.net/forum?id=B"}, {"URL": "https://openreview.net/forum?id=A"})
    assert e and "does not match" in e[0]
    e = validator.check_manifest_binding({"doc_id": "url:https://example.org/PaperA"}, {"URL": "https://example.org/papera"})
    assert e and "does not match" in e[0]
    assert validator.check_manifest_binding({"doc_id": "url:https://Example.org/PaperA"}, {"URL": "https://www.example.org/PaperA/"}) == []


BAD_URLS = {
    "port-word": "https://example.org:bad/Paper",
    "port-range": "https://example.org:99999/Paper",
    "space-host": "https://exa mple.org/Paper",
    "tab-host": "https://exa\tmple.org/Paper",
    "space-path": "https://example.org/Pa per",
}


def test_norm_url_rejects_bad_ports_and_internal_whitespace_without_raising():
    n = validator._norm_url
    for name, url in BAD_URLS.items():
        assert n(url) is None, name
    assert n("https://example.org/Pa\nper") is None
    assert n("  https://example.org/Paper  ") == "example.org/Paper"
    fm = dict(FM, URL="https://example.org/Paper")
    for name, url in BAD_URLS.items():
        errs = validator.check_manifest_binding({"doc_id": f"url:{url}"}, fm)
        assert errs and "is not a valid url identifier" in errs[0], (name, errs)
        bad_note = validator.check_manifest_binding({"doc_id": "url:https://example.org/Paper"}, dict(FM, URL=url))
        assert bad_note and "cannot bind" in bad_note[0], (name, bad_note)


def test_norm_url_keeps_distinct_identities_distinct():
    n = validator._norm_url
    for a, b in [
        ("https://example.org/Paper//", "https://example.org/Paper/"),
        ("https://example.org:0/Paper", "https://example.org/Paper"),
        ("http://[::1]:80/P", "http://[::1:80]/P"),
    ]:
        na, nb = n(a), n(b)
        assert na is not None and nb is not None and na != nb, (a, b, na)
        e = validator.check_manifest_binding({"doc_id": f"url:{a}"}, dict(FM, URL=b))
        assert e and "does not match" in e[0], (a, b, e)
    assert n("https://example.org/Paper/") == n("https://example.org/Paper") == "example.org/Paper"
    assert n("https://example.org") == n("https://example.org/") == "example.org/"
    assert n("http://[::1]:80/P") == "[::1]:80/P" and n("https://example.org:8080/x?q=1") == "example.org:8080/x?q=1"


# --- manifest ----------------------------------------------------------------------

def _run(note_dir, templates, note_text, manifest_obj=None, manifest_text=None, name="n"):
    note = write(note_dir / f"{name}.md", note_text)
    mpath = None
    if manifest_obj is not None or manifest_text is not None:
        mpath = write(note_dir / f"{name}.manifest.json", text=manifest_text, data=manifest_obj)
    return validator.validate_note(note, manifest_path=mpath, cli=True)


def test_manifest_complete_match_passes_and_is_reported_checked(note_dir, templates):
    res = _run(note_dir, templates, v3_note(), manifest())
    assert res.violations == [] and "visuals" in res.checked and "template:general-v1" in res.checked and res.skipped == []


def test_malformed_manifest_is_failure_not_skip(note_dir, templates):
    res = _run(note_dir, templates, v3_note(), manifest_text="{not json")
    assert any("invalid JSON" in v for v in res.violations) and any("malformed" in v for v in res.violations)
    assert "visuals" not in res.checked
    res = _run(note_dir, templates, v3_note(), manifest_text='{"manifest_version":1,"manifest_version":1,"doc_id":"arxiv:2601.15380","source":"s","scan":"complete","items":[]}', name="dupkey")
    assert any("duplicate JSON key" in v for v in res.violations)
    bad_items = manifest(items=[
        {"id": "Figure 1", "main_body": "false", "evidence": "viewed"},
        {"id": "Table 1", "main_body": True},
        {"id": "Table 1", "main_body": True, "evidence": "viewed"},
        {"id": "", "main_body": True, "evidence": "viewed"},
        {"id": "Figure 2", "main_body": True, "evidence": "seen"},
    ])
    joined = "\n".join(_run(note_dir, templates, v3_note(), bad_items, name="items").violations)
    assert "main_body must be true, false or \"unsure\" (got 'false')" in joined
    assert "items[1] missing `evidence`" in joined and "duplicate item id `Table 1`" in joined
    assert "items[3] id must be a non-empty string" in joined and "evidence must be one of" in joined
    res = _run(note_dir, templates, v3_note(), manifest(scan="partial"), name="partial-no-note")
    assert any("scan=partial requires" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(), manifest(extra="x", manifest_version=True), name="extra")
    assert any("unknown top-level keys" in v for v in res.violations) and any("manifest_version must be the integer" in v for v in res.violations)


def test_manifest_must_bind_to_the_same_paper_and_version_via_url(note_dir, templates):
    res = _run(note_dir, templates, v3_note(), manifest(doc_id="arxiv:2602.00001"), name="other")
    assert any("does not match the note" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(), manifest(doc_id="arxiv:2601.15380v1"), name="ver")
    assert any("version mismatch" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(), manifest(doc_version="v3"), name="ver2")
    assert any("version mismatch" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(), manifest(doc_id="doi:10.1000/x"), name="kind")
    assert any("does not yield a `doi` identifier" in v for v in res.violations)
    assert _run(note_dir, templates, v3_note(), manifest(doc_id="arxiv:2601.15380v2"), name="same").violations == []
    res = _run(note_dir, templates, v3_note(fm_overrides={"URL": "https://doi.org/10.1000/ABC"}), manifest(doc_id="doi:10.1000/abc"), name="doi")
    assert res.violations == []
    res = _run(note_dir, templates, v3_note(fm_overrides={"URL": "https://arxiv.org/pdf/2601.15380v2.pdf"}), manifest(doc_id="arxiv:2601.15380v2"), name="pdf")
    assert res.violations == []
    res = _run(note_dir, templates, v3_note(fm_overrides={"URL": "https://openreview.net/forum?id=A"}), manifest(doc_id="url:https://openreview.net/forum?id=A"), name="url")
    assert res.violations == []


def test_visual_items_missing_extra_duplicate_and_order_fail(note_dir, templates):
    res = _run(note_dir, templates, v3_note(visual_ids=("Figure 1",)), manifest(), name="missing")
    assert any("missing from note: `### Table 1`" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(visual_ids=("Figure 1", "Table 1", "Figure 7")), manifest(), name="extra")
    assert any("`### Figure 7` which is not a manifest target" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(visual_ids=("Figure 1", "Table 1", "Table 1")), manifest(), name="dup")
    assert any("more than once: `### Table 1`" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(visual_ids=("Table 1", "Figure 1")), manifest(), name="order")
    assert any("not in source order" in v for v in res.violations)
    assert _run(note_dir, templates, v3_note(visual_ids=("Figure 1 — 학습 곡선", "Table 1: 결과")), manifest(), name="titled").violations == []
    res = _run(note_dir, templates, v3_note(visual_ids=("Fig. 1", "Table 1")), manifest(), name="fig")
    assert any("`### Figure 1`" in v for v in res.violations)


def test_visual_check_and_quality_status_follow_manifest_evidence(note_dir, templates):
    m = manifest(items=[{"id": "Figure 1", "main_body": True, "evidence": "viewed"}, {"id": "Table 1", "main_body": True, "evidence": "caption-only"}])
    res = _run(note_dir, templates, v3_note(), m, name="mixed-wrong")
    assert any("visual-check=`viewed` but manifest implies `mixed`" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(fm_overrides={"visual-check": "mixed", "quality-status": "ready"}), m, name="mixed-ready")
    assert any("quality-status=`ready` not allowed" in v for v in res.violations)
    res = _run(note_dir, templates, v3_note(fm_overrides={"visual-check": "mixed", "quality-status": "review"}), m, name="mixed-lying")
    assert any("`### Table 1` states 확인 상태 ['viewed'] but manifest evidence is `caption-only`" in v for v in res.violations)
    honest = ("Figure 1", ("Table 1", "caption-only"))
    assert _run(note_dir, templates, v3_note(visual_ids=honest, fm_overrides={"visual-check": "mixed", "quality-status": "review"}), m, name="mixed-review").violations == []
    m = manifest(items=[{"id": "Figure 1", "main_body": True, "evidence": "not-seen"}, {"id": "Table 1", "main_body": True, "evidence": "viewed"}])
    honest = (("Figure 1", "not-seen"), "Table 1")
    assert _run(note_dir, templates, v3_note(visual_ids=honest, fm_overrides={"visual-check": "unverified", "quality-status": "review"}), m, name="notseen").violations == []
    assert validator.expected_visual_check(m) == "unverified"
    m = manifest(items=[{"id": "Figure 1", "main_body": "unsure", "evidence": "viewed"}, {"id": "Table 1", "main_body": True, "evidence": "viewed"}])
    assert any("every target main_body=true" in v for v in _run(note_dir, templates, v3_note(), m, name="unsure-ready").violations)
    m = manifest(scan="partial", scan_note="pages 9+ unreadable")
    assert any("needs scan=complete" in v for v in _run(note_dir, templates, v3_note(), m, name="partial-ready").violations)
    assert _run(note_dir, templates, v3_note(visual_ids=(), fm_overrides={"visual-check": "none"}), manifest(items=[]), name="none-ok").violations == []
    empty_partial = manifest(items=[], scan="partial", scan_note="only abstract page")
    res = _run(note_dir, templates, v3_note(visual_ids=(), fm_overrides={"visual-check": "none"}), empty_partial, name="none-bad")
    assert any("manifest implies `unverified`" in v for v in res.violations) and validator.expected_visual_check(empty_partial) == "unverified"


def test_user_narrowed_scope_requires_both_manifest_scope_and_note_fields(note_dir, templates):
    scoped = manifest(scope={"requested_by_user": "Figure 1만 설명해줘", "include": ["Figure 1"]})
    res = _run(note_dir, templates, v3_note(visual_ids=("Figure 1",)), scoped, name="scope-nofm")
    assert any("visual-scope is not `user-narrowed`" in v for v in res.violations)
    narrowed = {"visual-scope": "user-narrowed", "visual-scope-note": '"Figure 1만 설명해줘"'}
    assert _run(note_dir, templates, v3_note(visual_ids=("Figure 1",), fm_overrides=narrowed), scoped, name="scope-ok").violations == []
    res = _run(note_dir, templates, v3_note(fm_overrides=narrowed), manifest(), name="scope-nomanifest")
    assert any("manifest records no user scope" in v for v in res.violations)
    joined = "\n".join(_run(note_dir, templates, v3_note(), manifest(scope={"requested_by_user": "", "include": ["Figure 9"]}), name="scope-bad").violations)
    assert "requested_by_user" in joined and "unknown item `Figure 9`" in joined


def test_scope_quote_empty_description_and_evidence_state_consistency(note_dir, templates):
    scoped = manifest(scope={"requested_by_user": "Figure 1만 설명해줘", "include": ["Figure 1"]})
    fm = {"visual-scope": "user-narrowed", "visual-scope-note": '"모든 도표 해설"'}
    res = _run(note_dir, templates, v3_note(visual_ids=("Figure 1",), fm_overrides=fm), scoped, name="quote-mismatch")
    assert any("visual-scope-note must quote the same request" in v for v in res.violations)
    fm["visual-scope-note"] = '"Figure 1만  설명해줘"'
    assert _run(note_dir, templates, v3_note(visual_ids=("Figure 1",), fm_overrides=fm), scoped, name="quote-ok").violations == []
    empty = v3_note().replace("### Figure 1\n- 무엇을 보여주는가: 설명\n- 확인 상태: viewed\n", "### Figure 1\n")
    assert any("`### Figure 1` has no description" in v for v in _run(note_dir, templates, empty, manifest(), name="empty-h3").violations)
    m = manifest(items=[{"id": "Figure 1", "main_body": True, "evidence": "caption-only"}, {"id": "Table 1", "main_body": True, "evidence": "caption-only"}])
    res = _run(note_dir, templates, v3_note(fm_overrides={"visual-check": "caption-only", "quality-status": "review"}), m, name="claims-viewed")
    assert sum("states 확인 상태 ['viewed'] but manifest evidence is `caption-only`" in v for v in res.violations) == 2
    m = manifest(items=[{"id": "Figure 1", "main_body": True, "evidence": "not-seen"}, {"id": "Table 1", "main_body": True, "evidence": "viewed"}])
    note = v3_note(visual_ids=(), fm_overrides={"visual-check": "unverified", "quality-status": "review"}).replace(
        "본문 도표 없음 (전체 목록 확인 완료)\n\n",
        "### Figure 1\n- **확인 상태**: `not-seen` — 캡션도 확보하지 못함\n\n### Table 1\n- 캡션에서 확인되는 열: 모델, 정확도\n\n",
    )
    assert _run(note_dir, templates, note, m, name="honest").violations == []


def test_custom_template_without_any_general_headings_passes(note_dir, templates):
    write(templates / "systems-v1.md", '```json\n{"id":"systems-v1","title":"시스템","description":"d","required_h2":["설계 목표","구성 요소","실험 환경","측정 결과","그림과 표"],"visual_section":"그림과 표"}\n```\n\n작성 안내.\n')
    h2s = ["설계 목표", "구성 요소", "실험 환경", "측정 결과", "그림과 표"]
    note = v3_note(fm_overrides={"template-id": "systems-v1"}, h2s=h2s, visual_h2="그림과 표", begin="<!-- BEGIN AUTO:body template-id=systems-v1 -->\n")
    res = _run(note_dir, templates, note, manifest(), name="systems")
    assert res.violations == [] and "template:systems-v1" in res.checked and "visuals" in res.checked


def test_malformed_identifiers_and_types_give_errors_not_exceptions(note_dir, templates, capsys):
    base = manifest(items=[{"id": "Figure 1", "main_body": True, "evidence": "viewed"}])
    cases = {
        "scan-list": (dict(base, scan=[]), "scan must be one of"),
        "evidence-dict": (dict(base, items=[{"id": "Figure 1", "main_body": True, "evidence": {}}]), "evidence must be one of"),
        "version-float": (dict(base, manifest_version=1.0), "manifest_version must be the integer 1 (got 1.0)"),
        "contradictory": (dict(base, doc_id="arxiv:2601.15380v2", doc_version="v3"), "contradictory"),
        "bad-doc-version": (dict(base, doc_version="three"), "must look like `v2`"),
        "bad-doi": (dict(base, doc_id="doi:not-a-doi"), "not a valid DOI"),
        "bad-url": (dict(base, doc_id="url:not-a-url"), "not a valid http(s) URL"),
        "main-body-list": (dict(base, items=[{"id": "Figure 1", "main_body": [], "evidence": "viewed"}]), "main_body must be"),
    }
    for name, (m, expected) in cases.items():
        note = write(note_dir / f"{name}.md", v3_note(visual_ids=("Figure 1",)))
        mpath = write(note_dir / f"{name}.json", data=m)
        assert validator.main(["--path", str(note), "--manifest", str(mpath)]) == 2, name
        captured = capsys.readouterr()
        assert expected in captured.err and "Traceback" not in captured.err, (name, captured.err)
    note = write(note_dir / "note-url.md", v3_note(visual_ids=("Figure 1",), fm_overrides={"URL": "not a url"}))
    mpath = write(note_dir / "note-url.json", data=dict(base, doc_id="doi:10.1000/abc"))
    res = validator.validate_note(note, manifest_path=mpath, cli=True)
    assert any("URL=`not a url` is not a valid url identifier" in v for v in res.violations) and any("cannot bind" in v for v in res.violations)


def test_cli_bad_url_in_note_or_manifest_is_exit_2_not_traceback(note_dir, templates, capsys):
    base = manifest(items=[{"id": "Figure 1", "main_body": True, "evidence": "viewed"}])
    for name, url in BAD_URLS.items():
        note = write(note_dir / f"note-{name}.md", v3_note(visual_ids=("Figure 1",), fm_overrides={"URL": url}))
        assert validator.main(["--path", str(note)]) == 2, name
        err = capsys.readouterr().err
        assert "FORMAT_VIOLATION" in err and "Traceback" not in err and "is not a valid url identifier" in err, (name, err)
        mpath = write(note_dir / f"note-{name}.json", data=dict(base, doc_id="url:https://example.org/Paper"))
        assert validator.main(["--path", str(note), "--manifest", str(mpath)]) == 2, name
        err = capsys.readouterr().err
        assert "cannot bind" in err and "Traceback" not in err, (name, err)
        good = write(note_dir / f"good-{name}.md", v3_note(visual_ids=("Figure 1",), fm_overrides={"URL": "https://example.org/Paper"}))
        mpath = write(note_dir / f"manifest-{name}.json", data=dict(base, doc_id=f"url:{url}"))
        assert validator.main(["--path", str(good), "--manifest", str(mpath)]) == 2, name
        err = capsys.readouterr().err
        assert "is not a valid http(s) URL" in err and "Traceback" not in err, (name, err)
    good = write(note_dir / "good-ok.md", v3_note(visual_ids=("Figure 1",), fm_overrides={"URL": "https://www.Example.org/Paper/"}))
    mpath = write(note_dir / "manifest-ok.json", data=dict(base, doc_id="url:HTTP://example.org/Paper#x"))
    assert validator.main(["--path", str(good), "--manifest", str(mpath)]) == 0
    assert "RESULT: PASS" in capsys.readouterr().out


def test_manifest_given_to_legacy_note_is_checked_not_ignored(note_dir, capsys):
    note = write(note_dir / "v2.md", v2_note())
    broken = write(note_dir / "broken.json", text="{not json")
    assert validator.main(["--path", str(note), "--manifest", str(broken)]) == 2
    captured = capsys.readouterr()
    assert "malformed" in captured.err and "SKIPPED: visuals (manifest supplied but note is not paper-note-v3" in captured.out
    other = write(note_dir / "other.json", data=manifest(doc_id="arxiv:2602.00001"))
    assert validator.main(["--path", str(note), "--manifest", str(other)]) == 2
    assert "does not match the note" in capsys.readouterr().err
    good = write(note_dir / "good.json", data=manifest())
    assert validator.main(["--path", str(note), "--manifest", str(good)]) == 0
    out = capsys.readouterr().out
    assert "manifest-binding" in out and "SKIPPED: visuals (manifest supplied but note is not paper-note-v3" in out


# --- CLI / hook mode ---------------------------------------------------------------

def test_cli_path_is_fail_closed(tmp_path, note_dir, templates, capsys, monkeypatch):
    monkeypatch.setenv("SKIP_PAPER_VALIDATOR", "1")
    assert validator.main(["--path", str(tmp_path / "missing.md")]) == 2
    assert validator.main(["--path", str(tmp_path)]) == 2
    assert validator.main(["--path", str(write(tmp_path / "note.txt", v3_note()))]) == 2
    assert validator.main(["--path", str(write(note_dir / "nofm.md", "# 제목\n" + "본문 " * 300))]) == 2
    assert validator.main(["--path", str(write(note_dir / "concept.md", v3_note(fm_overrides={"type": "concept"})))]) == 2
    binary = note_dir / "bin.md"
    binary.write_bytes(b"\xff\xfe---\ntype: paper\n---\n# x\n")
    assert validator.main(["--path", str(binary)]) == 2
    assert validator.main(["--path", str(write(note_dir / "_index.md", v3_note(fm_overrides={"template-id": "nope-v9"})))]) == 2
    assert validator.main(["--path", str(note_dir / "x.md"), "--manifest", str(tmp_path / "no.json")]) == 2
    err = capsys.readouterr().err
    assert "PATH: file not found" in err and "not a Markdown" in err and "CLI check requires `type: paper`" in err


def test_cli_distinguishes_checked_from_skipped(note_dir, templates, capsys):
    note = write(note_dir / "ok.md", v3_note())
    assert validator.main(["--path", str(note)]) == 0
    out = capsys.readouterr().out
    assert "CHECKED: frontmatter, driller-meta, structure, template:general-v1" in out
    assert "SKIPPED: visuals (no manifest" in out and "RESULT: PASS" in out
    mpath = write(note_dir / "ok.manifest.json", data=manifest())
    assert validator.main(["--path", str(note), "--manifest", str(mpath)]) == 0
    out = capsys.readouterr().out
    assert "visuals" in out.splitlines()[0] and "SKIPPED" not in out
    bad = write(note_dir / "bad.manifest.json", text="[]")
    assert validator.main(["--path", str(note), "--manifest", str(bad)]) == 2
    captured = capsys.readouterr()
    assert "RESULT: FAIL" in captured.out and "MANIFEST:" in captured.err


def test_cli_check_template_option(templates, capsys):
    assert validator.main(["--check-template", str(templates / "general-v1.md")]) == 0
    assert "RESULT: PASS" in capsys.readouterr().out
    assert validator.main(["--check-template", str(write(templates / "broken-v1.md", "no metadata here\n"))]) == 2
    assert "TEMPLATE_INVALID" in capsys.readouterr().err


def test_hook_mode_scope_is_type_only(note_dir, templates, capsys, monkeypatch):
    def hook(path):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(path)}})))
        return validator.main([])

    note = write(note_dir / "hook.md", v3_note())
    assert hook(note) == 0 and "SKIPPED: visuals" in capsys.readouterr().out
    broken = write(note_dir / "hook-bad.md", v3_note(h2s=GENERAL_H2[:-1], visual_ids=()))
    assert hook(broken) == 2
    capsys.readouterr()
    concept = write(note_dir / "concept.md", "---\ntype: concept\nDOI: x\n---\n# c\n")
    assert hook(concept) == 0  # under Papers/ but not a paper
    nofm = write(note_dir / "raw.md", "# raw\n" + "body " * 200)
    assert hook(nofm) == 0
    overview = write(note_dir / "Topic - _overview.md", legacy_note({"tags": "[moc]"}))
    assert hook(overview) == 2  # filename never excludes a declared paper
    assert "KEY-FORBIDDEN" in capsys.readouterr().err


# --- update preservation ---------------------------------------------------------------

def test_update_preserves_user_content_and_limits_field_changes(note_dir, templates):
    old = v3_note(fm_overrides={"Comment": "원래 코멘트"}, after_auto="\n<!-- BEGIN USER:notes -->\n내 메모\n<!-- END USER:notes -->\n밖의 문장\n")
    ok_new = (old.replace("Review-Date: 2026-09-22", "Review-Date: 2026-10-01")
              .replace("quality-status: ready", "quality-status: review")
              .replace("visual-check: viewed", "visual-check: mixed")
              .replace("내용 (Section 1)", "새 내용 (Section 2)"))
    assert validator.check_update_preservation(old, ok_new) == []
    v = validator.check_update_preservation(old, old.replace("Comment: 원래 코멘트", "Comment: 바뀜"))
    assert any("`Comment` changed" in x for x in v)
    v = validator.check_update_preservation(old, old.replace("Lab:\n", ""))
    assert any("key removed: `Lab`" in x for x in v)
    v = validator.check_update_preservation(old, old.replace("내 메모", "지워짐"))
    assert any("USER block `notes` was altered" in x for x in v)
    v = validator.check_update_preservation(old, old.replace("밖의 문장", "다른 문장"))
    assert any("outside AUTO:body changed" in x for x in v)
    v = validator.check_update_preservation(old, old.replace("template-id: general-v1", "template-id: theory-v1"))
    assert any("approved template switch" in x for x in v)
    v = validator.check_update_preservation(old, old.replace("URL: https://arxiv.org/abs/2601.15380v2", "URL: https://arxiv.org/abs/2601.99999"))
    assert any("`URL` changed" in x for x in v)
    v = validator.check_update_preservation(old, old.replace("profile: empirical", "profile: survey"))
    assert any("DRILLER:meta `profile` changed" in x for x in v)
    v = validator.check_update_preservation(old, old.replace("Read-Depth:\n", "Read-Depth: 📖 Full paper\n"))
    assert any("`Read-Depth` changed" in x for x in v)
    v = validator.check_update_preservation(old, old.replace("visual-scope: main-body\n", ""))
    assert any("DRILLER:meta key removed: `visual-scope`" in x for x in v)
    legacy = legacy_note()
    v = validator.check_update_preservation(legacy, legacy)
    assert any("no well-formed AUTO:body markers" in x for x in v)
    old_path = write(note_dir / "old.md", old)
    new_path = write(note_dir / "new.md", old.replace("Comment: 원래 코멘트", "Comment: 바뀜"))
    res = validator.validate_note(new_path, previous_path=old_path, cli=True)
    assert "update-preservation" in res.checked and any("`Comment` changed" in x for x in res.violations)


def test_update_preservation_compares_raw_yaml_and_keeps_user_todos(note_dir, templates):
    old = (v3_note(fm_overrides={"Comment": '"원래 코멘트"', "Topic": "|\n  첫 줄\n    들여쓴 둘째 줄", "linked-bases": "\n  - '[[A.base]]'\n  - \"[[B.base]]\""})
           .replace("<!-- BEGIN USER:notes -->\n내 메모", "<!-- BEGIN USER:notes -->\nTODO: 나중에 Table 3 다시 보기"))
    ok_new = old.replace("Review-Date: 2026-09-22", "Review-Date: 2026-10-01").replace("내용 (Section 1)", "새 내용 (Section 2)")
    old_path, new_path = write(note_dir / "old.md", old), write(note_dir / "new.md", ok_new)
    res = validator.validate_note(new_path, previous_path=old_path, cli=True)
    assert res.violations == [], res.violations
    v = validator.check_update_preservation(old, ok_new.replace("    들여쓴 둘째 줄", "  들여쓴 둘째 줄"))
    assert any("`Topic` changed (raw YAML differs)" in x for x in v), v
    v = validator.check_update_preservation(old, ok_new.replace('Comment: "원래 코멘트"', "Comment: 원래 코멘트"))
    assert any("`Comment` changed (raw YAML differs)" in x for x in v), v
    v = validator.check_update_preservation(old, ok_new.replace("  - '[[A.base]]'", "  - \"[[A.base]]\""))
    assert any("`linked-bases` changed (raw YAML differs)" in x for x in v), v
    v, _ = validator.validate(write(note_dir / "auto-todo.md", old.replace("내용 (Section 1)", "TODO 내용", 1)))
    assert any("placeholder" in x for x in v)
    v = validator.check_update_preservation(old, ok_new.replace("# 제목", "# 새 제목", 1))
    assert any("outside AUTO:body changed" in x for x in v)


def test_unmigrated_previous_note_is_reported_not_silently_rewritten(note_dir, templates):
    old = v3_note().replace("Lab:\n", "Lab:\narXiv-ID: 2601.15380v2\nDOI: N/A\n")
    old_path = write(note_dir / "old.md", old)
    stripped = write(note_dir / "stripped.md", v3_note())
    res = validator.validate_note(stripped, previous_path=old_path, cli=True)
    assert any("key removed: `arXiv-ID`" in x for x in res.violations)  # the driller must not migrate silently; use fix
    kept = write(note_dir / "kept.md", old)
    res = validator.validate_note(kept, previous_path=old_path, cli=True)
    assert any("KEY-FORBIDDEN" in x and "arXiv-ID" in x for x in res.violations)  # and the old YAML is still invalid


def test_approved_switch_permits_only_switch_keys(note_dir, templates, capsys):
    write(templates / "theory-v1.md", '```json\n{"id":"theory-v1","title":"이론","description":"d","required_h2":["가정","정리","도표"],"visual_section":"도표"}\n```\n\n안내.\n')
    old = v3_note(fm_overrides={"Comment": "원래"})
    switched = v3_note(fm_overrides={"Comment": "원래", "template-id": "theory-v1", "summary-mode": "deep"},
                       h2s=["가정", "정리", "도표", "상세 독해 노트"], visual_h2="도표", begin="<!-- BEGIN AUTO:body template-id=theory-v1 -->\n")
    old_path, new_path = write(note_dir / "old.md", old), write(note_dir / "sw.md", switched)
    assert validator.main(["--path", str(new_path), "--previous", str(old_path)]) == 2
    assert "`template-id` changed — only allowed after an approved template switch" in capsys.readouterr().err
    assert validator.main(["--path", str(new_path), "--previous", str(old_path), "--approved-switch"]) == 0
    assert "update-preservation (approved switch)" in capsys.readouterr().out
    for bad in (switched.replace("Comment: 원래", "Comment: 바뀜"), switched.replace("내 메모", "지워짐"), switched.replace("# 제목", "# 다른 제목", 1)):
        assert validator.main(["--path", str(write(note_dir / "bad.md", bad)), "--previous", str(old_path), "--approved-switch"]) == 2
        capsys.readouterr()
    with pytest.raises(SystemExit):
        validator.main(["--path", str(new_path), "--approved-switch"])
    capsys.readouterr()

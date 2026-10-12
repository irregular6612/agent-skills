#!/usr/bin/env python3
"""
Paper summary format validator for /paper-driller notes (schema v4).

frontmatter 계약은 vault의 공유 엔진 `Public/_tools/paper_frontmatter.py`가 정한다:
`type: paper` 노트는 정확히 13개 키(type, Reading-Status, Read-Depth, Author,
Journal/Conference, Published Year, Topic, Review-Date, Comment, URL, Category,
linked-bases, Lab)만 가진다. 템플릿·수집 범위·도표 확인 같은 driller 내부
메타데이터는 YAML이 아니라 본문의 `<!-- BEGIN DRILLER:meta … END DRILLER:meta -->`
블록(또는 `--meta META.json`)에 둔다.

엔진은 신뢰 위치에서만 로드한다: `$PAPER_FRONTMATTER_TOOLS_DIR` → 설정된 vault
(`$PAPER_VAULT_ROOT` 또는 DEFAULT_VAULT)의 `Public/_tools`. 검사 대상 노트의 상위
디렉터리는 탐색하지 않는다 (임의 저장소의 코드를 import하지 않기 위해).

Two entry modes:

1. Hook mode (no CLI arguments) — reads PostToolUse JSON from stdin, validates the
   file when its frontmatter says `type: paper`. 폴더나 파일명으로 범위를 정하지 않는다.
   (실제 등록되는 훅은 paper-frontmatter-hook.py다. 이 모드는 호환용으로 남긴다.)

2. CLI mode (explicit arguments) — fail-closed.

     --path NOTE.md [--manifest M.json] [--previous OLD.md] [--approved-switch] [--meta META.json]
     --check-template TEMPLATE.md

   stdout always says what was actually checked and what was skipped:
     CHECKED: frontmatter, structure, template:general-v1, visuals
     SKIPPED: visuals (no manifest)

Exit codes:
  0 — not a paper note (hook mode only) OR validation passed
  2 — validation failed; stderr contains a structured FORMAT_VIOLATION block

Note kinds:
  * legacy (no DRILLER:meta, no --meta): frontmatter(엔진) + 최소 구조(H1, 본문 500자) + placeholder.
    enum·형식 검사는 하지 않는다 (옛 값을 거부하지 않는다).
  * driller note (meta 있음): 위에 더해 값 형식(연도·날짜·URL·Category enum), 사람 소유 필드 보호
    (새 노트는 Read-Depth 비움, Reading-Status는 비우거나 Not Started), 템플릿·도표·manifest 검사.
The validator checks consistency; it cannot prove that the manifest itself is
complete or that the source was read correctly.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# Schema / engine loading
# ---------------------------------------------------------------------------

SKILL_REFS = Path.home() / ".claude" / "skills" / "paper-driller" / "references"
SCHEMA_PATH = SKILL_REFS / "paper-schema.json"
# Tests monkeypatch this module constant. There is no environment override.
TEMPLATES_DIR = SKILL_REFS / "templates"
DEFAULT_VAULT = Path(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes"
)
ENGINE_REL = Path("Public") / "_tools" / "paper_frontmatter.py"

_SCHEMA_ERROR: str | None = None
_ENGINE = None
_ENGINE_ERROR: str | None = None


def _no_dup_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out


def _json_loads_strict(text: str):
    return json.loads(text, object_pairs_hook=_no_dup_pairs)


def _load_paper_schema():
    global _SCHEMA_ERROR
    try:
        return _json_loads_strict(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _SCHEMA_ERROR = f"{type(exc).__name__}: {exc}"
        return {}


PAPER_SCHEMA = _load_paper_schema()


def _vault_root() -> Path:
    env = os.environ.get("PAPER_VAULT_ROOT")
    return Path(env).expanduser() if env else DEFAULT_VAULT


def find_engine(start: Path | None = None) -> Path | None:
    """신뢰하는 위치에서만 엔진을 찾는다.

    1. $PAPER_FRONTMATTER_TOOLS_DIR/paper_frontmatter.py (운영자 명시 재정의)
    2. 설정된 vault($PAPER_VAULT_ROOT 또는 DEFAULT_VAULT)의 Public/_tools/paper_frontmatter.py

    검사 대상 노트의 상위 디렉터리는 절대 탐색하지 않는다. 그렇게 하면 임의 저장소의
    Public/_tools/paper_frontmatter.py를 이 프로세스 권한으로 import하게 된다.
    `start`는 호환용 인자이며 무시한다.
    """
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
    """(engine module or None, error). 한 번 로드하면 캐시한다."""
    global _ENGINE, _ENGINE_ERROR
    if _ENGINE is not None:
        return _ENGINE, None
    if "paper_frontmatter" in sys.modules and getattr(sys.modules["paper_frontmatter"], "PAPER_KEYS", None):
        _ENGINE = sys.modules["paper_frontmatter"]
        return _ENGINE, None
    path = find_engine(start)
    if path is None:
        _ENGINE_ERROR = "paper_frontmatter.py 엔진을 찾을 수 없다 (PAPER_FRONTMATTER_TOOLS_DIR 또는 vault의 Public/_tools)"
        return None, _ENGINE_ERROR
    try:
        spec = importlib.util.spec_from_file_location("paper_frontmatter", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules["paper_frontmatter"] = mod
        spec.loader.exec_module(mod)
    except Exception as exc:
        _ENGINE_ERROR = f"엔진 로드 실패 {path}: {type(exc).__name__}: {exc}"
        return None, _ENGINE_ERROR
    if not mod._yaml_available():
        _ENGINE_ERROR = f"PyYAML이 없다 (interpreter={sys.executable})"
        return None, _ENGINE_ERROR
    _ENGINE = mod
    return mod, None


_FM_SCHEMA = PAPER_SCHEMA.get("frontmatter", {}) if isinstance(PAPER_SCHEMA.get("frontmatter"), dict) else {}
PAPER_KEYS = tuple(_FM_SCHEMA.get("keys", [
    "type", "Reading-Status", "Read-Depth", "Author", "Journal/Conference", "Published Year",
    "Topic", "Review-Date", "Comment", "URL", "Category", "linked-bases", "Lab",
]))
FM_UPDATE_ALLOWLIST = set(_FM_SCHEMA.get("controlled_update_fields", ["Review-Date"]))
HUMAN_OWNED = tuple(_FM_SCHEMA.get("human_owned", ["Reading-Status", "Read-Depth"]))

_META_SCHEMA = PAPER_SCHEMA.get("driller_meta", {}) if isinstance(PAPER_SCHEMA.get("driller_meta"), dict) else {}
META_BEGIN = str(_META_SCHEMA.get("block_begin", "<!-- BEGIN DRILLER:meta"))
META_END = str(_META_SCHEMA.get("block_end", "END DRILLER:meta -->"))
META_RE = re.compile(re.escape(META_BEGIN) + r"[ \t]*\n(.*?)\n[ \t]*" + re.escape(META_END), re.DOTALL)
META_KEYS_ALL = set(
    _META_SCHEMA.get("note_v3", []) + _META_SCHEMA.get("preread_v2", []) + _META_SCHEMA.get("optional", [])
) or {
    "template-version", "template-id", "summary-mode", "profile", "source-coverage", "quality-status",
    "visual-check", "visual-scope", "visual-scope-note", "reading-decision", "decision-confidence", "audience-level",
}
META_UPDATE_ALLOWLIST = set(_META_SCHEMA.get("controlled_update_fields", [
    "source-coverage", "quality-status", "visual-check", "visual-scope", "visual-scope-note",
    "reading-decision", "decision-confidence",
]))
SWITCH_ONLY_KEYS = tuple(_META_SCHEMA.get("switch_only_fields", ["template-version", "template-id", "summary-mode"]))
PREREAD_V2_REQUIRED_KEYS = tuple(_META_SCHEMA.get("preread_v2", [
    "template-version", "summary-mode", "profile", "source-coverage", "quality-status",
    "reading-decision", "decision-confidence",
]))
NOTE_V3_REQUIRED_KEYS = tuple(_META_SCHEMA.get("note_v3", [
    "template-version", "template-id", "summary-mode", "profile", "source-coverage",
    "quality-status", "visual-check", "visual-scope",
]))

VALID_CATEGORIES = set(PAPER_SCHEMA.get("categories", [
    "Architecture", "Training", "Benchmark/Evaluation", "Application", "Reasoning",
    "Survey", "Dataset", "Optimization", "Theory", "AGI",
]))
VALID_READING_STATUS = set(PAPER_SCHEMA.get("reading_status", ["✅ Done", "▶️ In progress", "☑️ Not Started", "Not Started"]))
NOT_STARTED_STATUS = {"☑️ Not Started", "Not Started"}

# Structure requirements are intentionally lenient: any top-level H1 plus a
# non-trivial body counts as a real paper note.
MIN_BODY_CHARS = 500
MIN_H2_HEADINGS = 0
PREREAD_V2_HEADINGS = tuple(
    PAPER_SCHEMA.get("templates", {}).get("paper-preread-v2", {}).get(
        "required_h2", ["읽기 판단", "핵심 아이디어", "무엇을 했나", "핵심 근거", "어디까지 믿을까", "원문 읽기 지도"]
    )
)
PREREAD_V2_MAX_BODY_CHARS = int(
    PAPER_SCHEMA.get("templates", {}).get("paper-preread-v2", {}).get("max_body_non_whitespace_chars", 5500)
)
VALID_READING_DECISIONS = set(PAPER_SCHEMA.get("reading_decisions", ["read", "skim", "skip"]))
VALID_DECISION_CONFIDENCE = set(PAPER_SCHEMA.get("decision_confidence", ["high", "medium", "low"]))
VALID_SOURCE_COVERAGE = set(PAPER_SCHEMA.get("source_coverage", ["fulltext", "section-extract", "abstract-only", "unknown"]))
VALID_SUMMARY_MODES = set(PAPER_SCHEMA.get("summary_modes", ["preread", "deep"]))
VALID_QUALITY_STATUS = set(PAPER_SCHEMA.get("quality_status", ["inbox", "draft", "review", "ready", "archived"]))

# ---- paper-note-v3 -------------------------------------------------------

NOTE_V3 = "paper-note-v3"
DEEP_V2 = "paper-deep-v2"
KNOWN_TEMPLATE_VERSIONS = set(
    PAPER_SCHEMA.get("template_versions", ["paper-preread-v2", DEEP_V2, NOTE_V3])
) | {"paper-preread-v2", DEEP_V2, NOTE_V3}
_V3_SCHEMA = PAPER_SCHEMA.get("templates", {}).get(NOTE_V3, {})
DEEP_EXTRA_H2 = str(_V3_SCHEMA.get("deep_extra_h2", "상세 독해 노트"))
V3_ONLY_KEYS = ("template-id", "visual-check", "visual-scope", "visual-scope-note")
VALID_VISUAL_CHECK = set(PAPER_SCHEMA.get("visual_check", ["viewed", "caption-only", "mixed", "none", "unverified"]))
VALID_VISUAL_SCOPE = set(PAPER_SCHEMA.get("visual_scope", ["main-body", "user-narrowed"]))

MANIFEST_VERSION = 1
MANIFEST_SCAN = {"complete", "partial"}
MANIFEST_EVIDENCE = {"viewed", "caption-only", "not-seen"}
MANIFEST_DOC_KINDS = {"arxiv", "doi", "url"}
MANIFEST_TOP_KEYS = {"manifest_version", "doc_id", "doc_version", "source", "scan", "scan_note", "items", "scope"}
MANIFEST_TOP_REQUIRED = ("manifest_version", "doc_id", "source", "scan", "items")
MANIFEST_ITEM_KEYS = {"id", "main_body", "evidence", "caption", "locator", "note"}
MANIFEST_ITEM_REQUIRED = ("id", "main_body", "evidence")

TEMPLATE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
TEMPLATE_META_KEYS = {"id", "title", "description", "required_h2", "optional_h2", "visual_section"}
TEMPLATE_META_REQUIRED = ("id", "title", "description", "required_h2", "visual_section")
TEMPLATE_META_RE = re.compile(r"^```json[ \t]*\n(.*?)\n```[ \t]*$", re.DOTALL | re.MULTILINE)

AUTO_BEGIN_RE = re.compile(r"^<!-- BEGIN AUTO:body(?: template-id=([^\s>]+))? -->[ \t]*$", re.MULTILINE)
AUTO_END_RE = re.compile(r"^<!-- END AUTO:body -->[ \t]*$", re.MULTILINE)
ANY_AUTO_MARKER_RE = re.compile(r"<!-- (?:BEGIN|END) AUTO:", re.MULTILINE)
USER_BLOCK_RE = re.compile(r"<!-- BEGIN USER:([A-Za-z0-9_-]+) -->.*?<!-- END USER:\1 -->", re.DOTALL)
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
H2_RE = re.compile(r"(?m)^## (.+?)\s*$")
H3_RE = re.compile(r"(?m)^### (.+?)\s*$")
VISUAL_ID_SEPARATORS = (" — ", " – ", " - ", ": ", "：")
ARXIV_ID_RE = re.compile(r"^([a-z\-]+(?:\.[a-z]{2})?/\d{7}|\d{4}\.\d{4,5})(v\d+)?$")
ARXIV_VERSION_RE = re.compile(r"^v\d+$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
ITEM_EVIDENCE_RE = re.compile(r"확인 상태\**\s*[:：]\s*\**\s*`?(viewed|caption-only|not-seen)`?", re.IGNORECASE)

PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\[작성 필요\]"),
    re.compile(r"\[내용\]"),
]

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


# ---------------------------------------------------------------------------
# Frontmatter parsing (minimal string view; schema checks use the engine)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, None
    raw = match.group(1)
    body_start = match.end()
    data = {}
    current_key = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t", "-")) and current_key is not None:
            if isinstance(data[current_key], list):
                data[current_key].append(line.strip().lstrip("- "))
            else:
                data[current_key] = [data[current_key], line.strip().lstrip("- ")]
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key in data:
                data.setdefault("__duplicates__", []).append(key)
            data[key] = value.strip('"').strip("'") if value else []
            current_key = key
    return data, body_start


def _fm_str(fm: dict, key: str) -> str:
    value = fm.get(key, "")
    if isinstance(value, list):
        return ""
    return str(value).strip()


def raw_frontmatter_segments(text: str):
    """{key: raw YAML segment} — the key line plus its continuation lines, verbatim."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    segments: dict[str, str] = {}
    current_key = None
    for line in match.group(1).splitlines():
        starts_key = line and not line.startswith((" ", "\t", "-", "#")) and ":" in line
        if starts_key:
            current_key = line.partition(":")[0].strip()
            segments[current_key] = segments.get(current_key, "") + line + "\n"
        elif current_key is not None:
            segments[current_key] += line + "\n"
    return segments


# ---------------------------------------------------------------------------
# DRILLER:meta block (body-side metadata for generated notes)
# ---------------------------------------------------------------------------

def find_meta_blocks(body: str):
    spans = _fence_spans(body)
    return _outside_fences(META_RE.finditer(body), spans)


def parse_meta_text(inner: str):
    """key: value 줄 → dict. 자료형은 모두 문자열이다. 오류는 목록으로."""
    meta: dict[str, str] = {}
    errors: list[str] = []
    for line in inner.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line or line.startswith((" ", "\t")):
            errors.append(f"META: 지원하지 않는 줄 `{line.strip()[:40]}` (한 줄 `key: value`만)")
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key in meta:
            errors.append(f"META: duplicate key `{key}`")
        meta[key] = value
    return meta, errors


def parse_driller_meta(body: str):
    """(meta_or_None, errors). 블록이 없으면 (None, [])."""
    blocks = find_meta_blocks(body)
    if not blocks:
        return None, []
    if len(blocks) > 1:
        return None, [f"META: DRILLER:meta 블록은 정확히 하나여야 한다 (found {len(blocks)})"]
    meta, errors = parse_meta_text(blocks[0].group(1))
    begins, _ = find_auto_markers(body)
    if begins and blocks[0].start() > begins[0].start():
        errors.append("META: DRILLER:meta 블록은 AUTO:body 앞에 있어야 한다")
    unknown = sorted(set(meta) - META_KEYS_ALL)
    if unknown:
        errors.append(f"META: unknown keys in DRILLER:meta: {unknown}")
    return meta, errors


def load_meta_file(path: Path):
    try:
        raw = _json_loads_strict(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, [f"META: cannot read --meta `{path}` — {exc}"]
    if not isinstance(raw, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items()):
        return None, ["META: --meta must be a JSON object of string values"]
    unknown = sorted(set(raw) - META_KEYS_ALL)
    return raw, ([f"META: unknown keys in --meta: {unknown}"] if unknown else [])


# ---------------------------------------------------------------------------
# Template files (references/templates/{id}.md)
# ---------------------------------------------------------------------------

def parse_template_metadata(text: str):
    errors: list[str] = []
    match = TEMPLATE_META_RE.search(text)
    if not match:
        return None, ["TEMPLATE: no leading ```json metadata block"]
    try:
        meta = _json_loads_strict(match.group(1))
    except ValueError as exc:
        return None, [f"TEMPLATE: metadata JSON invalid — {exc}"]
    if not isinstance(meta, dict):
        return None, ["TEMPLATE: metadata must be a JSON object"]
    unknown = sorted(set(meta) - TEMPLATE_META_KEYS)
    if unknown:
        errors.append(f"TEMPLATE: unknown metadata keys: {unknown}")
    for key in TEMPLATE_META_REQUIRED:
        if key not in meta:
            errors.append(f"TEMPLATE: metadata missing `{key}`")
    for key in ("id", "title", "description", "visual_section"):
        value = meta.get(key)
        if key in meta and (not isinstance(value, str) or not value.strip()):
            errors.append(f"TEMPLATE: `{key}` must be a non-empty string")
    if isinstance(meta.get("id"), str) and not TEMPLATE_ID_RE.match(meta["id"]):
        errors.append(f"TEMPLATE: id `{meta['id']}` must match {TEMPLATE_ID_RE.pattern}")
    lists: dict[str, list[str] | None] = {"required_h2": None, "optional_h2": None}
    for key in lists:
        if key not in meta:
            continue
        value = meta[key]
        if not isinstance(value, list) or not all(isinstance(h, str) and h.strip() for h in value):
            errors.append(f"TEMPLATE: `{key}` must be a list of non-empty strings")
            continue
        if len(set(value)) != len(value):
            errors.append(f"TEMPLATE: `{key}` contains duplicate headings")
        lists[key] = value
    req, opt = lists["required_h2"], lists["optional_h2"]
    if req is not None and not req:
        errors.append("TEMPLATE: `required_h2` must not be empty")
    if req is not None and opt is not None and set(req) & set(opt):
        errors.append("TEMPLATE: a heading cannot be both required and optional")
    if req is not None and isinstance(meta.get("visual_section"), str) and meta["visual_section"] not in req:
        errors.append("TEMPLATE: `visual_section` must be one of `required_h2`")
    guidance = text[match.end():].strip()
    if not guidance:
        errors.append("TEMPLATE: no writing guidance after the metadata block")
    return meta, errors


def check_template_file(path: Path):
    errors: list[str] = []
    path = Path(path)
    if not path.exists():
        return None, [f"TEMPLATE: file not found: {path}"]
    if path.is_symlink():
        errors.append(f"TEMPLATE: symbolic links are not allowed: {path}")
    if not path.is_file():
        return None, errors + [f"TEMPLATE: not a regular file: {path}"]
    if path.suffix != ".md":
        errors.append("TEMPLATE: file must end with .md")
    try:
        expected = (TEMPLATES_DIR.resolve() / path.name)
        if path.resolve() != expected or path.parent.resolve() != TEMPLATES_DIR.resolve():
            errors.append(f"TEMPLATE: file must live directly inside {TEMPLATES_DIR} (no traversal, no symlink)")
    except OSError as exc:
        errors.append(f"TEMPLATE: cannot resolve path — {exc}")
    if not TEMPLATE_ID_RE.match(path.stem):
        errors.append(f"TEMPLATE: filename `{path.stem}` must match {TEMPLATE_ID_RE.pattern}")
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, errors + [f"TEMPLATE: cannot read as UTF-8 — {exc}"]
    meta, meta_errors = parse_template_metadata(text)
    errors.extend(meta_errors)
    if meta is not None and isinstance(meta.get("id"), str) and meta["id"] != path.stem:
        errors.append(f"TEMPLATE: metadata id `{meta['id']}` != filename `{path.stem}`")
    return (meta if not errors else None), errors


def load_template(template_id: str):
    if not TEMPLATE_ID_RE.match(template_id or ""):
        return None, [f"TEMPLATE: template-id `{template_id}` must match {TEMPLATE_ID_RE.pattern}"]
    return check_template_file(TEMPLATES_DIR / f"{template_id}.md")


# ---------------------------------------------------------------------------
# AUTO body extraction and heading helpers
# ---------------------------------------------------------------------------

def _fence_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in FENCE_RE.finditer(text)]


def _outside_fences(matches, spans):
    return [m for m in matches if not any(a <= m.start() < b for a, b in spans)]


def find_auto_markers(body: str):
    spans = _fence_spans(body)
    return (
        _outside_fences(AUTO_BEGIN_RE.finditer(body), spans),
        _outside_fences(AUTO_END_RE.finditer(body), spans),
    )


def extract_auto_body(body: str):
    begins, ends = find_auto_markers(body)
    errors: list[str] = []
    if len(begins) != 1:
        errors.append(f"MARKER: expected exactly one `<!-- BEGIN AUTO:body ... -->`, found {len(begins)}")
    if len(ends) != 1:
        errors.append(f"MARKER: expected exactly one `<!-- END AUTO:body -->`, found {len(ends)}")
    if errors:
        return None, None, errors
    begin, end = begins[0], ends[0]
    if end.start() < begin.end():
        return None, None, ["MARKER: `END AUTO:body` appears before `BEGIN AUTO:body`"]
    inner = body[begin.end():end.start()]
    if ANY_AUTO_MARKER_RE.search(FENCE_RE.sub("", inner)):
        return None, None, ["MARKER: nested AUTO marker inside AUTO:body"]
    return inner, begin.group(1), []


def strip_ignored(text: str) -> str:
    return USER_BLOCK_RE.sub("", FENCE_RE.sub("", text))


def h2_headings(text: str) -> list[str]:
    return [m.group(1).strip() for m in H2_RE.finditer(text)]


def section_text(text: str, heading: str) -> str | None:
    match = re.search(rf"(?m)^## {re.escape(heading)}\s*$", text)
    if not match:
        return None
    rest = text[match.end():]
    nxt = re.search(r"(?m)^## ", rest)
    return rest[: nxt.start()] if nxt else rest


def _visual_id(title: str) -> str:
    for sep in VISUAL_ID_SEPARATORS:
        if sep in title:
            return title.split(sep, 1)[0].strip()
    return title


def visual_h3_ids(section: str) -> list[str]:
    return [_visual_id(m.group(1).strip()) for m in H3_RE.finditer(section)]


def visual_h3_entries(section: str) -> list[tuple[str, str]]:
    matches = list(H3_RE.finditer(section))
    entries = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        entries.append((_visual_id(m.group(1).strip()), section[m.end():end]))
    return entries


def check_required_h2(auto_text: str, meta: dict) -> list[str]:
    violations: list[str] = []
    found = h2_headings(strip_ignored(auto_text))
    required = list(meta.get("required_h2", []))
    for heading in required:
        n = found.count(heading)
        if n == 0:
            violations.append(f"STRUCTURE: required section missing inside AUTO:body: `## {heading}`")
        elif n > 1:
            violations.append(f"STRUCTURE: required section duplicated: `## {heading}` ×{n}")
    positions = [found.index(h) for h in required if h in found]
    if positions != sorted(positions):
        violations.append("STRUCTURE: required sections out of template order — expected " + " → ".join(required))
    return violations


# ---------------------------------------------------------------------------
# Identity (URL is the only source identifier in frontmatter)
# ---------------------------------------------------------------------------

def _split_arxiv(value: str):
    value = value.strip().lower()
    if value.startswith("arxiv:"):
        value = value[len("arxiv:"):]
    m = ARXIV_ID_RE.match(value)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def _norm_doi(value: str):
    v = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:"):
        if v.startswith(prefix):
            v = v[len(prefix):]
    v = v.strip("/")
    return v if DOI_RE.match(v) else None


def _norm_url(value: str):
    """Conservative URL identity, or None when the value is not an http(s) URL."""
    value = value.strip()
    if any(ch.isspace() for ch in value):
        return None
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not hostname:
        return None
    host = hostname.lower()
    if host.startswith("www."):
        host = host[len("www."):]
    if ":" in host:
        host = f"[{host}]"
    if port is not None:
        host = f"{host}:{port}"
    path = parts.path.removesuffix("/") or "/"
    return host + path + (f"?{parts.query}" if parts.query else "")


_ARXIV_PATH_RE = re.compile(r"^/(?:abs|pdf|html)/(.+?)(?:\.pdf)?/?$", re.IGNORECASE)


def derive_doc_ids(fm: dict) -> dict:
    """{'url': (norm, None), 'arxiv': (base, ver)?, 'doi': (id, None)?} — 모두 URL에서 유도한다.

    A malformed URL is reported under `__invalid__` so binding can name it.
    """
    out: dict = {}
    url = _fm_str(fm, "URL")
    if not url or url.upper() == "N/A":
        return out
    norm = _norm_url(url)
    if norm is None:
        out["__invalid__"] = {"url": url}
        return out
    out["url"] = (norm, None)
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in ("arxiv.org", "export.arxiv.org"):
        m = _ARXIV_PATH_RE.match(parts.path)
        if m:
            base, ver = _split_arxiv(m.group(1))
            if base:
                out["arxiv"] = (base, ver)
    elif host in ("doi.org", "dx.doi.org"):
        doi = _norm_doi(url)
        if doi:
            out["doi"] = (doi, None)
    return out


# ---------------------------------------------------------------------------
# Manifest (source-derived list of figures/tables)
# ---------------------------------------------------------------------------

def load_manifest(path: Path):
    path = Path(path)
    try:
        raw = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, [f"MANIFEST: cannot read `{path}` — {exc}"]
    try:
        m = _json_loads_strict(raw)
    except ValueError as exc:
        return None, [f"MANIFEST: invalid JSON — {exc}"]
    errors: list[str] = []
    if not isinstance(m, dict):
        return None, ["MANIFEST: top level must be a JSON object"]
    unknown = sorted(set(m) - MANIFEST_TOP_KEYS)
    if unknown:
        errors.append(f"MANIFEST: unknown top-level keys: {unknown}")
    for key in MANIFEST_TOP_REQUIRED:
        if key not in m:
            errors.append(f"MANIFEST: missing required key `{key}`")
    mv = m.get("manifest_version")
    if type(mv) is not int or mv != MANIFEST_VERSION:
        errors.append(f"MANIFEST: manifest_version must be the integer {MANIFEST_VERSION} (got {mv!r})")
    doc_version = m.get("doc_version")
    if "doc_version" in m and (not isinstance(doc_version, str) or not doc_version.strip()):
        errors.append("MANIFEST: doc_version must be a non-empty string when present")
        doc_version = None
    doc_id = m.get("doc_id")
    if not isinstance(doc_id, str) or ":" not in doc_id:
        errors.append("MANIFEST: doc_id must be a string `kind:value` (kind = arxiv|doi|url)")
    else:
        kind, _, value = doc_id.partition(":")
        if kind not in MANIFEST_DOC_KINDS:
            errors.append(f"MANIFEST: doc_id kind `{kind}` must be one of {sorted(MANIFEST_DOC_KINDS)}")
        if not value.strip():
            errors.append("MANIFEST: doc_id value is empty")
        elif kind == "arxiv":
            base, embedded_ver = _split_arxiv(value)
            if base is None:
                errors.append(f"MANIFEST: doc_id `{doc_id}` is not a valid arXiv identifier")
            if isinstance(doc_version, str) and doc_version.strip():
                dv = doc_version.strip().lower()
                if not ARXIV_VERSION_RE.match(dv):
                    errors.append(f"MANIFEST: doc_version `{doc_version}` must look like `v2` for an arXiv doc_id")
                elif embedded_ver and embedded_ver != dv:
                    errors.append(f"MANIFEST: doc_id `{doc_id}` embeds version {embedded_ver} but doc_version says {doc_version} — contradictory")
        elif kind == "doi" and _norm_doi(value) is None:
            errors.append(f"MANIFEST: doc_id `{doc_id}` is not a valid DOI (expected 10.xxxx/suffix)")
        elif kind == "url" and _norm_url(value) is None:
            errors.append(f"MANIFEST: doc_id `{doc_id}` is not a valid http(s) URL")
    if not isinstance(m.get("source"), str) or not m.get("source", "").strip():
        errors.append("MANIFEST: source must be a non-empty string (a record, never a command)")
    scan = m.get("scan")
    if not isinstance(scan, str) or scan not in MANIFEST_SCAN:
        errors.append(f"MANIFEST: scan must be one of {sorted(MANIFEST_SCAN)} (got {scan!r})")
    if "scan_note" in m and not isinstance(m["scan_note"], str):
        errors.append("MANIFEST: scan_note must be a string")
    if scan == "partial" and not str(m.get("scan_note", "")).strip():
        errors.append("MANIFEST: scan=partial requires a non-empty scan_note")
    items = m.get("items")
    if not isinstance(items, list):
        errors.append("MANIFEST: items must be a list")
        items = []
    seen_ids: set[str] = set()
    for i, item in enumerate(items):
        where = f"items[{i}]"
        if not isinstance(item, dict):
            errors.append(f"MANIFEST: {where} must be an object")
            continue
        unknown = sorted(set(item) - MANIFEST_ITEM_KEYS)
        if unknown:
            errors.append(f"MANIFEST: {where} unknown keys: {unknown}")
        for key in MANIFEST_ITEM_REQUIRED:
            if key not in item:
                errors.append(f"MANIFEST: {where} missing `{key}`")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"MANIFEST: {where} id must be a non-empty string")
        elif item_id.strip() != item_id:
            errors.append(f"MANIFEST: {where} id has leading/trailing whitespace")
        elif item_id in seen_ids:
            errors.append(f"MANIFEST: duplicate item id `{item_id}`")
        else:
            seen_ids.add(item_id)
        mb = item.get("main_body")
        if not (mb is True or mb is False or mb == "unsure"):
            errors.append(f"MANIFEST: {where} main_body must be true, false or \"unsure\" (got {mb!r})")
        ev = item.get("evidence")
        if not isinstance(ev, str) or ev not in MANIFEST_EVIDENCE:
            errors.append(f"MANIFEST: {where} evidence must be one of {sorted(MANIFEST_EVIDENCE)} (got {ev!r})")
        for key in ("caption", "locator", "note"):
            if key in item and not isinstance(item[key], str):
                errors.append(f"MANIFEST: {where} `{key}` must be a string")
    scope = m.get("scope")
    if scope is not None:
        if not isinstance(scope, dict):
            errors.append("MANIFEST: scope must be an object")
        else:
            unknown = sorted(set(scope) - {"requested_by_user", "include"})
            if unknown:
                errors.append(f"MANIFEST: scope unknown keys: {unknown}")
            if not isinstance(scope.get("requested_by_user"), str) or not scope["requested_by_user"].strip():
                errors.append("MANIFEST: scope.requested_by_user must quote the user's actual request")
            inc = scope.get("include")
            if not isinstance(inc, list) or not inc or not all(isinstance(x, str) for x in inc):
                errors.append("MANIFEST: scope.include must be a non-empty list of item ids")
            else:
                if len(set(inc)) != len(inc):
                    errors.append("MANIFEST: scope.include has duplicates")
                for x in inc:
                    if x not in seen_ids:
                        errors.append(f"MANIFEST: scope.include references unknown item `{x}`")
    return (m if not errors else None), errors


def check_manifest_binding(manifest: dict, fm: dict) -> list[str]:
    """The manifest must describe the same paper (and version) as the note's URL."""
    doc_id = manifest.get("doc_id")
    if not isinstance(doc_id, str) or ":" not in doc_id:
        return ["MANIFEST: doc_id must be a string `kind:value` (kind = arxiv|doi|url)"]
    kind, _, value = doc_id.partition(":")
    if kind not in MANIFEST_DOC_KINDS:
        return [f"MANIFEST: doc_id kind `{kind}` must be one of {sorted(MANIFEST_DOC_KINDS)}"]
    note_ids = derive_doc_ids(fm)
    invalid = note_ids.get("__invalid__", {})
    if "url" in invalid:
        return [f"MANIFEST: note URL `{invalid['url']}` is not a valid url identifier — cannot bind"]
    if kind not in note_ids:
        return [f"MANIFEST: doc_id kind `{kind}` cannot be matched — note URL does not yield a `{kind}` identifier"]
    note_base, note_ver = note_ids[kind]
    doc_version = manifest.get("doc_version")
    m_ver = doc_version.strip().lower() if isinstance(doc_version, str) and doc_version.strip() else None
    if kind == "arxiv":
        m_base, embedded = _split_arxiv(value)
        if embedded and m_ver and embedded != m_ver:
            return [f"MANIFEST: doc_id `{doc_id}` embeds version {embedded} but doc_version says {doc_version} — contradictory"]
        m_ver = embedded or m_ver
    elif kind == "doi":
        m_base = _norm_doi(value)
    else:
        m_base = _norm_url(value)
    if m_base is None:
        return [f"MANIFEST: doc_id `{doc_id}` is not a valid {kind} identifier"]
    if m_base != note_base:
        return [f"MANIFEST: doc_id `{doc_id}` does not match the note ({kind}: {note_base})"]
    if m_ver and note_ver and m_ver != str(note_ver).lower():
        return [f"MANIFEST: version mismatch — manifest {m_ver}, note {note_ver}"]
    return []


def _quote_norm(text: str) -> str:
    t = " ".join(str(text).split())
    while len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'“”‘’":
        t = t[1:-1].strip()
    return t


def manifest_targets(manifest: dict) -> list[dict]:
    scope = manifest.get("scope")
    if scope:
        wanted = set(scope["include"])
        return [it for it in manifest["items"] if it["id"] in wanted]
    return [it for it in manifest["items"] if it["main_body"] in (True, "unsure")]


def expected_visual_check(manifest: dict) -> str:
    targets = manifest_targets(manifest)
    if not targets:
        return "none" if (manifest["scan"] == "complete" and not manifest.get("scope")) else "unverified"
    ev = {t["evidence"] for t in targets}
    if "not-seen" in ev:
        return "unverified"
    if ev == {"viewed"}:
        return "viewed"
    if ev == {"caption-only"}:
        return "caption-only"
    return "mixed"


def ready_allowed_by_manifest(manifest: dict) -> bool:
    targets = manifest_targets(manifest)
    return (
        manifest["scan"] == "complete"
        and all(t["main_body"] is True for t in targets)
        and expected_visual_check(manifest) in ("viewed", "none")
    )


def check_visuals(auto_text: str, meta: dict, manifest: dict, fm: dict, dmeta: dict) -> list[str]:
    violations = check_manifest_binding(manifest, fm)
    if violations:
        return violations
    section = section_text(strip_ignored(auto_text), meta["visual_section"])
    if section is None:
        return [f"VISUALS: visual section `## {meta['visual_section']}` not found inside AUTO:body"]
    entries = visual_h3_entries(section)
    found = [e[0] for e in entries]
    target_items = manifest_targets(manifest)
    targets = [t["id"] for t in target_items]
    evidence_of = {t["id"]: t["evidence"] for t in target_items}
    for tid in targets:
        n = found.count(tid)
        if n == 0:
            violations.append(f"VISUALS: main-body item missing from note: `### {tid}`")
        elif n > 1:
            violations.append(f"VISUALS: item described more than once: `### {tid}` ×{n}")
    for fid, body_text in entries:
        if fid not in targets:
            violations.append(f"VISUALS: note describes `### {fid}` which is not a manifest target (appendix, non-main or unknown)")
            continue
        if not body_text.strip():
            violations.append(f"VISUALS: `### {fid}` has no description — an empty heading does not count as explained")
        stated = {m.group(1).lower() for m in ITEM_EVIDENCE_RE.finditer(body_text)}
        if stated and stated != {evidence_of[fid]}:
            violations.append(f"VISUALS: `### {fid}` states 확인 상태 {sorted(stated)} but manifest evidence is `{evidence_of[fid]}`")
    ordered = [f for f in found if f in targets]
    if not violations and ordered != targets:
        violations.append("VISUALS: items are not in source order — expected " + ", ".join(targets))
    expected = expected_visual_check(manifest)
    actual = _fm_str(dmeta, "visual-check")
    if actual != expected:
        violations.append(f"VISUALS: visual-check=`{actual}` but manifest implies `{expected}`")
    scope = manifest.get("scope")
    vscope = _fm_str(dmeta, "visual-scope")
    if scope and vscope != "user-narrowed":
        violations.append("VISUALS: manifest has a user scope but visual-scope is not `user-narrowed`")
    if not scope and vscope == "user-narrowed":
        violations.append("VISUALS: visual-scope=`user-narrowed` but manifest records no user scope")
    if scope:
        requested = _quote_norm(scope.get("requested_by_user", "")) if isinstance(scope, dict) else ""
        note_request = _quote_norm(_fm_str(dmeta, "visual-scope-note"))
        if requested != note_request:
            violations.append(
                "VISUALS: visual-scope-note must quote the same request as manifest scope.requested_by_user "
                f"(note: `{note_request}`, manifest: `{requested}`)"
            )
    if _fm_str(dmeta, "quality-status") == "ready" and not ready_allowed_by_manifest(manifest):
        violations.append("VISUALS: quality-status=`ready` not allowed — needs scan=complete, every target main_body=true and evidence=viewed")
    return violations


# ---------------------------------------------------------------------------
# Update preservation (controlled field allowlist, USER/outside content)
# ---------------------------------------------------------------------------

def _outside_auto(text: str):
    """(raw fm segments, meta dict or None, body with AUTO block and META block collapsed) or (segs, meta, None)."""
    segs = raw_frontmatter_segments(text)
    _, body_start = parse_frontmatter(text)
    body = text[body_start:] if body_start else text
    dmeta, _ = parse_driller_meta(body)
    for m in reversed(find_meta_blocks(body)):
        body = body[: m.start()] + "<DRILLER:meta>" + body[m.end():]
    begins, ends = find_auto_markers(body)
    if len(begins) != 1 or len(ends) != 1 or ends[0].start() < begins[0].end():
        return segs, dmeta, None
    return segs, dmeta, body[: begins[0].start()] + "<AUTO:body>" + body[ends[0].end():]


def check_update_preservation(old_text: str, new_text: str, approved_switch: bool = False) -> list[str]:
    """What an automatic re-run may change. Everything else must survive verbatim.

    Frontmatter: raw YAML segment per key; only FM_UPDATE_ALLOWLIST (Review-Date) may change.
    DRILLER:meta: META_UPDATE_ALLOWLIST may change; switch-only keys need approved_switch.
    """
    violations: list[str] = []
    old_segs, old_meta, old_outside = _outside_auto(old_text)
    new_segs, new_meta, new_outside = _outside_auto(new_text)
    if old_segs is None:
        return ["UPDATE: previous note has no frontmatter — propose a diff, do not rewrite"]
    if old_outside is None:
        return [
            "UPDATE: previous note has no well-formed AUTO:body markers — legacy note: "
            "propose a diff and get approval, never rewrite wholesale"
        ]
    if new_segs is None or new_outside is None:
        return ["UPDATE: new note lost its frontmatter or AUTO:body markers"]
    for key, old_raw in old_segs.items():
        if key not in new_segs:
            violations.append(f"UPDATE: frontmatter key removed: `{key}`")
        elif new_segs[key] != old_raw and key not in FM_UPDATE_ALLOWLIST:
            violations.append(f"UPDATE: `{key}` changed (raw YAML differs) but is not in the controlled update allowlist")
    old_meta = old_meta or {}
    new_meta = new_meta or {}
    for key, old_val in old_meta.items():
        if key not in new_meta:
            violations.append(f"UPDATE: DRILLER:meta key removed: `{key}`")
        elif new_meta[key] != old_val and key not in META_UPDATE_ALLOWLIST:
            if key in SWITCH_ONLY_KEYS:
                if not approved_switch:
                    violations.append(f"UPDATE: `{key}` changed — only allowed after an approved template switch (--approved-switch)")
            else:
                violations.append(f"UPDATE: DRILLER:meta `{key}` changed but is not in the controlled update allowlist")
    for key in new_meta:
        if key not in old_meta:
            if key in SWITCH_ONLY_KEYS and not approved_switch:
                violations.append(f"UPDATE: `{key}` added — only allowed after an approved template switch (--approved-switch)")
            elif key not in META_UPDATE_ALLOWLIST and key not in SWITCH_ONLY_KEYS:
                violations.append(f"UPDATE: DRILLER:meta `{key}` added but is not in the controlled update allowlist")
    for block in USER_BLOCK_RE.finditer(old_text):
        if block.group(0) not in new_text:
            violations.append(f"UPDATE: USER block `{block.group(1)}` was altered or removed")
    if old_outside != new_outside:
        violations.append("UPDATE: content outside AUTO:body changed (H1 title, USER blocks and other user-owned text must stay verbatim)")
    return violations


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def in_scope(path: Path, fm: dict | None = None) -> bool:
    """In scope iff frontmatter declares `type: paper`. Paths never decide scope."""
    return fm is not None and str(fm.get("type", "")).strip() == "paper"


class Result:
    def __init__(self):
        self.violations: list[str] = []
        self.warnings: list[str] = []
        self.checked: list[str] = []
        self.skipped: list[str] = []


def _engine_frontmatter_check(res: Result, text: str, path: Path, cli: bool) -> str:
    """엔진으로 frontmatter 계약을 검사한다. 노트 kind를 돌려준다 (paper|paper-broken|...|engine-missing)."""
    engine, err = load_engine(path)
    if engine is None:
        res.violations.append(f"SCHEMA: frontmatter 엔진을 쓸 수 없다 — {err} (fail-closed)")
        return "engine-missing"
    info = engine.classify_text(text)
    if info.kind == "paper":
        for issue in engine.validate_paper(info.parsed):
            res.violations.append(f"FRONTMATTER: {issue}")
        for issue in info.encoding_issues:
            res.violations.append(f"FRONTMATTER: {issue}")
    elif info.kind == "paper-broken":
        for issue in list(info.issues) + list(info.encoding_issues):
            res.violations.append(f"FRONTMATTER: {issue}")
    elif cli:
        res.violations.append(f"FRONTMATTER: kind={info.kind} — CLI check requires `type: paper`")
    return info.kind


def validate_note(
    path: Path, manifest_path=None, previous_path=None, cli: bool = False,
    approved_switch: bool = False, meta_path=None,
) -> Result:
    """Full validation. `cli=True` is fail-closed (missing file, bad type, etc. are violations)."""
    res = Result()
    violations, warnings = res.violations, res.warnings
    path = Path(path)

    old_text = None
    if previous_path is not None:
        try:
            old_text = Path(previous_path).read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            violations.append(f"UPDATE: cannot read previous note — {exc}")

    if cli:
        if not path.exists():
            violations.append(f"PATH: file not found: {path}")
            return res
        if path.is_dir():
            violations.append(f"PATH: is a directory: {path}")
            return res
        if path.suffix.lower() != ".md":
            violations.append(f"PATH: not a Markdown (.md) file: {path}")
            return res
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            violations.append(f"PATH: cannot read as UTF-8 — {exc}")
            return res
        if _SCHEMA_ERROR:
            violations.append(f"SCHEMA: cannot load {SCHEMA_PATH} — {_SCHEMA_ERROR}")
    else:
        if not path.exists():
            return res
        text = path.read_text(encoding="utf-8", errors="replace")

    fm, body_start = parse_frontmatter(text)
    if fm is None:
        if cli:
            violations.append("FRONTMATTER: a paper note requires a leading YAML `---` block with `type: paper`")
        return res
    res.checked.append("frontmatter")
    kind = _engine_frontmatter_check(res, text, path, cli)
    if kind not in ("paper", "paper-broken", "engine-missing") and not cli:
        return res
    body = text[body_start:] if body_start else text

    # ---- driller meta (body block and/or --meta sidecar) ---------------------
    dmeta, meta_errors = parse_driller_meta(body)
    violations.extend(meta_errors)
    if meta_path is not None:
        side, side_errors = load_meta_file(Path(meta_path))
        violations.extend(side_errors)
        if side is not None:
            merged = dict(dmeta or {})
            for k, v in side.items():
                if k in merged and merged[k] != v:
                    violations.append(f"META: `{k}` differs between DRILLER:meta block (`{merged[k]}`) and --meta (`{v}`)")
                merged[k] = v
            dmeta = merged
    is_driller = dmeta is not None
    dmeta = dmeta or {}
    # YAML에 template 키가 남아 있으면 엔진이 KEY-FORBIDDEN으로 잡는다. 여기서는 참조하지 않는다.

    # ---- value checks (driller notes only; legacy values are never rejected) ----
    if is_driller:
        res.checked.append("driller-meta")
        rs = _fm_str(fm, "Reading-Status")
        if rs and rs not in VALID_READING_STATUS:
            violations.append(f"FRONTMATTER: Reading-Status=`{rs}` — must be one of {sorted(VALID_READING_STATUS)}")
        py = _fm_str(fm, "Published Year")
        if py and not re.fullmatch(r"\d{4}", py):
            violations.append(f"FRONTMATTER: Published Year=`{py}` — must be 4-digit integer")
        rd = _fm_str(fm, "Review-Date")
        if rd and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", rd):
            violations.append(f"FRONTMATTER: Review-Date=`{rd}` — must be YYYY-MM-DD")
        cat = _fm_str(fm, "Category")
        if cat and cat not in VALID_CATEGORIES:
            violations.append(f"FRONTMATTER: Category=`{cat}` — must be one of {sorted(VALID_CATEGORIES)}")
        url = _fm_str(fm, "URL")
        if url and url.upper() != "N/A" and _norm_url(url) is None:
            violations.append(f"FRONTMATTER: URL=`{url}` is not a valid url identifier (http(s)://, no whitespace)")
        if old_text is None:
            # 새 노트: 사람 소유 필드를 모델이 채우지 않는다.
            rd_val = fm.get("Read-Depth")
            rd_filled = (isinstance(rd_val, str) and rd_val.strip()) or (
                isinstance(rd_val, list) and any(str(x).strip() for x in rd_val)
            )
            if rd_filled:
                violations.append("FRONTMATTER: Read-Depth is the human reading depth — a generated note must leave it blank")
            if rs and rs not in NOT_STARTED_STATUS:
                violations.append(f"FRONTMATTER: Reading-Status=`{rs}` — a generated note may only be blank or Not Started")

    summary_mode = _fm_str(dmeta, "summary-mode")
    if summary_mode and summary_mode not in VALID_SUMMARY_MODES:
        violations.append(f"META: summary-mode=`{summary_mode}` — must be preread|deep")
    source_coverage = _fm_str(dmeta, "source-coverage")
    if source_coverage and source_coverage not in VALID_SOURCE_COVERAGE:
        violations.append(f"META: source-coverage=`{source_coverage}` — must be one of {sorted(VALID_SOURCE_COVERAGE)}")
    template_version = _fm_str(dmeta, "template-version")
    if template_version and template_version not in KNOWN_TEMPLATE_VERSIONS:
        violations.append(f"META: template-version=`{template_version}` — must be one of {sorted(KNOWN_TEMPLATE_VERSIONS)}")
    if not template_version:
        v3_shape = [k for k in V3_ONLY_KEYS if k in dmeta]
        if any(find_auto_markers(body)):
            v3_shape.append("AUTO:body markers")
        if v3_shape:
            violations.append(
                f"META: note has paper-note-v3 fields/markers {v3_shape} but no `template-version: {NOTE_V3}` — "
                "a v3 note cannot downgrade to the legacy path"
            )
    if template_version in ("paper-preread-v2", DEEP_V2):
        label = "preread v2" if template_version == "paper-preread-v2" else "deep v2"
        for key in PREREAD_V2_REQUIRED_KEYS:
            if not _fm_str(dmeta, key):
                violations.append(f"META: {label} requires `{key}`")
        if template_version == "paper-preread-v2" and summary_mode != "preread":
            violations.append("META: paper-preread-v2 requires summary-mode=`preread`")
        if template_version == DEEP_V2 and summary_mode != "deep":
            violations.append(f"META: {DEEP_V2} requires summary-mode=`deep`")
        for key, valid in (("reading-decision", VALID_READING_DECISIONS), ("decision-confidence", VALID_DECISION_CONFIDENCE)):
            val = _fm_str(dmeta, key)
            if val and val not in valid:
                violations.append(f"META: {key}=`{val}` — must be one of {sorted(valid)}")

    # ---- structure (all notes) ----------------------------------------------
    has_h1 = bool(re.search(r"(?m)^# [^\s#]", body))
    h2_count = len(re.findall(r"(?m)^## [^\s#]", body))
    body_chars = len(re.sub(r"\s+", "", body))
    if not has_h1:
        violations.append("STRUCTURE: body is missing a top-level `# ` title heading")
    if MIN_H2_HEADINGS > 0 and h2_count < MIN_H2_HEADINGS:
        violations.append(f"STRUCTURE: only {h2_count} `## ` heading(s) found — expected ≥{MIN_H2_HEADINGS}")
    if body_chars < MIN_BODY_CHARS:
        violations.append(f"STRUCTURE: body has only {body_chars} non-whitespace chars (<{MIN_BODY_CHARS}) — looks like a blank template")
    res.checked.append("structure")

    if template_version in ("paper-preread-v2", DEEP_V2):
        label = "preread v2" if template_version == "paper-preread-v2" else "deep v2"
        if template_version == "paper-preread-v2" and body_chars > PREREAD_V2_MAX_BODY_CHARS:
            violations.append(f"STRUCTURE: preread v2 길이 상한 초과 — {body_chars} non-whitespace chars (max {PREREAD_V2_MAX_BODY_CHARS})")
        if not re.search(r"(?m)^> \[!summary\] 1분 요약\s*$", body):
            violations.append(f"STRUCTURE: {label} requires `> [!summary] 1분 요약`")
        for heading in PREREAD_V2_HEADINGS:
            if not re.search(rf"(?m)^## {re.escape(heading)}\s*$", body):
                violations.append(f"STRUCTURE: {label} section missing: `## {heading}`")
        if template_version == DEEP_V2 and not re.search(rf"(?m)^## {re.escape(DEEP_EXTRA_H2)}\s*$", body):
            violations.append(f"STRUCTURE: {DEEP_V2} requires `## {DEEP_EXTRA_H2}` after the preread block")

    placeholder_scope = body
    if template_version == NOTE_V3:
        placeholder_scope = _validate_v3(res, fm, dmeta, body, manifest_path)
    elif manifest_path is not None:
        manifest, mf_errors = load_manifest(Path(manifest_path))
        if manifest is None:
            violations.extend(mf_errors)
            violations.append("MANIFEST: an explicitly supplied manifest is malformed — this is a failure, not a skip")
        else:
            violations.extend(check_manifest_binding(manifest, fm))
            res.checked.append("manifest-binding")
        res.skipped.append(f"visuals (manifest supplied but note is not {NOTE_V3} — figure/table coverage was NOT checked)")

    if summary_mode == "deep" and template_version != NOTE_V3 and "```mermaid" not in body:
        warnings.append("CONTENT: deep note has no ```mermaid block. Add one only if it improves comprehension.")

    stripped = re.sub(r"```.*?```", "", placeholder_scope, flags=re.DOTALL)
    for pat in PLACEHOLDER_PATTERNS:
        if pat.search(stripped):
            violations.append(f"CONTENT: placeholder pattern `{pat.pattern}` still present inside generated content")

    if old_text is not None:
        violations.extend(check_update_preservation(old_text, text, approved_switch=approved_switch))
        res.checked.append("update-preservation" + (" (approved switch)" if approved_switch else ""))
    return res


def _validate_v3(res: Result, fm: dict, dmeta: dict, body: str, manifest_path) -> str:
    violations = res.violations
    if _SCHEMA_ERROR:
        violations.append(f"SCHEMA: paper-note-v3 needs {SCHEMA_PATH} — {_SCHEMA_ERROR}")
    for key in NOTE_V3_REQUIRED_KEYS:
        if not _fm_str(dmeta, key):
            violations.append(f"META: paper-note-v3 requires `{key}`")
    invalid = derive_doc_ids(fm).get("__invalid__", {})
    if "url" in invalid:
        violations.append(f"FRONTMATTER: URL=`{invalid['url']}` is not a valid url identifier")
    if _fm_str(dmeta, "summary-mode") not in VALID_SUMMARY_MODES:
        violations.append("META: paper-note-v3 requires summary-mode=`preread` or `deep`")
    qs = _fm_str(dmeta, "quality-status")
    if qs and qs not in VALID_QUALITY_STATUS:
        violations.append(f"META: quality-status=`{qs}` — must be one of {sorted(VALID_QUALITY_STATUS)}")
    vc = _fm_str(dmeta, "visual-check")
    if vc and vc not in VALID_VISUAL_CHECK:
        violations.append(f"META: visual-check=`{vc}` — must be one of {sorted(VALID_VISUAL_CHECK)}")
    vs = _fm_str(dmeta, "visual-scope")
    if vs and vs not in VALID_VISUAL_SCOPE:
        violations.append(f"META: visual-scope=`{vs}` — must be one of {sorted(VALID_VISUAL_SCOPE)}")
    if vs == "user-narrowed" and not _fm_str(dmeta, "visual-scope-note"):
        violations.append("META: visual-scope=`user-narrowed` requires `visual-scope-note` quoting the user's request")
    for key, valid in (("reading-decision", VALID_READING_DECISIONS), ("decision-confidence", VALID_DECISION_CONFIDENCE)):
        val = _fm_str(dmeta, key)
        if val and val not in valid:
            violations.append(f"META: {key}=`{val}` — must be one of {sorted(valid)}")
    if qs == "ready" and _fm_str(dmeta, "source-coverage") in ("abstract-only", "unknown"):
        violations.append("META: quality-status=`ready` not allowed with source-coverage abstract-only|unknown")
    if qs == "ready" and vc in ("unverified", "caption-only", "mixed"):
        violations.append(f"META: quality-status=`ready` not allowed with visual-check=`{vc}` (use `review`)")

    template_id = _fm_str(dmeta, "template-id")
    meta, t_errors = load_template(template_id) if template_id else (None, [])
    violations.extend(t_errors)

    auto_text, marker_id, m_errors = extract_auto_body(body)
    violations.extend(m_errors)
    if auto_text is not None and marker_id is None:
        violations.append(f"MARKER: `BEGIN AUTO:body` must carry `template-id={template_id or '{id}'}` in a {NOTE_V3} note")
    elif auto_text is not None and marker_id != template_id:
        violations.append(f"MARKER: AUTO:body template-id=`{marker_id}` != DRILLER:meta template-id=`{template_id}`")
    placeholder_scope = strip_ignored(auto_text) if auto_text is not None else body

    if meta is None or auto_text is None:
        res.skipped.append("template (template or AUTO:body unavailable)")
        res.skipped.append("visuals (template or AUTO:body unavailable)")
        return placeholder_scope
    res.checked.append(f"template:{template_id}")
    violations.extend(check_required_h2(auto_text, meta))

    if _fm_str(dmeta, "summary-mode") == "deep":
        deep_section = section_text(strip_ignored(auto_text), DEEP_EXTRA_H2)
        if deep_section is None:
            violations.append(f"STRUCTURE: summary-mode=`deep` requires `## {DEEP_EXTRA_H2}` inside AUTO:body after the template sections")
        elif not deep_section.strip():
            violations.append(f"STRUCTURE: `## {DEEP_EXTRA_H2}` is empty — deep mode must add real reading notes")
        elif h2_headings(strip_ignored(auto_text)).index(DEEP_EXTRA_H2) < len(meta.get("required_h2", [])):
            violations.append(f"STRUCTURE: `## {DEEP_EXTRA_H2}` must come after all required template sections")

    if manifest_path is None:
        section = section_text(strip_ignored(auto_text), meta["visual_section"])
        found = visual_h3_ids(section) if section is not None else []
        if vc == "none" and found:
            violations.append("VISUALS: visual-check=`none` but the visual section lists items")
        if vc in ("viewed", "caption-only", "mixed") and not found:
            violations.append(f"VISUALS: visual-check=`{vc}` but the visual section has no `### ` items")
        dups = sorted({f for f in found if found.count(f) > 1})
        if dups:
            violations.append(f"VISUALS: duplicate item headings: {dups}")
        res.skipped.append("visuals (no manifest — completeness against the source was NOT checked)")
        return placeholder_scope
    manifest, mf_errors = load_manifest(Path(manifest_path))
    if manifest is None:
        violations.extend(mf_errors)
        violations.append("MANIFEST: an explicitly supplied manifest is malformed — this is a failure, not a skip")
        return placeholder_scope
    violations.extend(check_visuals(auto_text, meta, manifest, fm, dmeta))
    res.checked.append("visuals")
    return placeholder_scope


def validate(path: Path):
    """Legacy signature. Returns (violations, warnings)."""
    res = validate_note(path)
    return res.violations, res.warnings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _report(path, res: Result, cli: bool) -> int:
    if cli:
        sys.stdout.write(f"CHECKED: {', '.join(res.checked) if res.checked else '(nothing)'}\n")
        for s in res.skipped:
            sys.stdout.write(f"SKIPPED: {s}\n")
    if not res.violations:
        if res.warnings or (not cli and res.skipped):
            sys.stdout.write(
                f"FORMAT_WARNING for paper summary file: {path}\n"
                "These are advisory only — the file passed hook validation.\nWarnings:\n"
            )
            for w in res.warnings:
                sys.stdout.write(f"  - {w}\n")
            if not cli:
                for s in res.skipped:
                    sys.stdout.write(f"  - SKIPPED: {s}\n")
        if cli:
            sys.stdout.write("RESULT: PASS\n")
        return 0
    sys.stderr.write(
        f"FORMAT_VIOLATION in paper summary file: {path}\n"
        "The output does not conform to the canonical paper-summary schema defined in "
        "the paper-driller SKILL.md / references (frontmatter: Public/_tools/paper_frontmatter.py).\n\n"
        "Violations (blocking):\n"
    )
    for v in res.violations:
        sys.stderr.write(f"  - {v}\n")
    if res.warnings:
        sys.stderr.write("\nWarnings (non-blocking, surfaced for reference):\n")
        for w in res.warnings:
            sys.stderr.write(f"  - {w}\n")
    sys.stderr.write(
        "\nAction required: re-read the file, apply Edit to fix each violation, "
        "then re-write. Retry up to 3 times; report failure to user if still invalid.\n"
    )
    if cli:
        sys.stdout.write("RESULT: FAIL\n")
    return 2


def run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="paper-format-validator", add_help=True)
    parser.add_argument("--path", help="note to validate (fail-closed; scope/skip rules do not apply)")
    parser.add_argument("--manifest", help="source-derived figure/table manifest JSON")
    parser.add_argument("--meta", help="driller metadata JSON sidecar (instead of / in addition to the DRILLER:meta block)")
    parser.add_argument("--previous", help="previous version of the note (checks the update allowlist)")
    parser.add_argument("--approved-switch", action="store_true",
                        help="with --previous: the user already approved a template switch in conversation")
    parser.add_argument("--check-template", help="statically validate one template file")
    args = parser.parse_args(argv)
    if args.approved_switch and not args.previous:
        parser.error("--approved-switch requires --previous OLD.md")
    if args.check_template:
        tpath = Path(args.check_template).expanduser()
        meta, errors = check_template_file(tpath)
        if errors:
            sys.stdout.write("CHECKED: template-file\nRESULT: FAIL\n")
            sys.stderr.write(f"TEMPLATE_INVALID: {tpath}\n")
            for e in errors:
                sys.stderr.write(f"  - {e}\n")
            return 2
        sys.stdout.write(
            f"CHECKED: template-file\nTEMPLATE: {meta['id']} — {meta['title']} "
            f"({len(meta['required_h2'])} required sections, visual section `{meta['visual_section']}`)\nRESULT: PASS\n"
        )
        return 0
    if not args.path:
        parser.error("--path NOTE or --check-template FILE is required")
    if args.manifest and not Path(args.manifest).expanduser().exists():
        sys.stdout.write("CHECKED: (nothing)\nRESULT: FAIL\n")
        sys.stderr.write(f"MANIFEST: file not found: {args.manifest}\n")
        return 2
    if args.meta and not Path(args.meta).expanduser().exists():
        sys.stdout.write("CHECKED: (nothing)\nRESULT: FAIL\n")
        sys.stderr.write(f"META: file not found: {args.meta}\n")
        return 2
    path = Path(args.path).expanduser()
    res = validate_note(
        path,
        manifest_path=Path(args.manifest).expanduser() if args.manifest else None,
        previous_path=Path(args.previous).expanduser() if args.previous else None,
        cli=True,
        approved_switch=bool(args.approved_switch),
        meta_path=Path(args.meta).expanduser() if args.meta else None,
    )
    return _report(path, res, cli=True)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        return run_cli(argv)

    # Hook mode (compat). Bulk-maintenance bypass applies ONLY here, never to CLI checks.
    if os.environ.get("SKIP_PAPER_VALIDATOR") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return 0
    file_path_raw = payload.get("tool_input", {}).get("file_path") or payload.get("tool_input", {}).get("path") or ""
    if not file_path_raw:
        return 0
    path = Path(file_path_raw).expanduser()
    if not str(path).endswith(".md") or not path.exists():
        return 0
    text_for_scope = path.read_text(encoding="utf-8", errors="replace")
    fm_for_scope, _ = parse_frontmatter(text_for_scope)
    if not in_scope(path, fm=fm_for_scope):
        return 0
    res = validate_note(path)
    return _report(path, res, cli=False)


if __name__ == "__main__":
    sys.exit(main())

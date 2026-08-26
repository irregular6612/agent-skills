#!/usr/bin/env python3
"""
Paper summary format validator for Claude Code PostToolUse hook.

Reads PostToolUse JSON from stdin, extracts the file path of the Write/Edit,
and validates against the canonical paper-summary schema shared by
/paper-driller.

Exit codes:
  0 — not a paper-summary file (out of scope) OR validation passed
  2 — validation failed; stderr contains structured FORMAT_VIOLATION block
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Scope configuration
# ---------------------------------------------------------------------------

SCOPE_GLOBS = ("Public/AI/Papers/", "arxiv-notes/", "survey-notes/")
# Resolved relative to this file so the hook works from the plugin root
# (${CLAUDE_PLUGIN_ROOT}/hooks/), with the legacy ~/.claude layout as fallback.
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = _PLUGIN_ROOT / "skills" / "paper-driller" / "references" / "paper-schema.json"
if not SCHEMA_PATH.exists():
    SCHEMA_PATH = (
        Path.home() / ".claude" / "skills" / "paper-driller" / "references" / "paper-schema.json"
    )


def _load_paper_schema():
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Keep the hook operational during bootstrap. validate-driller.sh treats
        # a missing/invalid paper-schema.json as a deployment failure.
        return {}


PAPER_SCHEMA = _load_paper_schema()

# Common keys — required for EVERY paper note regardless of domain.
COMMON_REQUIRED_KEYS = PAPER_SCHEMA.get("required_frontmatter", {}).get(
    "common",
    [
        "Reading-Status", "Author", "Journal/Conference", "Published Year",
        "Topic", "Review-Date", "Comment", "URL", "arXiv-ID", "DOI",
        "Evidence-Quality", "Reproducibility", "type",
    ],
)

# AI-only keys — required only when the note lives under Public/AI/.
AI_ONLY_REQUIRED_KEYS = PAPER_SCHEMA.get("required_frontmatter", {}).get(
    "ai_only", ["Category", "isTargetPaper", "linked-bases"]
)

# Back-compat: everything that was ever required is allowed (not a banned alias).
REQUIRED_KEYS = COMMON_REQUIRED_KEYS + AI_ONLY_REQUIRED_KEYS


def is_ai_domain(path: Path) -> bool:
    return "Public/AI/" in str(path)

OPTIONAL_KEYS = {"Benchmark-Type", "Lab"}

# Legacy keys that leaked in from other templates. Their presence is a fail.
BANNED_ALIAS_KEYS = {
    "title",
    "Title",
    "authors",
    "author",
    "year",
    "Year",
    "venue",
    "Venue",
    "tags",
    "keywords",
    "description",
    "aliases",
    "cssclasses",
    "date",
    "url",
    "Journal",
    "Conference",
}

VALID_CATEGORIES = set(
    PAPER_SCHEMA.get(
        "categories",
        [
            "Architecture", "Training", "Benchmark/Evaluation", "Application",
            "Reasoning", "Survey", "Dataset", "Optimization", "Theory", "AGI",
        ],
    )
)

# "☑️ Not Started" is the canonical default emitted by the paper-driller.
VALID_READING_STATUS = set(
    PAPER_SCHEMA.get(
        "reading_status", ["✅ Done", "▶️ In progress", "☑️ Not Started", "Not Started"]
    )
)
VALID_GRADES = set(PAPER_SCHEMA.get("grades", ["A", "B", "C", "D"]))

# Structure requirements are intentionally lenient: any top-level H1 plus a
# non-trivial body counts as a real paper note. Specific section names are NOT
# enforced — custom Korean/English headings like `## 핵심 개념` or `## 아키텍처 상세`
# are fine as long as the note isn't a blank template.
MIN_BODY_CHARS = 500
MIN_H2_HEADINGS = 0  # Legacy notes: H1 + body content is enough.
PREREAD_V2_HEADINGS = tuple(
    PAPER_SCHEMA.get("templates", {})
    .get("paper-preread-v2", {})
    .get(
        "required_h2",
        ["읽기 판단", "핵심 아이디어", "무엇을 했나", "핵심 근거", "어디까지 믿을까", "원문 읽기 지도"],
    )
)
PREREAD_V2_REQUIRED_KEYS = tuple(
    PAPER_SCHEMA.get("required_frontmatter", {}).get(
        "preread_v2",
        [
            "template-version", "summary-mode", "profile", "source-coverage",
            "quality-status", "reading-decision", "decision-confidence",
        ],
    )
)
PREREAD_V2_MAX_BODY_CHARS = int(
    PAPER_SCHEMA.get("templates", {})
    .get("paper-preread-v2", {})
    .get("max_body_non_whitespace_chars", 5500)
)
VALID_READING_DECISIONS = set(PAPER_SCHEMA.get("reading_decisions", ["read", "skim", "skip"]))
VALID_DECISION_CONFIDENCE = set(
    PAPER_SCHEMA.get("decision_confidence", ["high", "medium", "low"])
)
VALID_SOURCE_COVERAGE = set(
    PAPER_SCHEMA.get("source_coverage", ["fulltext", "section-extract", "abstract-only", "unknown"])
)
VALID_SUMMARY_MODES = set(PAPER_SCHEMA.get("summary_modes", ["preread", "deep"]))

PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\[작성 필요\]"),
    re.compile(r"\[내용\]"),
]

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


# ---------------------------------------------------------------------------
# Frontmatter parsing (minimal; avoids yaml dependency)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, None
    raw = match.group(1)
    body_start = match.end()
    data = {}
    current_key = None
    for line_no, line in enumerate(raw.splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t", "-")) and current_key is not None:
            # continuation / list item — record as multiline
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


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def in_scope(path: Path, fm: dict | None = None) -> bool:
    """In scope if the path matches a legacy SCOPE_GLOB OR frontmatter declares type: paper.

    type-based scope lets flattened non-AI papers (which no longer live under a
    Papers/ path) be validated, while non-paper notes (type: concept/hub/...) are
    skipped regardless of location. Notes with no `type` and no matching path are
    out of scope — safe for vaults that don't use the wiki convention.
    """
    p = str(path)
    if any(seg in p for seg in SCOPE_GLOBS):
        return True
    if fm is not None and str(fm.get("type", "")).strip() == "paper":
        return True
    return False


def validate(path: Path):
    """Returns (violations, warnings). Violations block (exit 2); warnings surface on exit 0."""
    violations: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return violations, warnings  # nothing to check, file got removed
    text = path.read_text(encoding="utf-8", errors="replace")

    fm, body_start = parse_frontmatter(text)
    if fm is None:
        # A file written inside a canonical paper path is a paper candidate even
        # when its `type` key cannot be parsed. Silently skipping it lets raw or
        # truncated paper-driller output bypass the hook entirely.
        if any(seg in str(path) for seg in SCOPE_GLOBS):
            violations.append(
                "FRONTMATTER: canonical paper path requires a leading YAML `---` block"
            )
        return violations, warnings

    # Required keys: common always; AI-only when under Public/AI/.
    required = list(COMMON_REQUIRED_KEYS)
    if is_ai_domain(path):
        required += AI_ONLY_REQUIRED_KEYS
    for key in required:
        if key not in fm:
            violations.append(f"FRONTMATTER: required key missing: `{key}`")

    # Banned alias keys
    for alias in BANNED_ALIAS_KEYS:
        if alias in fm and alias not in REQUIRED_KEYS:
            violations.append(
                f"FRONTMATTER: deprecated/alias key present: `{alias}` "
                f"(remove or rename — see SKILL.md canonical schema)"
            )

    # Duplicate keys
    for dup in fm.get("__duplicates__", []):
        violations.append(f"FRONTMATTER: duplicate key: `{dup}`")

    # Value checks
    rs = fm.get("Reading-Status")
    if isinstance(rs, str) and rs not in VALID_READING_STATUS:
        violations.append(
            f"FRONTMATTER: Reading-Status=`{rs}` — must be one of {sorted(VALID_READING_STATUS)}"
        )

    py = fm.get("Published Year")
    if isinstance(py, str) and py and not re.fullmatch(r"\d{4}", py.strip()):
        violations.append(f"FRONTMATTER: Published Year=`{py}` — must be 4-digit integer")

    rd = fm.get("Review-Date")
    if isinstance(rd, str) and rd and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", rd.strip()):
        violations.append(f"FRONTMATTER: Review-Date=`{rd}` — must be YYYY-MM-DD")

    cat = fm.get("Category")
    if is_ai_domain(path) and isinstance(cat, str) and cat and cat not in VALID_CATEGORIES:
        violations.append(
            f"FRONTMATTER: Category=`{cat}` — must be one of {sorted(VALID_CATEGORIES)}"
        )

    for grade_key in ("Evidence-Quality", "Reproducibility"):
        g = fm.get(grade_key)
        if isinstance(g, str) and g and g not in VALID_GRADES:
            violations.append(f"FRONTMATTER: {grade_key}=`{g}` — must be A|B|C|D")

    istp = fm.get("isTargetPaper")
    if isinstance(istp, str) and istp not in ("true", "false", ""):
        violations.append(f"FRONTMATTER: isTargetPaper=`{istp}` — must be bare `true`/`false`")

    url = fm.get("URL")
    if isinstance(url, str) and url and not re.match(r"https?://", url):
        violations.append(f"FRONTMATTER: URL=`{url}` — must start with http(s)://")

    summary_mode = str(fm.get("summary-mode", "")).strip()
    if summary_mode and summary_mode not in VALID_SUMMARY_MODES:
        violations.append(
            f"FRONTMATTER: summary-mode=`{summary_mode}` — must be preread|deep"
        )
    source_coverage = str(fm.get("source-coverage", "")).strip()
    if source_coverage and source_coverage not in VALID_SOURCE_COVERAGE:
        violations.append(
            "FRONTMATTER: source-coverage="
            f"`{source_coverage}` — must be one of {sorted(VALID_SOURCE_COVERAGE)}"
        )

    template_version = str(fm.get("template-version", "")).strip()
    if template_version == "paper-preread-v2":
        for key in PREREAD_V2_REQUIRED_KEYS:
            if not str(fm.get(key, "")).strip():
                violations.append(f"FRONTMATTER: preread v2 requires `{key}`")
        if summary_mode != "preread":
            violations.append("FRONTMATTER: paper-preread-v2 requires summary-mode=`preread`")
        reading_decision = str(fm.get("reading-decision", "")).strip()
        if reading_decision and reading_decision not in VALID_READING_DECISIONS:
            violations.append(
                f"FRONTMATTER: reading-decision=`{reading_decision}` — "
                f"must be one of {sorted(VALID_READING_DECISIONS)}"
            )
        decision_confidence = str(fm.get("decision-confidence", "")).strip()
        if decision_confidence and decision_confidence not in VALID_DECISION_CONFIDENCE:
            violations.append(
                f"FRONTMATTER: decision-confidence=`{decision_confidence}` — "
                f"must be one of {sorted(VALID_DECISION_CONFIDENCE)}"
            )

    # Structure — minimal "not a blank template" bar.
    # Require H1 title + ≥2 H2 sections + non-trivial body content.
    body = text[body_start:] if body_start else text
    has_h1 = bool(re.search(r"(?m)^# [^\s#]", body))
    h2_count = len(re.findall(r"(?m)^## [^\s#]", body))
    body_chars = len(re.sub(r"\s+", "", body))
    if not has_h1:
        violations.append("STRUCTURE: body is missing a top-level `# ` title heading")
    if MIN_H2_HEADINGS > 0 and h2_count < MIN_H2_HEADINGS:
        violations.append(
            f"STRUCTURE: only {h2_count} `## ` heading(s) found — expected ≥{MIN_H2_HEADINGS} "
            "(any section names are allowed; this only catches blank templates)"
        )
    if body_chars < MIN_BODY_CHARS:
        violations.append(
            f"STRUCTURE: body has only {body_chars} non-whitespace chars (<{MIN_BODY_CHARS}) — "
            "looks like a blank template"
        )

    if template_version == "paper-preread-v2":
        if body_chars > PREREAD_V2_MAX_BODY_CHARS:
            violations.append(
                f"STRUCTURE: preread v2 길이 상한 초과 — {body_chars} non-whitespace chars "
                f"(max {PREREAD_V2_MAX_BODY_CHARS})"
            )
        if not re.search(r"(?m)^> \[!summary\] 1분 요약\s*$", body):
            violations.append("STRUCTURE: preread v2 requires `> [!summary] 1분 요약`")
        for heading in PREREAD_V2_HEADINGS:
            if not re.search(rf"(?m)^## {re.escape(heading)}\s*$", body):
                violations.append(f"STRUCTURE: preread v2 section missing: `## {heading}`")

    # Mermaid is advisory only in explicitly requested deep notes. preread
    # intentionally omits it unless a diagram materially improves comprehension.
    if summary_mode == "deep" and "```mermaid" not in body:
        warnings.append(
            "CONTENT: deep note has no ```mermaid block. Add one only if it improves comprehension."
        )

    # Placeholder detection (ignore fenced code blocks for safety) — blocking.
    stripped = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    for pat in PLACEHOLDER_PATTERNS:
        if pat.search(stripped):
            violations.append(f"CONTENT: placeholder pattern `{pat.pattern}` still present")

    return violations, warnings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # Bypass for intentional bulk migration / maintenance.
    # Export SKIP_PAPER_VALIDATOR=1 before running batch scripts.
    if os.environ.get("SKIP_PAPER_VALIDATOR") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # no hook input — nothing to validate

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return 0

    file_path_raw = (
        payload.get("tool_input", {}).get("file_path")
        or payload.get("tool_input", {}).get("path")
        or ""
    )
    if not file_path_raw:
        return 0

    path = Path(file_path_raw).expanduser()
    if not str(path).endswith(".md"):
        return 0
    # Parse frontmatter once so scope can consider `type: paper` (location-independent).
    text_for_scope = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    fm_for_scope, _ = parse_frontmatter(text_for_scope)
    if not in_scope(path, fm=fm_for_scope):
        return 0

    # Skip Obsidian landing/index pages and survey overviews.
    # Conventions: filename starts with `_`, ends with `_overview.md`,
    # is a bare `*papers.md` index, or uses the `Attention Methods.md`-style index.
    if (
        path.name == "_survey-overview.md"
        or path.name.startswith("_")
        or path.name.endswith("_overview.md")
        or path.stem.lower().endswith(" papers")
        or path.name.lower() in {"ai-papers.md", "attention methods.md"}
    ):
        return 0

    violations, warnings = validate(path)

    if not violations:
        # Silent success, or warnings-only informational output.
        if warnings:
            sys.stdout.write(
                f"FORMAT_WARNING for paper summary file: {path}\n"
                "These are advisory only — the file passed hook validation.\n"
                "Warnings:\n"
            )
            for w in warnings:
                sys.stdout.write(f"  - {w}\n")
        return 0

    sys.stderr.write(
        "FORMAT_VIOLATION in paper summary file: "
        f"{path}\n"
        "The PostToolUse hook blocked this Write/Edit because the output "
        "does not conform to the canonical paper-summary schema defined in "
        "the paper-driller SKILL.md.\n\n"
        "Violations (blocking):\n"
    )
    for v in violations:
        sys.stderr.write(f"  - {v}\n")
    if warnings:
        sys.stderr.write("\nWarnings (non-blocking, surfaced for reference):\n")
        for w in warnings:
            sys.stderr.write(f"  - {w}\n")
    sys.stderr.write(
        "\nAction required: re-read the file, apply Edit to fix each violation, "
        "then re-write. Retry up to 3 times; report failure to user if still invalid.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

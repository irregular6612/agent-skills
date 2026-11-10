"""categorizer: give every skill/agent a category (= graph color).

Order: frontmatter category (via category_aliases) -> LLM (cached) -> keyword fallback -> "other",
then modes.yaml overrides win. The LLM step batches all uncached nodes (chunks of BATCH) into
`claude -p` calls, cached per node in judgments.json["categories"] under
sha256(node hash + CATEGORIZE_VERSION + category list). Keywords are used only when the LLM is
not allowed (`--rules-only`, run/switch) or failed, and are never cached.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import judgments_path, load_json, save_json
from .judge import call_claude, parse_json_obj

CATEGORIZE_VERSION = "categorize-v1"
BATCH = 50

PROMPT = """Assign each Claude Code extension below to exactly one category.
Categories:
{cats}
If none fits, use "other". Judge by what the user would be doing when it triggers.
Answer with ONE JSON object mapping id -> category and nothing else.

{items}
"""


def _fm_category(n: dict) -> str:
    fm = n.get("frontmatter") or {}
    return str(fm.get("category") or "")


def _keyword_category(n: dict, categories: dict) -> str:
    text = (n["name"].replace("-", " ") + " " + n.get("description", "")).lower()
    best, best_hits = "", 0
    for cat, spec in categories.items():
        hits = sum(1 for kw in spec.get("keywords", [])
                   if re.search(rf"(?<![a-z]){re.escape(kw.lower())}(?![a-z])", text))
        if hits > best_hits:
            best, best_hits = cat, hits
    return best


def categorize(nodes: list[dict], cfg: dict, use_llm: bool, model: str, log=print) -> tuple[dict, int]:
    """Return ({node_id: category}, llm_calls)."""
    categories = cfg.get("categories", {}) or {}
    aliases = cfg.get("category_aliases", {}) or {}
    overrides = {(k if ":" in k else f"skill:{k}"): v for k, v in (cfg.get("overrides") or {}).items()}
    out, pending = {}, []
    for n in nodes:
        if n["kind"] in ("mcp", "package"):
            out[n["id"]] = "mcp" if n["kind"] == "mcp" else "package"
            continue
        fm = _fm_category(n)
        fm = fm if fm in categories else aliases.get(fm, "")
        fm = fm or overrides.get(n["id"].split("@")[0], "")  # overridden nodes never go to the LLM
        if fm:
            out[n["id"]] = fm
        else:
            pending.append(n)

    calls = 0
    cache = load_json(judgments_path(), {"version": 1, "entries": {}})
    cc = cache.setdefault("categories", {})
    cat_list = ",".join(sorted(categories))
    keys = {n["id"]: hashlib.sha256((n["hash"] + CATEGORIZE_VERSION + cat_list).encode()).hexdigest()
            for n in pending}
    todo = [n for n in pending if keys[n["id"]] not in cc]
    if todo and use_llm:
        cats = "\n".join(f"- {c}: {spec.get('description', '')}" for c, spec in categories.items())
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            items = "\n".join(f"- {n['id']}: {n.get('description', '')[:300]}" for n in chunk)
            prompt = PROMPT.replace("{cats}", cats).replace("{items}", items)
            for _ in range(2):  # one retry on parse failure
                calls += 1
                try:
                    res = parse_json_obj(call_claude(prompt, model))
                    for n in chunk:
                        c = str(res.get(n["id"], "other"))
                        cc[keys[n["id"]]] = c if c in categories else "other"
                    break
                except Exception:
                    continue
        save_json(judgments_path(), cache)
        log(f"  categorizer: {len(todo)}개 LLM 분류 (호출 {calls}회)")
    for n in pending:
        out[n["id"]] = cc.get(keys[n["id"]]) or _keyword_category(n, categories) or "other"
    for nid in list(out):  # overrides always win
        if nid.split("@")[0] in overrides:
            out[nid] = overrides[nid.split("@")[0]]
    return out, calls


def palette(cfg: dict) -> dict:
    p = {cat: spec.get("color", "#999999") for cat, spec in (cfg.get("categories") or {}).items()}
    p.update({"other": "#BBBBBB", "mcp": "#444444", "package": "#999999"})
    return p

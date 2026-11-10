"""dep-judge: one `claude -p` call per candidate pair, cached in judgments.json.

Cache key = sha256(hashA + hashB + prompt_version), pair sorted by id so (A,B) == (B,A).
The prompt template and prompt_version live in .claude/skills/skm-dep-judge/SKILL.md.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import skm
from . import SKILLS_SRC, judgments_path, load_json, save_json

SKILL_FILE = SKILLS_SRC / "skm-dep-judge" / "SKILL.md"
UNKNOWN = {"relation": "unknown", "direction": "none", "overlap": 0.0, "conflict": False,
           "conflict_reason": "", "confidence": 0.0}

# lean headless call: no skills, no MCP, no user settings, no tools, no saved session
CLAUDE_FLAGS = ["--output-format", "json", "--disable-slash-commands", "--strict-mcp-config",
                "--setting-sources", "", "--tools", "", "--no-session-persistence"]


def load_prompt() -> tuple[str, str]:
    text = SKILL_FILE.read_text(encoding="utf-8")
    m = re.search(r"^\s*prompt_version:\s*(\S+)", text, re.M)
    version = m.group(1).strip("'\"") if m else "unversioned"
    m = re.search(r"<!-- PROMPT:BEGIN -->\n(.*?)<!-- PROMPT:END -->", text, re.S)
    if not m:
        raise RuntimeError(f"prompt template markers not found in {SKILL_FILE}")
    return m.group(1), version


def cache_key(hash_a: str, hash_b: str, version: str) -> str:
    return hashlib.sha256((hash_a + hash_b + version).encode()).hexdigest()


def call_claude(prompt: str, model: str, timeout: int = 180) -> str:
    """Return the model's text output (raises on CLI failure)."""
    cmd = ["claude", "-p", prompt, "--model", model] + CLAUDE_FLAGS
    skm.STORE.mkdir(parents=True, exist_ok=True)  # neutral cwd: no project CLAUDE.md / .claude loads
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(skm.STORE))
    out = json.loads(p.stdout)
    if out.get("is_error"):
        raise RuntimeError(str(out.get("result"))[:200])
    return out.get("result", "")


def parse_json_obj(text: str) -> dict:
    """Pull the first {...} object out of the model text (tolerates code fences / prose)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in response")
    return json.loads(m.group(0))


def _normalize(r: dict) -> dict:
    out = dict(UNKNOWN)
    out.update({k: r[k] for k in UNKNOWN if k in r})
    out["overlap"] = max(0.0, min(1.0, float(out["overlap"] or 0)))
    out["confidence"] = max(0.0, min(1.0, float(out["confidence"] or 0)))
    out["conflict"] = bool(out["conflict"])
    return out


def judge_pair(prompt: str, model: str) -> tuple[dict, int]:
    """(result, calls_made). Parse failure -> one retry -> unknown/0. Never raises."""
    calls = 0
    for _ in range(2):
        calls += 1
        try:
            return _normalize(parse_json_obj(call_claude(prompt, model))), calls
        except Exception:
            continue
    return dict(UNKNOWN), calls


def _body(n: dict) -> str:
    """Body without the frontmatter block (the frontmatter is passed separately)."""
    text = n.get("body", "")
    if text.startswith("---"):
        parts = text.split("---", 2)
        text = parts[2] if len(parts) == 3 else text
    return text.lstrip()


def build_prompt(template: str, a: dict, b: dict, hints: list[str]) -> str:
    def fm(n):
        return json.dumps(n.get("frontmatter", {}), ensure_ascii=False)[:800]
    vals = {
        "hints": "; ".join(hints) or "none",
        "a_id": a["id"], "a_kind": a["kind"], "a_frontmatter": fm(a), "a_body": _body(a)[:1500],
        "b_id": b["id"], "b_kind": b["kind"], "b_frontmatter": fm(b), "b_body": _body(b)[:1500],
    }
    out = template
    for k, v in vals.items():  # str.replace, not .format: bodies contain braces
        out = out.replace("{" + k + "}", v)
    return out


def run(nodes: list[dict], candidates: list[dict], limit: int, model: str,
        workers: int = 4, log=print, cache_only: bool = False) -> dict:
    """Judge candidates (already sorted by rule score, highest first).

    Returns {"judgments": [{a,b,result,cached}], "calls": n, "hits": n, "skipped": n, "prompt_version": v}
    """
    template, version = load_prompt()
    by_id = {n["id"]: n for n in nodes}
    cache = load_json(judgments_path(), {"version": 1, "entries": {}})
    entries = cache["entries"]

    # The limit is a window over candidates sorted by rule score (highest first):
    # pairs inside the window are judged (cached ones cost nothing), the rest are deferred.
    # So re-running the same command makes 0 calls; raising --limit widens the window.
    valid = [c for c in candidates if c["a"] in by_id and c["b"] in by_id]
    window = [] if cache_only else valid[:limit]
    in_window = {(c["a"], c["b"]) for c in window}
    results, todo, skipped = [], [], 0
    for c in valid:
        a, b = by_id[c["a"]], by_id[c["b"]]
        key = cache_key(a["hash"], b["hash"], version)
        if key in entries:  # cached verdicts are always used, inside the window or not
            results.append({"a": a["id"], "b": b["id"], "result": entries[key]["result"], "cached": True})
        elif (c["a"], c["b"]) in in_window:
            todo.append((key, a, b, c))
        else:
            skipped += 1
    hits = len(results)

    calls = 0
    if todo:
        log(f"  LLM 판정 {len(todo)}쌍 (model={model}, 동시 {workers})…")

        def work(item):
            key, a, b, c = item
            res, n = judge_pair(build_prompt(template, a, b, c.get("reasons", [])), model)
            return key, a, b, res, n

        with ThreadPoolExecutor(max_workers=workers) as ex:
            for key, a, b, res, n in ex.map(work, todo):
                calls += n
                entries[key] = {"a": a["id"], "b": b["id"], "hash_a": a["hash"], "hash_b": b["hash"],
                                "prompt_version": version, "result": res}
                results.append({"a": a["id"], "b": b["id"], "result": res, "cached": False})
                if res["relation"] == "unknown":
                    log(f"    ! {a['id']} × {b['id']}: JSON 파싱 실패 → unknown/0 으로 기록")
        save_json(judgments_path(), cache)

    if calls == 0:
        log(f"  캐시 히트 {hits}건 — LLM 호출 0회" + (f" (상한/캐시전용으로 {skipped}쌍 보류)" if skipped else ""))
    else:
        log(f"  캐시 히트 {hits}건, 새 LLM 호출 {calls}회" + (f", 상한 초과로 {skipped}쌍 보류" if skipped else ""))
    return {"judgments": results, "calls": calls, "hits": hits, "skipped": skipped, "prompt_version": version}


def edges_from(judgments: list[dict]) -> list[dict]:
    """LLM judgments -> graph edges (requires with direction, overlaps)."""
    edges = []
    for j in judgments:
        r = j["result"]
        conf = r.get("confidence", 0)
        if conf <= 0:
            continue
        if r["relation"] == "requires":
            d = r.get("direction")
            pairs = {"a->b": [(j["a"], j["b"])], "b->a": [(j["b"], j["a"])],
                     "both": [(j["a"], j["b"]), (j["b"], j["a"])]}.get(d, [])
            for s, t in pairs:
                edges.append({"source": s, "target": t, "relation": "requires", "origin": "llm",
                              "confidence": conf, "evidence": "LLM judge"})
        if r.get("overlap", 0) >= 0.6:
            edges.append({"source": j["a"], "target": j["b"], "relation": "overlaps", "origin": "llm",
                          "confidence": round(r["overlap"], 2), "evidence": "LLM trigger overlap"})
    return edges

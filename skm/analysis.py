"""rules -> categorize -> judge -> audit, for one parent mode (day/night)."""
from __future__ import annotations

import os
import re
import time

from . import report_path, save_json
from . import rules, audit, judge, categorize, modes


def llm_settings(cfg: dict):
    llm = cfg.get("llm", {}) or {}
    return (os.environ.get("SKM_MODEL") or llm.get("model") or "haiku",
            int(llm.get("limit", 100)), int(llm.get("workers", 4)))


def analyze(nodes: list, mode: str, *, use_llm: bool, limit: int = None, cache_only: bool = False,
            extra_issues: list = None, log=print) -> dict:
    """Return a report dict. Keys starting with "_" are working data and are not saved.

    use_llm=False / cache_only=True never call `claude -p` (cached verdicts are still used);
    install/uninstall/graph always run that way."""
    cfg = modes.load_config()
    model, default_limit, workers = llm_settings(cfg)
    limit = default_limit if limit is None else limit

    r = rules.infer(nodes)
    cats, cat_calls = categorize.categorize(nodes, cfg, use_llm and not cache_only, model, log=log)
    jr = judge.run(nodes, r["candidates"], limit, model, workers, log=log,
                   cache_only=cache_only or not use_llm)
    edges = r["edges"] + judge.edges_from(jr["judgments"])
    issues = audit.rule_checks(nodes, r["dangling"]) + list(extra_issues or []) + audit.llm_checks(jr["judgments"])
    kept = audit.apply_ignore(issues, cfg.get("ignore"))

    submodes = cfg.get("submodes") or {}
    members = {name: sorted(modes.resolve(name, cfg, nodes, cats, edges)["members"]) for name in submodes}
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "edges": edges,
        "issues": kept,
        "ignored": len(issues) - len(kept),
        "categories": cats,
        "palette": categorize.palette(cfg),
        "modes": dict({"base": sorted(modes.resolve("", cfg, nodes, cats, edges)["members"])}, **members),
        "mode_descriptions": {k: (v or {}).get("description", "") for k, v in submodes.items()},
        "broken": broken_links(r["dangling"], extra_issues or []),
        "candidates": len(r["candidates"]),
        "llm": {"model": model, "calls": jr["calls"] + cat_calls, "cache_hits": jr["hits"],
                "deferred": jr["skipped"], "prompt_version": jr["prompt_version"],
                "judged_pairs": len(jr["judgments"])},
        "_judgments": jr["judgments"],
        "_dangling": r["dangling"],
    }


def save_report(rep: dict) -> None:
    save_json(report_path(rep["mode"]), {k: v for k, v in rep.items() if not k.startswith("_")})


def mode_issues(rep: dict, nodes: list, members: set) -> list:
    """Issues restricted to an active set + 'requires X which is not in this sub-mode'."""
    cfg = modes.load_config()
    inside = [d for d in rep["_dangling"] if d["node"] in members]
    iss = audit.rule_checks([n for n in nodes if n["id"] in members or n["kind"] == "mcp"], inside)
    iss += audit.mode_link_checks(members, rep["edges"])
    iss += audit.llm_checks([j for j in rep["_judgments"] if j["a"] in members and j["b"] in members])
    return audit.apply_ignore(iss, cfg.get("ignore"))


def broken_links(dangling: list, extra_issues: list) -> list:
    """Every reference that points at nothing, for the dashboard's alert banner and ghost nodes:
    {source, target, kind, label, message}. target is a ghost id ("missing:<kind>:<ref>") or ""
    when there is nothing to draw (e.g. a link that leaves the skills folder)."""
    out, seen = [], set()
    for d in dangling:
        key = (d["node"], d["ref"])
        if key in seen:
            continue
        seen.add(key)
        ref = d["ref"].split(":", 1)[-1]
        out.append({"source": d["node"], "target": "missing:{}:{}".format(d["kind"], ref), "kind": d["kind"],
                    "label": ref, "message": "{} -> {} ({}): {}".format(d["node"], d["ref"], d["kind"], d["evidence"])})
    for i in extra_issues:
        m = re.search(r"calls '([^']+)', which mode '[^']+' does not have", i["message"])
        h = re.search(r"\[([\w,]+)\]\s*$", i["message"])   # harnesses where it is missing
        label = (m.group(1) + (" · " + h.group(1) + "에 없음" if h else "")) if m else ""
        out.append({"source": i["nodes"][0], "target": "missing:skill:" + label if m else "",
                    "kind": "skill" if m else "install", "label": label, "message": i["message"]})
    return out


def install_check_issues(lines: list) -> list:
    """install.py dependency_report lines ("name (pkg) ...  [claude]") -> rule errors."""
    out = []
    for line in lines:
        name = line.split(" ", 1)[0]
        out.append({"check": "install_check", "severity": "error", "nodes": ["skill:" + name],
                    "message": line, "origin": "rule"})
    return out

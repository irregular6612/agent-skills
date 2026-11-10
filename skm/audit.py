"""Four checks -> issues[].

  name_conflict          rule  -> error   same skill/agent name from two sources, or two dirs
                                          declaring the same frontmatter name
  broken_link            rule  -> error   reference to a skill/agent/MCP/file that does not exist
                                          (or, inside a mode, a required member that is not active)
  trigger_overlap        LLM   -> warn|info  descriptions would fire on the same requests
  instruction_conflict   LLM   -> warn|info  bodies give contradictory instructions

LLM checks can never produce "error" (capped at warn). The thresholds and the ignore
format are documented in .claude/skills/skm-conflict-audit/SKILL.md.

Issue: {check, severity, nodes:[ids], message, origin: rule|llm, confidence?}
"""
from __future__ import annotations

from collections import defaultdict

WARN_MIN_CONFIDENCE = 0.7     # LLM finding >= this -> warn, else info
OVERLAP_MIN = 0.6             # judge "overlap" score that counts as trigger_overlap


def rule_checks(nodes: list[dict], dangling: list[dict]) -> list[dict]:
    issues = []
    by_name = defaultdict(list)
    by_fm = defaultdict(list)
    for n in nodes:
        if n["kind"] not in ("skill", "agent"):
            continue
        by_name[(n["kind"], n["name"])].append(n)
        fm_name = str(n.get("frontmatter", {}).get("name") or n["name"])
        by_fm[(n["kind"], fm_name)].append(n)
    for (kind, name), lst in by_name.items():
        if len(lst) < 2:
            continue
        if len({n.get("realpath") or n["path"] for n in lst}) == 1:
            continue  # one original reached by two links (SSOT), nothing is shadowed
        own = [n for n in lst if not n.get("plugin")]
        if len(own) > 1:
            issues.append(_issue("name_conflict", "error", [n["id"] for n in lst],
                                 f"{kind} '{name}' exists in {len(lst)} sources: "
                                 + ", ".join(n["source"] for n in lst) + " — one shadows the other"))
        else:  # plugin copies are namespaced (plugin:name), so nothing is shadowed, but both load
            issues.append(_issue("name_conflict", "warn", [n["id"] for n in lst],
                                 f"{kind} '{name}' is installed {len(lst)} times ("
                                 + ", ".join(n["source"] for n in lst) + ") — both load and may trigger together"))
    for (kind, fm_name), lst in by_fm.items():
        dirs = {n["name"] for n in lst}
        if len(dirs) > 1:
            issues.append(_issue("name_conflict", "error", [n["id"] for n in lst],
                                 f"{kind}s {sorted(dirs)} all declare frontmatter name '{fm_name}'"))
    seen = set()
    for d in dangling:
        if (d["node"], d["ref"]) in seen:
            continue
        seen.add((d["node"], d["ref"]))
        issues.append(_issue("broken_link", "error", [d["node"]],
                             f"{d['node']} → {d['ref']} ({d['kind']}): {d['evidence']}"))
    return issues


def mode_link_checks(members: set[str], edges: list[dict]) -> list[dict]:
    """Inside an active set: a member that requires a skill/agent outside the set."""
    issues = []
    for e in edges:
        if e["relation"] == "requires" and e["source"] in members and e["target"] not in members \
                and e["target"].startswith(("skill:", "agent:")) and e.get("confidence", 0) >= 0.6:
            issues.append(_issue("broken_link", "error", [e["source"], e["target"]],
                                 f"{e['source']} requires {e['target']} which is not in this mode"))
    return issues


def llm_checks(judgments: list[dict]) -> list[dict]:
    """judgments: [{a, b, result:{relation,direction,overlap,conflict,conflict_reason,confidence}}]"""
    issues = []
    for j in judgments:
        r = j["result"]
        conf = float(r.get("confidence") or 0)
        if conf <= 0:
            continue
        sev = "warn" if conf >= WARN_MIN_CONFIDENCE else "info"   # never "error"
        if float(r.get("overlap") or 0) >= OVERLAP_MIN:
            issues.append(_issue("trigger_overlap", sev, [j["a"], j["b"]],
                                 f"{j['a']} and {j['b']} may trigger on the same requests "
                                 f"(overlap {float(r['overlap']):.2f})", "llm", conf))
        if r.get("conflict"):
            issues.append(_issue("instruction_conflict", sev, [j["a"], j["b"]],
                                 f"{j['a']} vs {j['b']}: {r.get('conflict_reason') or 'contradictory instructions'}",
                                 "llm", conf))
    return issues


def apply_ignore(issues: list[dict], ignore: list) -> list[dict]:
    """ignore entries (modes.yaml):
         - node: skill:pdf                 # drop every issue touching this node
         - check: trigger_overlap          # drop a check entirely ...
           nodes: [skill:a, skill:b]       # ... or only for this exact node set
    """
    def hit(iss, rule):
        if isinstance(rule, str):
            rule = {"node": rule}
        if "node" in rule and _norm(rule["node"]) in iss["nodes"]:
            return True
        if "check" in rule and rule["check"] == iss["check"]:
            return "nodes" not in rule or set(map(_norm, rule["nodes"])) == set(iss["nodes"])
        return False
    return [i for i in issues if not any(hit(i, r) for r in (ignore or []))]


def _norm(x: str) -> str:
    return x if ":" in x else f"skill:{x}"


def _issue(check, severity, nodes, message, origin="rule", confidence=None):
    if origin == "llm" and severity == "error":
        severity = "warn"
    d = {"check": check, "severity": severity, "nodes": nodes, "message": message, "origin": origin}
    if confidence is not None:
        d["confidence"] = round(confidence, 2)
    return d


def summarize(issues: list[dict]) -> str:
    c = defaultdict(int)
    for i in issues:
        c[i["severity"]] += 1
    return f"error {c['error']} · warn {c['warn']} · info {c['info']}"

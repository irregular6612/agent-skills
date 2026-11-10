"""Rule-based dependency inference (no LLM).

Produces:
  edges       confirmed-by-rule relations  {source,target,relation,origin:"rule",confidence,evidence}
  candidates  pairs worth an LLM look     {a,b,score,reasons}
  dangling    references to things that do not exist (fed to audit as broken_link)

Signals
  1. name reference   body invokes another skill/agent (requires|uses) or only names it (mentions)
  2. mcp__server__     body or allowed-tools uses an MCP tool -> requires mcp:server
  3. allowed-tools    Skill(x) / Agent(x) / Task(x) entries
  4. import           paths into another skill dir (../x/, ~/.claude/skills/x/) and local md links
  5. keyword overlap  description token Jaccard -> overlap candidate only (never an edge)
"""
from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path


# MCP prefixes that are provided outside the scanned config (plugins / claude.ai connectors)
EXTERNAL_MCP_PREFIXES = ("plugin_", "claude_ai_", "claude-in-chrome", "ccd_")

STOPWORDS = set("""
a an the and or of to in on for with by from as at is are be this that it its use used using
when whenever user users asks ask wants want need needs should must can will also any all
skill skills agent agents claude code file files task tasks e.g eg etc via not do does
트리거 사용 사용자 때 경우 요청 위한 하는 있는 같은 등 및 또는 이 그 the
""".split())

CODE_FENCE = re.compile(r"```.*?```", re.S)


def _tokens(text: str) -> set[str]:
    toks = re.findall(r"[a-z][a-z0-9-]{2,}|[가-힣]{2,}", text.lower())
    return {t for t in toks if t not in STOPWORDS}


def _mention_patterns(name: str) -> list[tuple[re.Pattern, str]]:
    """(pattern, strength). 'call' = the text actually invokes it; 'mention' = it is named.
    Names are matched case-sensitively so prose like 'Cloudflare' or 'Implement' does not hit."""
    n = re.escape(name)
    call = [
        rf"subagent_type[\"']?\s*[:=]\s*[\"']{n}[\"']",                  # subagent_type: "name"
        rf"(?:Skill|Agent|Task)\(\s*[\"']?{n}[\"')]",                       # Skill(name)
        rf"(?i:skill tool)[^.\n]{{0,40}}[\"'`]{n}[\"'`]",                    # call the Skill tool with "name"
        rf"(?i:load|invoke|run|call)\s+(?:the\s+)?[`*]*{n}[`*]*\s+(?i:skill|agent|subagent)\b",
    ]
    mention = [
        rf"(?<![\w/-])/{n}(?![\w-])",                                        # /name
        rf"`{n}`",                                                           # `name`
        rf"(?<![\w-]){n}[`*]*\s+(?i:skill|agent|subagent)\b|(?<![\w-]){n}\s*(?:스킬|에이전트)",
    ]
    if "-" in name:  # hyphenated names are specific enough to match bare
        mention.append(rf"(?<![\w/.-]){n}(?![\w-])")
    return [(re.compile(p), "call") for p in call] + [(re.compile(p), "mention") for p in mention]


def infer(nodes: list[dict]) -> dict:
    by_name: dict[str, list[dict]] = {}
    # a bare name resolves to the user's own copy before a plugin's skill of the same name
    for n in sorted(nodes, key=lambda n: bool(n.get("plugin"))):
        if n["kind"] in ("skill", "agent"):
            by_name.setdefault(n["name"], []).append(n)
    # mcp__<server>__ and mcp__plugin_<plugin>_<server>__ tool prefixes -> node id
    mcp_ids = {}
    for n in nodes:
        if n["kind"] == "mcp":
            key = re.sub(r"[^A-Za-z0-9_-]", "_", n["name"])
            mcp_ids["plugin_{}_{}".format(n["plugin"], key) if n.get("plugin") else key] = n["id"]
    sa = [n for n in nodes if n["kind"] in ("skill", "agent")]
    bodies = {n["id"]: n.get("body", "") for n in sa}
    patterns = {name: _mention_patterns(name) for name in by_name}

    edges, dangling = [], []

    def add_edge(src, tgt, rel, conf, ev):
        edges.append({"source": src, "target": tgt, "relation": rel, "origin": "rule",
                      "confidence": round(conf, 2), "evidence": ev[:160]})

    for n in sa:
        body = bodies[n["id"]]
        text = n.get("description", "") + "\n" + body
        prose = CODE_FENCE.sub(" ", body)

        # 1. name mentions
        for name, pats in patterns.items():
            if name == n["name"] or name not in text:  # cheap substring gate before regexes
                continue
            hits = [(p.search(text), strength) for p, strength in pats]
            hits = [(m, st) for m, st in hits if m]
            if not hits:
                continue
            m, strength = next(((m, st) for m, st in hits if st == "call"), hits[0])
            tgt = by_name[name][0]
            if strength == "call":
                add_edge(n["id"], tgt["id"], "uses" if tgt["kind"] == "agent" else "requires", 0.85, _ctx(text, m))
            else:
                add_edge(n["id"], tgt["id"], "mentions", 0.75 if "-" in name else 0.6, _ctx(text, m))

        # 2. mcp__server__tool in body or tools
        refs = set(re.findall(r"mcp__([A-Za-z0-9_-]+?)__", text + " " + " ".join(n.get("tools", []))))
        for srv in sorted(refs):
            if srv in mcp_ids:
                add_edge(n["id"], mcp_ids[srv], "requires", 0.9, f"mcp__{srv}__")
            elif not srv.startswith(EXTERNAL_MCP_PREFIXES) and not n.get("plugin"):
                dangling.append({"node": n["id"], "ref": f"mcp:{srv}", "kind": "mcp",
                                 "evidence": f"mcp__{srv}__ is not configured"})

        # 3. allowed-tools Skill(x)/Agent(x) that do not exist
        for t in n.get("tools", []):
            m = re.match(r"(Skill|Agent|Task)\(\s*[\"']?([\w:-]+)", t)
            if m and m.group(2) not in by_name and ":" not in m.group(2):
                dangling.append({"node": n["id"], "ref": m.group(2), "kind": "tool",
                                 "evidence": f"allowed-tools {t}"})
        for m in re.finditer(r"subagent_type[\"']?\s*[:=]\s*[\"']([\w-]+)[\"']", text):
            if m.group(1) not in by_name and m.group(1) not in ("general-purpose", "Explore", "Plan") \
                    and not n.get("plugin"):
                dangling.append({"node": n["id"], "ref": f"agent:{m.group(1)}", "kind": "agent",
                                 "evidence": m.group(0)})

        # 4. imports: paths into other skills, and local markdown links that don't resolve
        for m in re.finditer(r"(?:\.\./|~/\.claude/skills/|\.claude/skills/)([\w-]+)/", prose):
            name = m.group(1)
            if name in by_name and name != n["name"]:
                add_edge(n["id"], by_name[name][0]["id"], "requires", 0.9, m.group(0))
        if n["kind"] == "skill" and not n.get("plugin"):
            base = Path(n["path"])
            main = CODE_FENCE.sub(" ", n.get("main") or body)  # links in references/ resolve elsewhere
            for m in re.finditer(r"\]\(([^)\s#]+?\.(?:md|py|sh|json|ya?ml|txt))\)", main):
                rel = m.group(1)
                if re.match(r"^[a-z]+://", rel) or rel.startswith(("/", "~", "<", "{")):
                    continue
                if not (base / rel).exists():
                    dangling.append({"node": n["id"], "ref": rel, "kind": "file",
                                     "evidence": f"link ({rel}) not found in {base.name}/"})

    # 5. description keyword overlap -> candidates for LLM
    toks = {n["id"]: _tokens(n["name"].replace("-", " ") + " " + n.get("description", "")) for n in sa}
    edge_pairs = {}
    for e in edges:
        if e["target"].startswith(("skill:", "agent:")):
            k = tuple(sorted((e["source"], e["target"])))
            edge_pairs[k] = max(edge_pairs.get(k, 0), e["confidence"])
    candidates = []
    for a, b in combinations(sa, 2):
        k = tuple(sorted((a["id"], b["id"])))
        ta, tb = toks[a["id"]], toks[b["id"]]
        jac = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
        reasons = []
        if jac >= 0.12:
            reasons.append(f"keyword overlap {jac:.2f}: {', '.join(sorted(ta & tb)[:6])}")
        if k in edge_pairs:
            reasons.append("name reference")
        if reasons:
            candidates.append({"a": k[0], "b": k[1], "score": round(max(jac, edge_pairs.get(k, 0)), 2),
                               "reasons": reasons})
    candidates.sort(key=lambda c: -c["score"])

    edges += _package_edges(nodes)
    return {"edges": _dedupe(edges), "candidates": candidates, "dangling": dangling}


def _package_edges(nodes):
    return [{"source": n["id"], "target": f"pkg:{n['package']}", "relation": "part_of",
             "origin": "rule", "confidence": 1.0, "evidence": "agent-skills state.json"}
            for n in nodes if n.get("package") and n["kind"] in ("skill", "agent")]


def _dedupe(edges):
    best = {}
    for e in edges:
        k = (e["source"], e["target"], e["relation"])
        if k not in best or e["confidence"] > best[k]["confidence"]:
            best[k] = e
    return list(best.values())


def _ctx(text, m, width=50):
    s = max(0, m.start() - width)
    return " ".join(text[s:m.end() + width].split())

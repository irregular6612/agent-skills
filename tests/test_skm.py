"""skm: rule inference, audit severities, sub-mode closure, LLM judge cache/retry, broken links.

Pure-function tests over hand-made nodes; `claude -p` is replaced by a fake, so no network."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import skm  # noqa: E402
from skm import analysis, audit, judge, modes, rules  # noqa: E402


def node(nid, body="", desc="", plugin="", path=None, h="x"):
    kind, name = nid.split(":", 1)
    path = path or "/nonexistent/" + nid.replace(":", "/")
    return {"id": nid, "kind": kind, "name": name.split(":")[-1], "plugin": plugin, "harness": ["claude"],
            "source": "plugin: " + plugin if plugin else "mine", "path": path, "realpath": path,
            "hash": h * 64, "description": desc, "tools": [], "frontmatter": {}, "package": "",
            "body": body, "main": body}


class RulesTest(unittest.TestCase):
    def test_call_is_requires_mention_is_mentions_and_missing_agent_dangles(self):
        nodes = [
            node("skill:writer", 'Call the Skill tool with "citation-check". See also `paper-digest`.\n'
                                 'Use subagent_type: "ghost-agent" for review.', h="a"),
            node("skill:citation-check", h="b"),
            node("skill:paper-digest", h="c"),
        ]
        r = rules.infer(nodes)
        rel = {(e["source"], e["target"]): e["relation"] for e in r["edges"]}
        self.assertEqual(rel[("skill:writer", "skill:citation-check")], "requires")
        self.assertEqual(rel[("skill:writer", "skill:paper-digest")], "mentions")
        self.assertEqual([d["ref"] for d in r["dangling"]], ["agent:ghost-agent"])

    def test_plugin_mcp_tool_names_resolve(self):
        mcp = node("mcp:docs", plugin="cloudflare")
        user = node("skill:u", "uses mcp__plugin_cloudflare_docs__search", h="a")
        r = rules.infer([mcp, user])
        self.assertIn(("skill:u", "mcp:docs", "requires"), {(e["source"], e["target"], e["relation"]) for e in r["edges"]})
        self.assertEqual(r["dangling"], [])


class AuditTest(unittest.TestCase):
    def test_llm_findings_are_never_errors(self):
        j = [{"a": "skill:a", "b": "skill:b",
              "result": {"relation": "related", "overlap": 0.9, "conflict": True, "conflict_reason": "x",
                         "confidence": 0.95}}]
        sev = {i["check"]: i["severity"] for i in audit.llm_checks(j)}
        self.assertEqual(sev, {"trigger_overlap": "warn", "instruction_conflict": "warn"})

    def test_plugin_copy_of_a_skill_is_a_warning_not_an_error(self):
        own, plug = node("skill:wrangler"), node("skill:cloudflare:wrangler", plugin="cloudflare")
        iss = audit.rule_checks([own, plug], [])
        self.assertEqual([(i["check"], i["severity"]) for i in iss], [("name_conflict", "warn")])

    def test_two_links_to_one_original_are_not_a_conflict(self):
        user = node("skill:skm-dep-judge", path="/src/skm-dep-judge")
        proj = dict(node("skill:skm-dep-judge", path="/proj/skm-dep-judge"), id="skill:skm-dep-judge@2",
                    realpath="/src/skm-dep-judge")
        user["realpath"] = "/src/skm-dep-judge"
        self.assertEqual(audit.rule_checks([user, proj], []), [])

    def test_ignore_by_check_and_nodes(self):
        iss = [{"check": "trigger_overlap", "severity": "warn", "nodes": ["skill:a", "skill:b"], "message": ""}]
        self.assertEqual(audit.apply_ignore(iss, [{"check": "trigger_overlap", "nodes": ["a", "b"]}]), [])


class ModesTest(unittest.TestCase):
    def test_base_plus_addon_with_requires_closure_and_exclude(self):
        nodes = [node("skill:" + n) for n in ("pdf", "draft", "cite", "bib", "noise")]
        cfg = {"base": ["pdf"], "submodes": {"paper": {"include": ["draft", "noise"], "exclude": ["noise"]}}}
        edges = [{"source": "skill:draft", "target": "skill:cite", "relation": "requires", "confidence": 0.85},
                 {"source": "skill:cite", "target": "skill:bib", "relation": "requires", "confidence": 0.9},
                 {"source": "skill:draft", "target": "skill:noise", "relation": "mentions", "confidence": 0.75}]
        res = modes.resolve("paper", cfg, nodes, {}, edges)
        self.assertEqual(res["members"], {"skill:pdf", "skill:draft", "skill:cite", "skill:bib"})
        self.assertEqual(res["added_by_closure"], ["skill:bib", "skill:cite"])

    def test_session_links_replace_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            skm.configure(tmp)
            a, b = Path(tmp, "a"), Path(tmp, "b")
            a.mkdir(), b.mkdir()
            nodes = [node("skill:a", path=str(a)), node("skill:b", path=str(b))]
            modes.link_set("s1", {"skill:a"}, nodes, "m1", "day")
            out = modes.link_set("s1", {"skill:b"}, nodes, "m2", "day")
            links = sorted(p.name for p in (modes.session_dir("s1") / ".claude" / "skills").iterdir())
            self.assertEqual((links, out["added"], out["removed"]), (["b"], 1, 1))


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        skm.configure(self.tmp.name)
        self.nodes = [node("skill:a", "A body", h="a"), node("skill:b", "B body", h="b")]
        self.cands = [{"a": "skill:a", "b": "skill:b", "score": 0.5, "reasons": []}]

    def tearDown(self):
        self.tmp.cleanup()

    def test_cache_hit_makes_zero_calls(self):
        reply = json.dumps({"relation": "requires", "direction": "a->b", "overlap": 0.1, "conflict": False,
                            "conflict_reason": "", "confidence": 0.9})
        with mock.patch.object(judge, "call_claude", return_value=reply) as fake:
            first = judge.run(self.nodes, self.cands, 20, "haiku", 1, log=lambda *_: None)
            second = judge.run(self.nodes, self.cands, 20, "haiku", 1, log=lambda *_: None)
        self.assertEqual((first["calls"], second["calls"], second["hits"], fake.call_count), (1, 0, 1, 1))

    def test_bad_json_retries_once_then_unknown(self):
        with mock.patch.object(judge, "call_claude", return_value="not json") as fake:
            out = judge.run(self.nodes, self.cands, 20, "haiku", 1, log=lambda *_: None)
        r = out["judgments"][0]["result"]
        self.assertEqual((fake.call_count, r["relation"], r["confidence"]), (2, "unknown", 0.0))

    def test_limit_window_defers_the_rest(self):
        with mock.patch.object(judge, "call_claude") as fake:
            out = judge.run(self.nodes, self.cands, 0, "haiku", 1, log=lambda *_: None)
        self.assertEqual((fake.call_count, out["skipped"]), (0, 1))


class BrokenLinksTest(unittest.TestCase):
    def test_install_check_line_names_the_missing_harness(self):
        line = "paper-digest (paper-digest) calls 'eli5', which mode 'day' does not have; install eli5:eli5  [codex]"
        b = analysis.broken_links([], analysis.install_check_issues([line]))[0]
        self.assertEqual((b["source"], b["label"]), ("skill:paper-digest", "eli5 · codex에 없음"))


class DashboardTest(unittest.TestCase):
    def test_one_page_holds_every_mode(self):
        from skm import dashboard
        rep = {"edges": [], "issues": [], "generated_at": "t"}
        html = dashboard.render({"day": ([node("skill:a")], rep), "night": ([node("skill:b")], rep)}, "night")
        blob = html.split("const ALL = ", 1)[1].split(";\n", 1)[0]
        data = json.loads(blob.replace("<\\/", "</"))
        self.assertEqual((data["initial"], sorted(data["views"])), ("night", ["day", "night"]))
        self.assertEqual(data["views"]["day"]["inventory"]["nodes"][0]["id"], "skill:a")


class DoctorPlanTest(unittest.TestCase):
    """install.doctor_plan: a fix is offered only when a package ships the skill for that harness."""

    def plan(self, items):
        import install
        cat = {"packages": [{"id": "radar", "group": "mine", "items": items}]}
        cat["by_id"] = {p["id"]: p for p in cat["packages"]}
        env = mock.Mock(harnesses=["codex"])
        with mock.patch.object(install, "mode_skills", return_value={"driller": "driller"}), \
                mock.patch.object(install, "item_path", return_value=Path("/x")), \
                mock.patch.object(install, "skill_files", return_value=[("SKILL.md", "")]), \
                mock.patch.object(install, "skill_calls", return_value={"radar"}):
            return install.doctor_plan(env, cat, mock.Mock(), "day", rep={"broken": [], "issues": []})

    def test_claude_only_package_is_not_offered_as_a_codex_fix(self):
        fixes, manual = self.plan([{"harness": "claude", "dest": "skills/radar", "src": "s"}])
        self.assertEqual(fixes, [])
        self.assertIn("other harnesses only", manual[0])

    def test_package_with_a_codex_item_is_offered(self):
        fixes, _ = self.plan([{"harness": "codex", "dest": "skills/radar", "src": "s"}])
        self.assertEqual([(f["harness"], f["package"]) for f in fixes], [("codex", "radar")])


if __name__ == "__main__":
    unittest.main()

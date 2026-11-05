"""End-to-end tests for install.py in a throwaway HOME.

    python3 -m unittest discover -s tests -v
    AGENT_SKILLS_NETWORK_TESTS=1 python3 -m unittest discover -s tests -v   # + GitHub fetch
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NETWORK = os.environ.get("AGENT_SKILLS_NETWORK_TESTS") == "1"


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / ".claude").mkdir()
        (self.home / ".codex").mkdir()
        self.config = self.home / ".codex" / "config.toml"
        self.config.write_text('model = "x"\n\n[agents.debugger]\nconfig_file = "/elsewhere"\n')
        self.original_config = self.config.read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, ok=True):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "AGENT_SKILLS_STATE")}
        env.update(HOME=str(self.home), USERPROFILE=str(self.home), PYTHONDONTWRITEBYTECODE="1",
                   PATH="/usr/bin:/bin")  # no claude/codex CLIs: plugin steps must be skipped
        proc = subprocess.run([sys.executable, str(REPO / "install.py")] + list(args), env=env,
                              capture_output=True, text=True)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def leftovers(self):
        return sorted(str(p.relative_to(self.home)) for p in self.home.rglob("*")
                      if ".agent-skills" not in p.parts)

    def state(self):
        return json.loads((self.home / ".agent-skills" / "state.json").read_text())


class Helpers(unittest.TestCase):
    def test_minimal_paths_drops_children_of_fetched_parents(self):
        sys.path.insert(0, str(REPO))
        import install
        self.assertEqual(install.minimal_paths({"pstack/skills", "pstack/skills/how", "pstack/LICENSE", "/a/"}),
                         ["a", "pstack/LICENSE", "pstack/skills"])


class Overlay(Sandbox):
    def test_codex_explicit_overlay_links_upstream_and_adds_policy(self):
        sys.path.insert(0, str(REPO))
        import install, argparse
        os.environ["AGENT_SKILLS_STATE"] = str(self.home / ".agent-skills")
        try:
            env = install.Env(argparse.Namespace(harness="codex", dry_run=False, force=False, mode=None, method=None))
        finally:
            del os.environ["AGENT_SKILLS_STATE"]
        src = self.home / ".agent-skills" / "vendor" / "o__r" / "abc" / "skills" / "x"
        (src / "agents").mkdir(parents=True)
        (src / "SKILL.md").write_text("---\nname: x\n---\n")
        (src / "agents" / "openai.yaml").write_text("interface:\n  display_name: X\npolicy:\n  allow_implicit_invocation: true\n")
        out = install.explicit_overlay(env, src)
        self.assertEqual(Path(os.readlink(out / "SKILL.md")), src / "SKILL.md")
        yaml = (out / "agents" / "openai.yaml").read_text()
        self.assertIn("display_name: X", yaml)
        self.assertIn("allow_implicit_invocation: false", yaml)
        self.assertNotIn("allow_implicit_invocation: true", yaml)
        self.assertEqual(src.joinpath("agents", "openai.yaml").read_text().count("true"), 1)  # upstream untouched


class HermesHome(Sandbox):
    def test_skill_links_into_real_home_in_every_mode(self):
        skills = self.home / ".hermes" / "skills"
        skills.mkdir(parents=True)
        (skills / ".usage.json").write_text("{}")  # Hermes' own bookkeeping must survive
        for mode in ("day", "night"):
            self.run_cli("install", "vault-wiki", "--harness", "hermes", "--mode", mode, "-y")
            link = skills / "vault-wiki"
            self.assertTrue(link.is_symlink(), mode)
            self.assertEqual(Path(os.readlink(str(link))), REPO / "sources" / "skills" / "vault-wiki")
            self.assertFalse(skills.is_symlink(), "hermes skills folder must not be wired to a mode")
            self.assertIn("hermes:skills/vault-wiki", self.state()["items"])
            self.run_cli("uninstall", "vault-wiki", "--harness", "hermes", "--mode", mode, "-y")
            self.assertFalse(link.exists() or link.is_symlink(), mode)
        self.assertEqual((skills / ".usage.json").read_text(), "{}")


class OwnPackages(Sandbox):
    def test_catalog_lists_every_package(self):
        out = self.run_cli("list", "--harness", "claude,codex").stdout
        catalog = json.loads((REPO / "catalog.json").read_text())
        for pkg in catalog["packages"]:
            self.assertIn(pkg["id"], out)

    def test_own_sources_exist(self):
        catalog = json.loads((REPO / "catalog.json").read_text())
        for pkg in catalog["packages"]:
            for item in pkg.get("items", []):
                self.assertTrue((REPO / item["src"]).exists(), item["src"])

    def test_link_install_then_uninstall_restores_everything(self):
        before = self.leftovers()
        self.run_cli("install", "ditto-writer", "humanize", "dev-agents", "juhyeon-hooks",
                     "-y", "--harness", "claude,codex")
        skill = self.home / ".claude" / "skills" / "humanize"
        self.assertTrue(skill.is_symlink())
        self.assertEqual(Path(os.readlink(skill)), REPO / "sources" / "skills" / "humanize")
        self.assertTrue((self.home / ".codex" / "skills" / "humanize" / "SKILL.md").is_file())
        config = self.config.read_text()
        self.assertIn("[agents.code-reviewer]", config)
        self.assertEqual(config.count("[agents.debugger]"), 1)  # user's own entry is left alone
        settings = json.loads((self.home / ".claude" / "settings.json").read_text())
        self.assertIn("PostToolUse", settings["hooks"])
        self.assertTrue((self.home / ".agent-skills" / "graph.html").is_file())

        self.run_cli("uninstall", "--all", "-y")
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.assertEqual(self.leftovers(), before)
        self.assertEqual(self.state()["items"], {})

    def test_single_package_uninstall_keeps_the_rest(self):
        self.run_cli("install", "ditto-writer", "humanize", "-y", "--harness", "claude")
        self.run_cli("uninstall", "humanize", "-y")
        self.assertFalse((self.home / ".claude" / "skills" / "humanize").exists())
        self.assertTrue((self.home / ".claude" / "skills" / "ditto-writer").is_symlink())

    def test_existing_item_is_backed_up_and_restored(self):
        mine = self.home / ".claude" / "skills" / "humanize"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("my own humanize")
        self.run_cli("install", "humanize", "-y", "--harness", "claude")
        self.assertTrue(mine.is_symlink())
        self.run_cli("uninstall", "humanize", "-y")
        self.assertEqual((mine / "SKILL.md").read_text(), "my own humanize")

    def test_copy_mode_protects_local_edits(self):
        self.run_cli("install", "ditto-writer", "-y", "--harness", "claude", "--method", "copy")
        skill = self.home / ".claude" / "skills" / "ditto-writer"
        self.assertFalse(skill.is_symlink())
        (skill / "SKILL.md").write_text("edited locally")
        proc = self.run_cli("uninstall", "ditto-writer", "-y")
        self.assertIn("changed after install", proc.stderr)
        self.assertTrue(skill.exists())
        self.run_cli("uninstall", "ditto-writer", "-y", "--force")
        self.assertFalse(skill.exists())

    def test_config_created_for_agents_is_removed_again(self):
        self.config.unlink()
        self.run_cli("install", "dev-agents", "-y", "--harness", "codex")
        self.assertIn("[agents.debugger]", self.config.read_text())
        self.run_cli("uninstall", "--all", "-y")
        self.assertFalse(self.config.exists())

    def test_dry_run_changes_nothing(self):
        before = self.leftovers()
        self.run_cli("install", "--preset", "mine", "--dry-run", "--harness", "claude,codex")
        self.assertEqual(self.leftovers(), before)
        self.assertFalse((self.home / ".agent-skills" / "state.json").exists())

    def test_day_folders_are_links_into_modes_day(self):
        self.run_cli("install", "ditto-writer", "-y", "--harness", "claude")
        skills = self.home / ".claude" / "skills"
        self.assertTrue(skills.is_symlink())
        self.assertEqual(Path(os.readlink(skills)), self.home / ".agent-skills" / "modes" / "day" / "claude" / "skills")

    def test_night_mode_is_separate_but_shares_history(self):
        (self.home / ".claude" / "projects").mkdir()
        (self.home / ".claude.json").write_text("{}")
        self.run_cli("install", "ditto-writer", "-y", "--harness", "claude", "--mode", "night")
        self.run_cli("install", "aha", "-y", "--harness", "claude")
        night = Path(self.run_cli("home", "night", "claude").stdout.strip())
        self.assertTrue((night / "skills" / "ditto-writer" / "SKILL.md").is_file())
        self.assertFalse((night / "skills" / "aha").exists())
        self.assertFalse((self.home / ".claude" / "skills" / "ditto-writer").exists())
        self.assertTrue((self.home / ".claude" / "skills" / "aha").exists())
        self.assertEqual(Path(os.readlink(night / "projects")), self.home / ".claude" / "projects")
        self.assertEqual(Path(os.readlink(night / ".claude.json")), self.home / ".claude.json")
        self.assertEqual(Path(self.run_cli("home", "day", "claude").stdout.strip()), self.home / ".claude")

    def test_night_codex_config_registers_only_night_agents(self):
        self.run_cli("install", "dev-agents", "-y", "--harness", "codex", "--mode", "night")
        night = Path(self.run_cli("home", "night", "codex").stdout.strip())
        night_cfg = (night / "config.toml").read_text()
        self.assertIn(str(night / "agents" / "code-reviewer.toml"), night_cfg)
        self.assertNotIn("[agents.debugger]\nconfig_file = \"/elsewhere\"", night_cfg)
        self.assertNotIn("code-reviewer", self.config.read_text())  # main (day) config untouched
        self.assertIn('model = "x"', night_cfg)
        self.run_cli("uninstall", "dev-agents", "-y", "--mode", "night")
        self.assertNotIn("code-reviewer", (night / "config.toml").read_text())

    def test_graph_links_skills_to_their_subagents(self):
        self.run_cli("install", "humanize", "paper-driller", "-y", "--harness", "claude")
        data = json.loads(self.run_cli("graph", "--json").stdout)
        edges = {(e["source"], e["target"]) for e in data["edges"]}
        self.assertIn(("skill:humanize", "agent:humanize-ko-detector"), edges)
        self.assertIn(("skill:paper-driller", "agent:paper-spine"), edges)


@unittest.skipUnless(NETWORK, "set AGENT_SKILLS_NETWORK_TESTS=1 to fetch from GitHub")
class ThirdParty(Sandbox):
    def test_fetch_one_skill_from_upstream_and_remove_it(self):
        self.run_cli("install", "k-dense:literature-review", "eli5", "-y", "--harness", "claude")
        skill = self.home / ".claude" / "skills" / "literature-review"
        self.assertTrue((skill / "SKILL.md").is_file())
        self.assertFalse((self.home / ".claude" / "skills" / "scientific-writing").exists())
        rec = self.state()["items"]["day:claude:skills/literature-review"]
        self.assertTrue(rec["origin"].startswith("K-Dense-AI/scientific-agent-skills@"))
        self.run_cli("uninstall", "--all", "-y")
        self.assertFalse(skill.exists())


if __name__ == "__main__":
    unittest.main()

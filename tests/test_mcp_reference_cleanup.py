"""Offline regression guards for the approved paper-tool reference cleanup."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRILLER = ROOT / 'sources/skills/paper-driller'
BANANA = ROOT / 'sources/skills/paper-banana/SKILL.md'
LEGACY_CLAUDE = ROOT / 'claude-code/juhyeon/paper-workflow/skills/paper-driller/SKILL.md'
LEGACY_CODEX = ROOT / 'codex/skills/paper-driller/SKILL.md'


class MCPReferenceCleanupTests(unittest.TestCase):
    def test_arxiv_mcp_removed_from_owned_workflows(self):
        paths = [DRILLER / 'SKILL.md', DRILLER / 'references/workflow.md',
                 DRILLER / 'references/legacy-workflow.md', LEGACY_CLAUDE, LEGACY_CODEX]
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text()
                self.assertNotIn('mcp__arxiv__', text)
                self.assertNotIn('arXiv MCP', text)

    def test_shared_and_codex_allowlists_do_not_require_claude_mcp(self):
        for path in (DRILLER / 'SKILL.md', LEGACY_CODEX):
            with self.subTest(path=path):
                self.assertNotIn('mcp__', path.read_text().split('---', 2)[1])
        self.assertNotIn('mcp__', LEGACY_CODEX.read_text())

    def test_shared_collection_paths_gate_tools_and_coverage(self):
        paths = [DRILLER / 'SKILL.md', DRILLER / 'references/workflow.md',
                 DRILLER / 'references/legacy-workflow.md']
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text()
                for required in ('웹/PDF 수집이 기본 경로', '노출된 경우에만',
                                 '인증·권한이 확인된 경우에만', 'Codex에서 이 서버들을 필수로 요구하거나 자동 등록하지 않는다',
                                 '사용자가 제공한 PDF·텍스트만', '검색 결과·초록·웹 요약은 전문이 아니다',
                                 'abstract-only', 'fulltext'):
                    self.assertIn(required, text)

    def test_supported_claude_research_servers_remain_optional(self):
        text = (DRILLER / 'SKILL.md').read_text()
        for name in ('mcpsemanticscholar', 'paper-search-mcp-openai-v2'):
            self.assertIn(name, text)
        legacy = LEGACY_CLAUDE.read_text()
        self.assertIn('mcp__mcpsemanticscholar__get-paper-abstract', legacy)
        self.assertIn('mcp__paper-search-mcp-openai-v2__search_arxiv', legacy)
        self.assertIn('인증·권한이 확인된 경우에만', legacy)

    def test_banana_cli_default_and_unavailable_stop(self):
        for path in (BANANA, ROOT / 'codex/skills/paper-banana/SKILL.md'):
            with self.subTest(path=path):
                text = path.read_text()
                self.assertIn('Codex는 아래 CLI 경로를 기본으로 사용한다', text)
                self.assertIn('CLI `paperbanana generate`로 생성', text)
                self.assertIn('사용자 승인을 먼저 확인', text)
                self.assertIn('생성·평가 기능을 사용할 수 없다고 알리고 중단', text)
        legacy = (ROOT / 'codex/skills/paper-banana/SKILL.md').read_text()
        self.assertNotIn('mcp__paperbanana__', legacy)
        self.assertNotIn('```jsonc', legacy)
        self.assertNotIn('✓ Connected', legacy)
        shared = BANANA.read_text()
        self.assertIn('Claude 이름 예시', shared)
        self.assertIn('mcp__paperbanana__generate_diagram', shared)

    def test_both_harnesses_still_discover_same_canonical_sources(self):
        entries = json.loads((ROOT / 'manifest.yaml').read_text())['links']
        for name in ('paper-driller', 'paper-banana'):
            owned = [item for item in entries if item['destination'] == 'skills/' + name]
            self.assertEqual({item['harness'] for item in owned}, {'claude', 'codex'})
            self.assertEqual({item['source'] for item in owned}, {'sources/skills/' + name})


if __name__ == '__main__':
    unittest.main()

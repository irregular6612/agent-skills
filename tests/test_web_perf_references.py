"""Regression coverage for bare Chrome APIs, permission gates and external exceptions."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
REL = 'sources/skills/web-perf-codex/SKILL.md'
spec = importlib.util.spec_from_file_location('mcp_reference_audit', ROOT / 'tools/mcp_reference_audit.py')
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class WebPerfReferenceTests(unittest.TestCase):
    def test_original_missing_bare_calls_are_detected(self):
        text = 'Try calling `navigate_page` or `performance_start_trace`.\nAsk the user to add this chrome-devtools MCP.\nnpx chrome-devtools-mcp@latest'
        rows = audit.audit_document('/fixture/SKILL.md', text, 'codex', {'hermes-tools', 'node_repl'})
        self.assertEqual({r['classification'] for r in rows}, {'UNSUPPORTED_REFERENCE'})
        self.assertEqual({r['token'] for r in rows if r['kind'] == 'bare-tool'}, {'navigate_page', 'performance_start_trace'})
        self.assertIn('installation-recommendation', {r['kind'] for r in rows})

    def test_explicit_and_prose_are_distinct(self):
        rows = audit.extract_references('mcp__chrome-devtools__navigate_page\nChrome DevTools MCP required\nnavigate_page')
        self.assertEqual([r['kind'] for r in rows], ['explicit-token', 'prose-dependency', 'bare-tool'])

    def test_owned_document_has_full_gate_and_conditional_apis(self):
        text = (ROOT / REL).read_text()
        self.assertTrue(audit.chrome_gate_valid(text))
        rows = audit.audit_document(ROOT / REL, text, 'codex', {'hermes-tools', 'node_repl'}, conditional_chrome=True)
        self.assertTrue(rows)
        self.assertEqual({r['classification'] for r in rows}, {'CONDITIONAL_DOCUMENTATION'})
        self.assertEqual({r['token'] for r in rows if r['kind'] == 'bare-tool'}, set(audit.CHROME_APIS))
        for phrase in ('Available retrieval and static analysis (default)', 'Already installed, user-approved CLI',
                       'Never fabricate metric values', 'not measured', 'a Lighthouse lab run does not establish field INP'):
            self.assertIn(phrase, text)

    def test_conditional_heading_cannot_mask_reintroduced_probe(self):
        for instruction in ('Try calling navigate_page before checking availability.',
                            'Run npx -y chrome-devtools-mcp', 'Install chrome-devtools first.'):
            with self.subTest(instruction=instruction):
                text = (ROOT / REL).read_text() + '\n' + instruction
                self.assertFalse(audit.chrome_gate_valid(text))
                rows = audit.audit_document(ROOT / REL, text, 'codex', set(), conditional_chrome=True)
                self.assertTrue(any(r['classification'] == 'UNSUPPORTED_REFERENCE' for r in rows))

    def test_removing_any_gate_requirement_fails(self):
        text = (ROOT / REL).read_text()
        for requirement in audit.GATE:
            with self.subTest(requirement=requirement):
                self.assertFalse(audit.chrome_gate_valid(text.replace(requirement, 'REMOVED')))

    def test_external_exception_is_exact_and_not_keep(self):
        plan = json.loads((ROOT / 'docs/mcp-web-perf-addendum.json').read_text())
        exception = plan['exceptions'][0]
        self.assertTrue(plan['new_server_rows'][1]['ask_user_question'])
        text = 'Try calling navigate_page or performance_start_trace with chrome-devtools.'
        rows = audit.audit_document(exception['file'], text, 'claude', set(), plan['exceptions'])
        self.assertEqual({r['classification'] for r in rows}, {'ASK_USER'})
        for path, harness in ((exception['file'] + '.other', 'claude'), (exception['file'], 'codex')):
            rows = audit.audit_document(path, text, harness, set(), plan['exceptions'])
            self.assertEqual({r['classification'] for r in rows}, {'UNSUPPORTED_REFERENCE'})

    def test_unreviewed_document_cannot_claim_conditional_status(self):
        text = (ROOT / REL).read_text()
        rows = audit.audit_document('/unreviewed/SKILL.md', text, 'codex', set())
        self.assertEqual({r['classification'] for r in rows}, {'UNSUPPORTED_REFERENCE'})

    def test_discovery_frontmatter_unchanged_from_exact_candidate(self):
        before = subprocess.check_output(['git', 'show', 'a31b12ab6f880944fecdf38e7a999015daa54575:' + REL], cwd=ROOT, text=True)
        self.assertEqual(before.split('---', 2)[1], (ROOT / REL).read_text().split('---', 2)[1])
        links = json.loads((ROOT / 'manifest.yaml').read_text())['links']
        codex = [r for r in links if r['harness'] == 'codex' and r['destination'] == 'skills/web-perf']
        self.assertEqual([r['source'] for r in codex], ['sources/skills/web-perf-codex'])


if __name__ == '__main__':
    unittest.main()

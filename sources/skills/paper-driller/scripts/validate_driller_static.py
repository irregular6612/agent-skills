"""Portable static contract check; never imports local vault/frontmatter code."""
import json
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
REPO = SKILL.parents[2]
EXPECTED = ['type', 'Reading-Status', 'Read-Depth', 'Author', 'Journal/Conference', 'Published Year', 'Topic', 'Review-Date', 'Comment', 'URL', 'Category', 'linked-bases', 'Lab']

def main():
    schema = json.loads((SKILL/'references/paper-schema.json').read_text())
    assert schema['frontmatter']['keys'] == EXPECTED
    assert schema['schema_version'] == 4
    for path in ('SKILL.md', 'references/workflow.md', 'references/legacy-workflow.md', 'references/insight-digest-spec.md', 'references/readability-spec.md', 'references/preread-v2-spec.md'):
        assert (SKILL/path).is_file(), path
    text = (SKILL/'SKILL.md').read_text()
    for token in ('Paper Driller v3', '--template', 'paper-note-v3', 'DRILLER:meta', '--approved-switch', 'USER:notes', 'not-seen'):
        assert token in text, token
    validator = REPO/'sources/hooks/claude/paper-format-validator.py'
    for template in sorted((SKILL/'references/templates').glob('*.md')):
        p = subprocess.run([sys.executable, str(validator), '--check-template', str(template)], text=True, capture_output=True)
        assert p.returncode == 0, (template, p.stdout, p.stderr)
        print('PASS template:', template.name)
    print('PASS canonical v3/schema v4 contract; SKIPPED local vault engine, unmanaged hooks, model execution')
    return 0

if __name__ == '__main__':
    sys.exit(main())

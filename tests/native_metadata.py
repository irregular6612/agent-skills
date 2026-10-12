"""Source metadata oracle for the approved scalar frontmatter subset (stdlib)."""
import json
import re


def front(path):
    text = path.read_text()
    assert text.startswith('---\n'), str(path)
    lines = text.split('---', 2)[1].splitlines()
    result = {}
    for i, line in enumerate(lines):
        match = re.match(r'^(name|description|argument-hint):[ \t]*(.*)$', line)
        if not match:
            continue
        key, value = match.groups()
        assert key not in result, (path, key)
        if value in ('>-', '>', '|-', '|'):
            block = []
            for row in lines[i+1:]:
                if row and not row[0].isspace():
                    break
                block.append(row.strip())
            value = (' ' if value.startswith('>') else '\n').join(block).rstrip()
            if not match[2].endswith('-'):
                value += '\n'
        elif value.startswith('"'):
            value = json.loads(value)
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1].replace("''", "'")
        result[key] = value
    return result


def claude_entry(root, entry, response):
    category = entry['destination'].split('/')[0]
    path = root / entry['source']
    meta = front(path / 'SKILL.md' if category == 'skills' else path)
    name = meta.get('name', path.name) if category != 'commands' else __import__('pathlib').Path(entry['destination']).stem
    items = response['agents'] if category == 'agents' else response['commands']
    found = [item for item in items if item['name'] == name]
    expected = meta['description'].replace('\\n', '\n') if category == 'agents' else meta['description']
    actual = found[0].get('description') if len(found) == 1 else None
    normalized = actual
    if category != 'agents' and isinstance(actual, str) and actual.endswith(' (user)'):
        normalized = actual[:-7]
    hint = found[0].get('argumentHint') if len(found) == 1 else None
    expected_hint = meta.get('argument-hint')
    # Native displays the contents of the source's bracketed hint.
    if expected_hint and expected_hint.startswith('[') and expected_hint.endswith(']'):
        expected_hint = expected_hint[1:-1]
    return {'category': category, 'destination': entry['destination'], 'name': name,
            'expected_description': expected, 'runtime_description': actual,
            'argument_hint': hint, 'expected_argument_hint': expected_hint,
            'recognized': len(found) == 1 and normalized == expected and
                (category != 'commands' or hint == expected_hint)}

"""Offline reference extraction; not a complete natural-language safety proof."""
import re
from pathlib import Path

EXPLICIT = re.compile(r'mcp__([A-Za-z0-9_-]+?)__[A-Za-z0-9_.*-]*')
CHROME_APIS = ('navigate_page', 'performance_start_trace', 'performance_analyze_insight',
               'list_network_requests', 'get_network_request', 'take_snapshot')
BARE = re.compile(r'(?<![\w])(?:' + '|'.join(CHROME_APIS) + r')(?![\w])')
CHROME = re.compile(r'chrome-devtools(?:-mcp)?|Chrome DevTools MCP', re.I)
GATE = (
    "Inspect the current session's actual tool list and permissions",
    'Do not probe availability by calling an absent tool',
    'Do not install or register chrome-devtools or any other MCP server automatically',
    'every required API is present in the current exposed tool list',
    'authentication, permissions and the target are authorized',
    'Skip any phase whose required tools are absent',
    'performance trace, measured Core Web Vitals and runtime accessibility measurement are unavailable',
    'stop that scope safely',
    '## Conditional Chrome DevTools API Reference and Workflow',
)


def chrome_gate_valid(text):
    return (all(s in text for s in GATE)
            and not re.search(r'Try calling|Ask the user to add this|chrome-devtools-mcp|(?:^|\n)(?:Install|Run npx|Register)\b', text, re.I)
            and text.index(GATE[0]) < text.index(GATE[-1]))


def extract_references(text):
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        explicit = list(EXPLICIT.finditer(line))
        for match in explicit:
            rows.append(dict(line=number, token=match[0], server=match[1], kind='explicit-token'))
        # Avoid double-counting a prefixed API as a bare name.
        for match in BARE.finditer(line):
            if not any(m.start() <= match.start() < m.end() for m in explicit):
                rows.append(dict(line=number, token=match[0], server='chrome-devtools', kind='bare-tool'))
        chrome = CHROME.search(line)
        if chrome and not any(m.start() <= chrome.start() < m.end() for m in explicit):
            kind = ('installation-recommendation' if re.search(r'npx|Ask the user to add|command|install', line, re.I)
                    else 'prose-dependency')
            if kind == 'installation-recommendation' and 'Do not install or register' in line:
                kind = 'installation-prohibition'
            rows.append(dict(line=number, token=chrome[0], server='chrome-devtools', kind=kind))
    return rows


def audit_document(path, text, harness, configured, exceptions=(), conditional_chrome=False):
    """Exceptions must match exact file, harness and server and carry a reason."""
    rows = extract_references(text)
    for row in rows:
        row.update(file=str(path), harness=harness)
        exception = next((e for e in exceptions if
                          Path(e['file']).resolve() == Path(path).resolve()
                          and e['harness'] == harness and e['server'] == row['server']
                          and e.get('class') == 'ASK_USER' and e.get('reason')), None)
        if exception:
            classification, reason = 'ASK_USER', exception['reason']
        elif row['server'] == 'chrome-devtools' and conditional_chrome and chrome_gate_valid(text):
            classification, reason = 'CONDITIONAL_DOCUMENTATION', 'Reviewed exposure/permission gate; no default installation or probe'
        elif row['server'] in configured:
            classification, reason = 'CONFIGURED', 'Registration name only; exposure/permission still required'
        else:
            classification, reason = 'UNSUPPORTED_REFERENCE', 'Absent registration and no reviewed conditional path or exact ASK_USER exception'
        row.update(classification=classification, reason=reason)
    return rows

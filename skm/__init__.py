"""skm — dependency analysis, LLM checks, dashboard and sub-modes on top of agent-skills.

install.py does the scanning (Inventory); skm turns the scan into graph edges, issues,
categories and per-session skill sets. Standard library only (Python 3.9+).
Runtime data lives in <state_dir>/skm/ (default ~/.agent-skills/skm/); configure() points it
elsewhere (install.py passes env.state_dir, which honours AGENT_SKILLS_STATE).
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent          # agent-skills checkout
CONFIG = REPO / "submodes.json"                         # base, submodes, categories, ignore, llm
SKILLS_SRC = REPO / "sources" / "skills"                # skm-dep-judge etc. (prompt templates)
STORE = Path.home() / ".agent-skills" / "skm"


def configure(state_dir):
    global STORE
    STORE = Path(state_dir) / "skm"


def judgments_path():
    return STORE / "judgments.json"


def report_path(mode):
    return STORE / "report-{}.json".format(mode)


def sessions_dir():
    return STORE / "sessions"


def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

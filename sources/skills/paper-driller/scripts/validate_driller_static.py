"""Static check for the paper-driller skill: docs agree with the vault checker, and its tests pass."""
import os
import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
VAULT = Path(os.environ.get("PAPER_VAULT_ROOT") or
             Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes")


def main():
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    spec = (SKILL / "references/note-spec.md").read_text(encoding="utf-8")
    for token in ("general-v2", "paper_note.py", "paper_figures.py", "references/note-spec.md", "--previous"):
        assert token in skill, f"SKILL.md lacks {token}"
    tools = VAULT / "Public/_tools"
    if not (tools / "paper_note.py").is_file():
        print("SKIPPED: vault checker not found at", tools)
        return 0
    sys.path.insert(0, str(tools))
    import paper_note as pn  # noqa: E402
    for title, limit in pn.BUDGET.items():
        assert re.search(rf"`## {re.escape(title)}` \| {limit:,} \|", spec), f"note-spec budget for {title} != {limit}"
    for key in pn.FRONTMATTER_KEYS:
        assert f"| `{key}` |" in spec, f"note-spec lacks frontmatter key {key}"
    r = subprocess.run([sys.executable, "-m", "unittest", "tests.test_paper_note"], cwd=tools,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    print("CHECKED: SKILL.md tokens, note-spec budgets and keys match paper_note.py, checker tests pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

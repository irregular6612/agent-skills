"""Sub-modes on top of day/night: base + add-on merge, requires-closure, session folders, prune.

A sub-mode (paper, autopilot-code, ...) picks a subset of the skills/agents installed in a
parent mode (day or night). Session folder layout (under <state_dir>/skm/sessions/<id>/):
  session.json
  .claude/skills/<name>      -> real skill dir
  .claude/agents/<name>.md   -> real agent file
`claude` starts with `--setting-sources project,local --settings ~/.claude/settings.json
--add-dir <session>`, so only the session's skills/agents (plus plugins and built-ins) load.
Nothing in modes/<day|night>/ or ~/.claude is changed.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
from pathlib import Path

import skm
from . import CONFIG, load_json, save_json

CLOSURE_MIN_CONFIDENCE = 0.6


def load_config() -> dict:
    return load_json(CONFIG, {}) or {}


def _norm(x: str) -> str:
    return x if ":" in x else "skill:" + x


def resolve(mode_expr: str, cfg: dict, nodes: list, categories: dict, edges: list) -> dict:
    """mode_expr like "paper" or "paper+office" ("" = base only). Returns
    {members, added_by_closure, missing, unknown_modes}. Plugin skills are never members:
    plugins load on their own in every session."""
    modes = cfg.get("submodes", {}) or {}
    ids = {n["id"] for n in nodes if n["kind"] in ("skill", "agent") and not n.get("plugin")}
    members, missing, unknown = set(), [], []

    def add(x):
        x = _norm(x)
        (members.add(x) if x in ids else missing.append(x))

    for x in cfg.get("base", []) or []:
        add(x)
    for name in [m for m in mode_expr.split("+") if m]:
        spec = modes.get(name)
        if spec is None:
            unknown.append(name)
            continue
        cats = set(spec.get("categories", []) or [])
        for nid in ids:
            if categories.get(nid) in cats:
                members.add(nid)
        for x in spec.get("include", []) or []:
            add(x)
        for x in spec.get("exclude", []) or []:
            members.discard(_norm(x))

    req = {}
    for e in edges:
        if e["relation"] in ("requires", "uses") and e.get("confidence", 0) >= CLOSURE_MIN_CONFIDENCE \
                and e["target"] in ids:
            req.setdefault(e["source"], set()).add(e["target"])
    added, stack = [], list(members)
    while stack:
        cur = stack.pop()
        for t in req.get(cur, ()):
            if t not in members:
                members.add(t)
                added.append(t)
                stack.append(t)
    return {"members": members, "added_by_closure": sorted(added), "missing": missing,
            "unknown_modes": unknown}


# ---------- session folders ----------

def session_dir(sid: str) -> Path:
    return skm.sessions_dir() / sid


def new_session_id(mode_expr: str) -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + mode_expr.replace("+", "_")


def prepare(sid: str) -> Path:
    """Create the session folder BEFORE any link is swapped."""
    d = session_dir(sid)
    (d / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
    (d / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
    return d


def link_set(sid: str, members: set, nodes: list, mode_expr: str, parent: str) -> dict:
    """Make the session's links match `members` exactly. Links are replaced in place
    (tmp link + os.replace) so the skills/ dir itself stays put for a running session."""
    d = prepare(sid)
    by_id = {n["id"]: n for n in nodes}
    want = {}
    for m in members:
        n = by_id.get(m)
        if not n or "claude" not in n.get("harness", ["claude"]):
            continue
        if n["kind"] == "skill":
            want[d / ".claude" / "skills" / Path(n["path"]).name] = n["realpath"]
        elif n["kind"] == "agent" and n["path"].endswith(".md"):
            # named by the agent's own (unique) name: two folders may both hold academic-reviewer.md
            want[d / ".claude" / "agents" / (n["name"] + ".md")] = n["realpath"]
    added = removed = 0
    for sub in ("skills", "agents"):
        for p in (d / ".claude" / sub).iterdir():
            if p not in want and p.is_symlink():
                p.unlink()
                removed += 1
    for link, target in want.items():
        if link.is_symlink() and os.readlink(str(link)) == target:
            continue
        tmp = link.with_name(link.name + ".skmtmp")
        if tmp.is_symlink():
            tmp.unlink()
        tmp.symlink_to(target)
        os.replace(str(tmp), str(link))
        added += 1
    now = dt.datetime.now().isoformat(timespec="seconds")
    old = load_json(d / "session.json", {}) or {}
    save_json(d / "session.json", {"id": sid, "mode": mode_expr, "parent": parent, "updated_at": now,
                                   "created_at": old.get("created_at", now), "members": sorted(members)})
    return {"dir": d, "added": added, "removed": removed, "total": len(want)}


def claude_args(sid: str) -> list:
    d = session_dir(sid)
    args = ["--setting-sources", "project,local"]
    user_settings = Path.home() / ".claude" / "settings.json"
    if user_settings.exists():
        args += ["--settings", str(user_settings)]
    return args + ["--add-dir", str(d)]


def list_sessions() -> list:
    root = skm.sessions_dir()
    if not root.exists():
        return []
    out = []
    for d in sorted(root.iterdir()):
        meta = load_json(d / "session.json")
        if meta:
            out.append(meta)
    return out


# ---------- prune ----------

def prune_plan(nodes: list, cfg: dict, categories: dict, edges: list, days: int) -> dict:
    """Stale session folders to archive, and installed skills/agents that no sub-mode uses.
    Installed items are only REPORTED (removing them is `install.py uninstall`'s job)."""
    in_any = set(resolve("", cfg, nodes, categories, edges)["members"])
    for name in (cfg.get("submodes") or {}):
        in_any |= resolve(name, cfg, nodes, categories, edges)["members"]
    unused = [n for n in nodes if n["kind"] in ("skill", "agent") and not n.get("plugin")
              and n["id"] not in in_any]
    cutoff = dt.datetime.now() - dt.timedelta(days=days)
    stale = [s for s in list_sessions()
             if dt.datetime.fromisoformat(s.get("updated_at", s.get("created_at"))) < cutoff]
    return {"unused": unused, "stale_sessions": stale}


def prune_apply(plan: dict) -> list:
    dest_root = skm.STORE / "archive" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    moved = []
    for s in plan["stale_sessions"]:
        src = session_dir(s["id"])
        dest = dest_root / "sessions" / s["id"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append("{} -> {}".format(src, dest))
    if moved:
        (dest_root / "manifest.json").write_text(json.dumps(moved, ensure_ascii=False, indent=2), encoding="utf-8")
    return moved

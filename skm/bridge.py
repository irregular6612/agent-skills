"""install.py Inventory nodes -> skm node schema.

Inventory node: {id, type, name, plugin, harness[], source, path, desc, text}
skm node:       {id, kind, name, plugin, harness, source, path, realpath, hash, description,
                 tools, frontmatter, package, body (SKILL.md + references), main (SKILL.md only)}

hash is sha256 of the main file only (SKILL.md / agent file), the same rule as the standalone
skm-project, so judgments.json entries stay valid across both.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path


def _main_file(n: dict) -> Path:
    p = Path(n["path"])
    return p / "SKILL.md" if n["type"] == "skill" else p


def _frontmatter(text: str) -> dict:
    """Top-level scalar keys (same tiny reader idea as install.py) plus allowed-tools/tools lists."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out = {}
    for line in parts[1].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m and m.group(2).strip() not in (">", ">-", "|", "|-", ""):
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    m = re.search(r"^\s+category:\s*(\S+)", parts[1], re.M)   # metadata.category
    if m and "category" not in out:
        out["category"] = m.group(1).strip("'\"")
    return out


def _tools(fm: dict) -> list:
    raw = fm.get("allowed-tools") or fm.get("tools") or ""
    raw = raw.strip("[]")
    return [t.strip().strip("'\"") for t in re.split(r",\s*|\s+(?![^(]*\))", raw) if t.strip()]


def package_map(state_items: dict) -> dict:
    out = {}
    for it in state_items.values():
        tgt, pkg = it.get("target"), it.get("package")
        if tgt and pkg:
            out[os.path.realpath(tgt)] = pkg
    return out


def from_inventory(inv_nodes, state_items: dict) -> list:
    pkgs = package_map(state_items)
    out = []
    for n in inv_nodes:
        kind = n["type"]
        node = {"id": n["id"], "kind": kind, "name": n["name"], "plugin": n.get("plugin") or "",
                "harness": list(n.get("harness", [])), "source": n.get("source", ""),
                "path": n.get("path", ""), "realpath": "", "hash": "", "description": n.get("desc", ""),
                "tools": [], "frontmatter": {}, "package": "", "body": n.get("text", ""), "main": ""}
        if kind in ("skill", "agent"):
            f = _main_file(n)
            try:
                raw = f.read_bytes()
            except OSError:
                raw = node["body"].encode()
            node["hash"] = hashlib.sha256(raw).hexdigest()
            node["realpath"] = os.path.realpath(n["path"])
            node["main"] = raw.decode("utf-8", errors="replace")  # main file only: local links resolve here
            fm = _frontmatter(node["main"])
            node["frontmatter"] = fm
            node["tools"] = _tools(fm)
            node["package"] = pkgs.get(node["realpath"], "")
        out.append(node)
    for p in sorted({n["package"] for n in out if n["package"]}):
        out.append({"id": "pkg:" + p, "kind": "package", "name": p, "plugin": "", "harness": [],
                    "source": "agent-skills", "path": "", "realpath": "", "hash": "", "description": "",
                    "tools": [], "frontmatter": {}, "package": "", "body": "", "main": ""})
    return out

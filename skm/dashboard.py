"""Render the dashboard (one HTML file, data inlined, Cytoscape.js from CDN).

One page holds every mode (day, night): a toggle in the header switches between them."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("dashboard_template.html")


def _view(nodes: list, report: dict, mode: str) -> dict:
    slim = [{k: n.get(k) for k in ("id", "kind", "name", "plugin", "harness", "source", "path",
                                   "package", "description")} for n in nodes]
    return {"inventory": {"nodes": slim, "mode": mode},
            "report": {k: v for k, v in report.items() if not k.startswith("_")}}


def render(views: dict, initial: str) -> str:
    """views = {mode: (nodes, report)}; `initial` is the mode shown when the page opens."""
    data = {"initial": initial, "views": {m: _view(n, r, m) for m, (n, r) in views.items()}}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__SKM_DATA__*/null", blob)

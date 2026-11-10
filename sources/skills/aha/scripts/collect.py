#!/usr/bin/env python3
"""Collect user/assistant prose from one KST day without tool results."""

import argparse
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")


def _text(content, accepted):
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block.get("text", "").strip()
        for block in content
        if isinstance(block, dict) and block.get("type") in accepted
        and isinstance(block.get("text"), str) and block.get("text", "").strip()
    )


def _extract(row, source):
    if source == "codex":
        if row.get("type") != "response_item":
            return None
        payload = row.get("payload", {})
        if payload.get("type") != "message" or payload.get("role") not in {"user", "assistant"}:
            return None
        if payload.get("role") == "assistant" and payload.get("phase") not in {None, "final_answer"}:
            return None
        role = payload["role"]
        message = _text(payload.get("content"), {"input_text" if role == "user" else "output_text"})
    else:
        if row.get("type") not in {"user", "assistant"} or row.get("isMeta") or row.get("isSidechain"):
            return None
        payload = row.get("message", {})
        role = row["type"]
        message = _text(payload.get("content"), {"text"})
    if not message:
        return None
    return role, message[:1200]


def collect(day, codex_root, claude_root):
    target = date.fromisoformat(day)
    start = datetime.combine(target, time.min, KST).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    items = []
    for source, root in (("codex", Path(codex_root)), ("claude", Path(claude_root))):
        if not root.is_dir():
            continue
        for path in root.rglob("*.jsonl"):
            if path.stat().st_mtime < start.timestamp():
                continue
            with path.open(encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                        when = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                    except (ValueError, KeyError, TypeError):
                        continue
                    if not start <= when.astimezone(timezone.utc) < end:
                        continue
                    result = _extract(row, source)
                    if result:
                        role, message = result
                        items.append({"at": when.isoformat(), "source": source, "role": role, "text": message})
    return sorted(items, key=lambda item: item["at"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now(KST).date().isoformat())
    parser.add_argument("--codex-root", type=Path, default=Path.home() / ".codex/sessions")
    parser.add_argument("--claude-root", type=Path, default=Path.home() / ".claude/projects")
    args = parser.parse_args()
    print(json.dumps(collect(args.date, args.codex_root, args.claude_root), ensure_ascii=False))


if __name__ == "__main__":
    main()

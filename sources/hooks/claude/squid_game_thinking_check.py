#!/usr/bin/env python3
"""Companion Python for squid_game_thinking_check.sh.

Reads the Claude Code SubagentStop hook payload from stdin, extracts the
session_id of the squid-game-player subagent that just finished, and
verifies that the Anthropic proxy captured at least one thinking record
for it. Writes one summary line to
    ~/.claude/squid_game_verification.log
Exit code is always 0 — this hook is informational only.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LOG = Path.home() / ".claude" / "squid_game_verification.log"

SESSION_ID_RE = re.compile(
    r'"?session_id"?\s*[:=]\s*"?([0-9a-fA-F][0-9a-fA-F\-]{7,})'
)

# Default path matches interface/anthropic_proxy.py default.
_DEFAULT_PROXY_LOG = (
    Path.home()
    / "Documents"
    / "WorkSpace"
    / "Squid-Game"
    / "outputs"
    / "api_sessions"
    / "thinking_traces"
    / "api_calls.jsonl"
)
PROXY_LOG = Path(
    os.environ.get("SQUID_THINKING_LOG_DIR", str(_DEFAULT_PROXY_LOG.parent))
) / "api_calls.jsonl"

PROXY_HEALTH = os.environ.get(
    "SQUID_PROXY_HEALTH_URL", "http://127.0.0.1:8765/_proxy/health"
)
PROXY_SESSION_BASE = PROXY_HEALTH.replace("/_proxy/health", "/_proxy/session/")


def _log(line: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now(timezone.utc).isoformat()}] {line}\n")
    except Exception:
        pass


def _extract_session_id(payload: dict) -> str | None:
    # Hit anything that smells like the subagent's final message.
    candidates: list[str] = []
    for key in ("last_assistant_message", "message", "final_response"):
        v = payload.get(key)
        if isinstance(v, str):
            candidates.append(v)
    # Sometimes hooks nest under "hookSpecificOutput" or similar.
    for k, v in payload.items():
        if isinstance(v, str) and "session_id" in v:
            candidates.append(v)
        elif isinstance(v, dict):
            for sv in v.values():
                if isinstance(sv, str) and "session_id" in sv:
                    candidates.append(sv)
    for text in candidates:
        m = SESSION_ID_RE.search(text)
        if m:
            return m.group(1)
    return None


def _count_via_http(sid: str) -> int | None:
    try:
        with urllib.request.urlopen(
            PROXY_SESSION_BASE + sid, timeout=2
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return int(data.get("count") or 0)
    except Exception:
        return None


def _count_via_file(sid: str) -> int:
    if not PROXY_LOG.exists():
        return 0
    count = 0
    needle = f'"session_id": "{sid}"'
    # also tolerate non-pretty key order
    needle_alt = f'"session_id":"{sid}"'
    try:
        with PROXY_LOG.open("r", encoding="utf-8") as fh:
            for line in fh:
                if needle in line or needle_alt in line:
                    count += 1
    except Exception:
        return 0
    return count


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}

    event = payload.get("hook_event_name") or payload.get("event") or ""
    if event and event not in {"SubagentStop", "Stop"}:
        return 0

    sid = _extract_session_id(payload)
    if not sid:
        # Not a squid-game subagent (or message doesn't carry session_id) — skip quietly.
        return 0

    proxy_active = os.environ.get("SQUID_PROXY_ACTIVE") or os.environ.get(
        "ANTHROPIC_BASE_URL", ""
    ).startswith(("http://127.0.0.1", "http://localhost"))

    count = _count_via_http(sid)
    via = "http"
    if count is None:
        count = _count_via_file(sid)
        via = "file"

    if count > 0:
        _log(f"OK session={sid} thinking_records={count} via={via}")
    else:
        if proxy_active:
            _log(
                f"WARN session={sid} NO thinking captured by proxy "
                f"(log={PROXY_LOG}). Did the model run with extended thinking enabled?"
            )
        else:
            _log(
                f"SKIP session={sid} proxy not active (ANTHROPIC_BASE_URL not "
                f"pointing at local proxy) — thinking capture disabled for this session."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash
# SubagentStop hook — verifies that the Anthropic proxy captured thinking
# traces for any squid-game-player subagent that just finished.
#
# Non-blocking. Never returns exit code 2. On any error the hook silently
# exits 0 so it cannot interfere with Claude Code.
#
# Input (stdin): Claude Code hook JSON with fields including
# `hook_event_name` and `last_assistant_message`.
#
# Output: one line appended to
#   $HOME/.claude/squid_game_verification.log
# with either OK or WARN and the session_id extracted from the subagent's
# final assistant message.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/env python3 "$SCRIPT_DIR/squid_game_thinking_check.py"

#!/usr/bin/env bash
# macOS notification for Claude Code — fires only in Cursor/VS Code integrated
# terminal (iTerm/kitty/ghostty already get native notifications).
# Usage: cursor-notify.sh <event>   where <event> = stop | notification
#
# Title shows "Claude Code · <dir>" plus the last 4 chars of the session id,
# so finished sessions are distinguishable even across windows on the same dir.

[ "$TERM_PROGRAM" = "vscode" ] || exit 0

event="${1:-stop}"
input="$(cat 2>/dev/null)"

cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)"
[ -n "$cwd" ] || cwd="$PWD"
dir="$(basename "$cwd")"

sid="$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)"
suffix=""
[ -n "$sid" ] && suffix=" (${sid: -4})"
title="Claude Code · ${dir}${suffix}"

if [ "$event" = "notification" ]; then
  msg="$(printf '%s' "$input" | jq -r '.message // "입력을 기다리고 있어요"' 2>/dev/null)"
else
  msg="작업이 끝났어요 — 입력 대기 중"
fi

# Delivery has two tiers.
#
# Tier 1 - terminal-notifier from ~/Applications. That copy is re-signed so its
# Info.plist is bound, which UNUserNotificationCenter requires; the Homebrew copy
# is only linker-signed and cannot register at all. -sender borrows the host
# editor's bundle identity (exported as __CFBundleIdentifier), so the alert shows
# VS Code's or Cursor's icon and clicking it focuses that window.
#
# Tier 2 - osascript, which posts under Script Editor's identity. Used whenever
# tier 1 is missing or exits non-zero (most likely: notification permission for
# terminal-notifier is still off in System Settings > Notifications).
sender="${__CFBundleIdentifier:-com.microsoft.VSCode}"
notifier="$HOME/Applications/terminal-notifier.app/Contents/MacOS/terminal-notifier"
[ -x "$notifier" ] || notifier="$(command -v terminal-notifier 2>/dev/null)"

delivered=0
if [ -n "$notifier" ] && [ -x "$notifier" ]; then
  "$notifier" \
    -title "$title" \
    -message "$msg" \
    -sender "$sender" \
    -activate "$sender" \
    -group "claude-code-${sid:-default}" \
    -sound Glass >/dev/null 2>&1 && delivered=1
fi

if [ "$delivered" -eq 0 ]; then
  osascript -e 'on run argv' \
    -e 'display notification (item 1 of argv) with title (item 2 of argv) sound name "Glass"' \
    -e 'end run' "$msg" "$title" >/dev/null 2>&1
fi

exit 0

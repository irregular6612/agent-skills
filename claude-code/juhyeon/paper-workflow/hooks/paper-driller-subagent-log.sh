#!/usr/bin/env bash
# paper-driller SubagentStop hook
# Logs each completed paper-driller subagent's identity as JSONL for QC observability.
# Family: paper-spine, paper-section-* (driller), paper-meta, paper-evidence,
# paper-comparison, paper-digest-composer.
#
# Hook input (stdin): Claude Code SubagentStop JSON payload. Field names can vary by
# version, so subagent_type is extracted best-effort with POSIX-safe,
# whitespace-tolerant regex (works on both BSD/macOS and GNU grep).
# Output: silent. Always exit 0 so it never blocks the main session.

set -o pipefail

LOG_DIR="${HOME}/.claude/logs"
LOG_FILE="${LOG_DIR}/paper-driller-qc.jsonl"
mkdir -p "${LOG_DIR}"

PAYLOAD="$(cat 2>/dev/null || true)"
[[ -z "${PAYLOAD}" ]] && exit 0
# Drop oversized payloads so the hook self-terminates cleanly instead of relying
# on the harness timeout (the grep passes below would otherwise scan it repeatedly).
[[ "${#PAYLOAD}" -gt 524288 ]] && exit 0

# POSIX-safe, whitespace-tolerant string-value extractor for a JSON key.
# Value is constrained to [^"]+ so the result cannot contain quotes/newlines (JSON-safe, no injection).
extract() { # $1 = key name
  printf '%s' "${PAYLOAD}" \
    | grep -oE "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]+\"" \
    | head -1 \
    | sed -E 's/.*:[[:space:]]*"([^"]+)"$/\1/'
}

# Strip control chars and backslashes so a crafted value cannot emit malformed JSONL.
sanitize() { printf '%s' "$1" | LC_ALL=C tr -d '\000-\037\\'; }

SUBAGENT_TYPE="$(extract subagent_type)"
[[ -z "${SUBAGENT_TYPE}" ]] && SUBAGENT_TYPE="$(extract subagentType)"
[[ -z "${SUBAGENT_TYPE}" ]] && SUBAGENT_TYPE="$(extract agent_type)"

# Only log the paper-driller family.
case "${SUBAGENT_TYPE}" in
  paper-spine|paper-section-*|paper-meta|paper-evidence|paper-comparison|paper-digest-composer)
    ;;
  *)
    exit 0
    ;;
esac

SUBAGENT_TYPE="$(sanitize "${SUBAGENT_TYPE}")"

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

printf '{"ts":"%s","subagent_type":"%s","payload_bytes":%d}\n' \
  "${TS}" "${SUBAGENT_TYPE}" "${#PAYLOAD}" >> "${LOG_FILE}"

exit 0

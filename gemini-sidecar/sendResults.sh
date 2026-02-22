#!/bin/bash
# gemini-sidecar/sendResults.sh
# Agent-to-Brain callback script. Installed as both sendResults and sendMessage (symlink).
#
# sendResults -- pushes a deliverable (stored as the agent's result, last-write-wins)
# sendMessage -- pushes a progress note (shown in UI, does NOT overwrite deliverable)
#
# Usage (PREFER file or pipe for multiline content):
#   sendResults ./path/to/report.md          BEST: Send file contents as result
#   echo "text" | sendResults                GOOD: Send stdin as result
#   sendResults -m "short single-line text"  OK for short messages only
#   sendMessage -m "status update"           Send inline string as progress note
#   sendMessage ./path/to/notes.md           Send file contents as progress note
#
# WARNING: -m with multiline text breaks in bash (newlines split the command).
# For reports, ALWAYS write to a file first, then: sendResults ./results/findings.md

set -euo pipefail

CALLBACK_URL="http://localhost:${PORT:-9090}/callback"

# Determine type from invocation name: sendMessage -> message, sendResults -> result
INVOKED_AS="$(basename "$0")"
if [ "$INVOKED_AS" = "sendMessage" ]; then
  TYPE="message"
else
  TYPE="result"
fi

# Read content from: -m flag, file argument, or stdin
CONTENT=""
if [ "${1:-}" = "-m" ] && [ -n "${2:-}" ]; then
  CONTENT="$2"
elif [ -n "${1:-}" ] && [ -f "$1" ]; then
  CONTENT="$(cat "$1")"
elif [ ! -t 0 ]; then
  CONTENT="$(cat -)"
else
  echo "Usage: $INVOKED_AS -m \"text\" | $INVOKED_AS <file> | echo text | $INVOKED_AS" >&2
  exit 1
fi

if [ -z "$CONTENT" ]; then
  echo "Error: empty content" >&2
  exit 1
fi

# POST to sidecar callback endpoint
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$CALLBACK_URL" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg type "$TYPE" --arg content "$CONTENT" '{type: $type, content: $content}')")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ne 200 ]; then
  echo "Error: callback returned HTTP $HTTP_CODE: $BODY" >&2
  exit 1
fi

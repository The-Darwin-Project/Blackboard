#!/bin/bash
# gemini-sidecar/huddleSendMessage.sh
# Agent-to-Brain huddle. Sends a message and BLOCKS until the Brain replies.
#
# This is agent-to-Brain communication (dev/qe -> Brain).
# For non-blocking status updates, use sendMessage or sendResults.
#
# Usage (PREFER file or pipe for multiline content):
#   huddleSendMessage ./report.md                  BEST: Send file contents
#   echo "tests done" | huddleSendMessage           GOOD: Pipe stdin
#   huddleSendMessage -m "short single-line msg"    OK for short messages only
#
# WARNING: -m with multiline text breaks in bash. Write to file first.

set -euo pipefail

CALLBACK_URL="http://localhost:${PORT:-9090}/callback"

# Read content from: -m flag, file argument, bare string, or stdin
CONTENT=""
if [ "${1:-}" = "-m" ] && [ -n "${2:-}" ]; then
  CONTENT="$2"
elif [ -n "${1:-}" ] && [ -f "$1" ]; then
  CONTENT="$(cat "$1")"
elif [ -n "${1:-}" ]; then
  CONTENT="$1"
elif [ ! -t 0 ]; then
  CONTENT="$(cat -)"
else
  echo "Usage: huddleSendMessage -m \"text\" | huddleSendMessage <file> | echo text | huddleSendMessage" >&2
  exit 1
fi

if [ -z "$CONTENT" ]; then
  echo "Error: empty content" >&2
  exit 1
fi

# POST to sidecar callback. The sidecar HOLDS this request open until the Brain replies.
# Timeout: 600s (10 min) -- Brain needs time for LLM thinking + coordination.
# Background heartbeat keeps the CLI from killing us for "no output" (Gemini CLI 5min inactivity timeout).
echo "Waiting for Brain reply..."
(while true; do sleep 30; echo "Still waiting for Brain..."; done) &
HEARTBEAT_PID=$!
trap "kill $HEARTBEAT_PID 2>/dev/null" EXIT

RESPONSE=$(curl -s -m 600 -w "\n%{http_code}" -X POST "$CALLBACK_URL" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg type "huddle_message" --arg content "$CONTENT" '{type: $type, content: $content}')")

kill $HEARTBEAT_PID 2>/dev/null
trap - EXIT

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ne 200 ]; then
  echo "Error: Brain reply failed (HTTP $HTTP_CODE): $BODY" >&2
  exit 1
fi

# Print the Brain's reply
echo "$BODY" | jq -r '.reply // .content // .'

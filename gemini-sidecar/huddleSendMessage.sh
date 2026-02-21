#!/bin/bash
# gemini-sidecar/huddleSendMessage.sh
# Agent-to-Manager communication. Sends a message and BLOCKS until the Manager replies.
#
# This is team-internal communication (dev/qe -> Manager).
# For Brain/system communication, use sendMessage or sendResults.
#
# Usage:
#   huddleSendMessage -m "step 1 is unclear, need clarification from the architect"
#   huddleSendMessage ./question.md
#   echo "should I fix tests first?" | huddleSendMessage

set -euo pipefail

CALLBACK_URL="http://localhost:${PORT:-9090}/callback"

# Read content from: -m flag, file argument, or stdin
CONTENT=""
if [ "${1:-}" = "-m" ] && [ -n "${2:-}" ]; then
  CONTENT="$2"
elif [ -n "${1:-}" ] && [ -f "$1" ]; then
  CONTENT="$(cat "$1")"
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

# POST to sidecar callback. The sidecar HOLDS this request open until the Manager replies.
# Timeout: 50s (sidecar timeout is 45s -- 5s buffer for network).
RESPONSE=$(curl -s -m 50 -w "\n%{http_code}" -X POST "$CALLBACK_URL" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg type "huddle_message" --arg content "$CONTENT" '{type: $type, content: $content}')")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ne 200 ]; then
  echo "Error: Manager reply failed (HTTP $HTTP_CODE): $BODY" >&2
  exit 1
fi

# Print the Manager's reply (the LLM's response)
echo "$BODY" | jq -r '.reply // .content // .'

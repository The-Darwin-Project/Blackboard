#!/bin/bash
# gemini-sidecar/hooks/require-results.sh
# @ai-rules:
# 1. [Pattern]: Antigravity Stop hook -- mirrors Claude's Stop hook behavior.
# 2. [Purpose]: Blocks agent exit if team_send_results was never called (no results delivered).
# 3. [Constraint]: Exit 0 always with JSON. Uses "continue" decision to instruct model to deliver results.
# 4. [Gotcha]: message mode tasks are exempt (they use team_send_message, not team_send_results).
# 5. [Constraint]: "continue" is BOUNDED (MAX_CONTINUES per task, counter in /tmp keyed by sidecar port).
#    An agent that cannot deliver results (e.g. tool denied, sidecar unreachable) must be able to exit
#    rather than loop forever. Counter resets on any "stop" decision and expires after COUNTER_TTL_MIN.

MAX_CONTINUES=3
COUNTER_TTL_MIN=30

INPUT=$(cat 2>/dev/null)
RESULT=$(curl -sf --connect-timeout 0.5 --max-time 1 "http://localhost:${SIDECAR_PORT:-9090}/hook-status" 2>/dev/null)
HAS_RESULTS=$(echo "$RESULT" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.hasResults?'yes':'no')}catch{process.stdout.write('no')}" 2>/dev/null)
TASK_MODE=$(echo "$RESULT" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.taskMode||'')}catch{process.stdout.write('')}" 2>/dev/null)
TASK_ID=$(echo "$RESULT" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write((j.taskId||'').replace(/[^a-zA-Z0-9_-]/g,''))}catch{process.stdout.write('')}" 2>/dev/null)

COUNTER_DIR="/tmp/.darwin-hooks-${UID:-1001}"
mkdir -p -m 0700 "$COUNTER_DIR" 2>/dev/null
COUNTER_FILE="${COUNTER_DIR}/require-results-${SIDECAR_PORT:-9090}-${TASK_ID:-default}.count"

# Defend against symlink attacks: remove if it is a symlink
[ -L "$COUNTER_FILE" ] && rm -f "$COUNTER_FILE" 2>/dev/null

# Drop stale counters older than TTL
[ -f "$COUNTER_FILE" ] && [ -n "$(find "$COUNTER_FILE" -mmin +"$COUNTER_TTL_MIN" 2>/dev/null)" ] && rm -f "$COUNTER_FILE" 2>/dev/null

allow_stop() {
    rm -f "$COUNTER_FILE" 2>/dev/null
    echo '{"decision": "stop"}'
    exit 0
}

# Message mode is exempt -- those tasks use team_send_message
if [ "$TASK_MODE" = "message" ]; then
    allow_stop
fi

if [ "$HAS_RESULTS" = "yes" ]; then
    allow_stop
fi

# Bounded continue: after MAX_CONTINUES nudges, let the agent exit
COUNT=$(cat "$COUNTER_FILE" 2>/dev/null)
case "$COUNT" in ''|*[!0-9]*) COUNT=0 ;; esac
if [ "$COUNT" -ge "$MAX_CONTINUES" ]; then
    allow_stop
fi

TMP_CNT=$(mktemp "${COUNTER_DIR}/cnt.XXXXXX" 2>/dev/null)
if [ -n "$TMP_CNT" ]; then
    echo $((COUNT + 1)) > "$TMP_CNT" 2>/dev/null
    mv -f "$TMP_CNT" "$COUNTER_FILE" 2>/dev/null
else
    echo $((COUNT + 1)) > "$COUNTER_FILE" 2>/dev/null
fi

# No results delivered -- continue (Antigravity Stop hook)
node -e "
  const msg = 'You have NOT called team_send_results yet. You MUST deliver your findings before exiting. Call team_send_results now with the specific data requested in your task instruction.';
  process.stdout.write(JSON.stringify({ decision: 'continue', reason: msg }));
"
exit 0

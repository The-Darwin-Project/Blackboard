#!/bin/bash
# gemini-sidecar/hooks/require-results.sh
# @ai-rules:
# 1. [Pattern]: Gemini AfterAgent hook -- mirrors Claude's Stop hook behavior.
# 2. [Purpose]: Blocks agent exit if team_send_results was never called (no results delivered).
# 3. [Constraint]: Exit 0 always with JSON. Uses "retry" decision to force model to deliver results.
# 4. [Gotcha]: message mode tasks are exempt (they use team_send_message, not team_send_results).

RESULT=$(curl -sf "http://localhost:${SIDECAR_PORT:-9090}/hook-status" 2>/dev/null)
HAS_RESULTS=$(echo "$RESULT" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.hasResults?'yes':'no')}catch{process.stdout.write('no')}" 2>/dev/null)
TASK_MODE=$(echo "$RESULT" | node -e "const d=require('fs').readFileSync(0,'utf8');try{const j=JSON.parse(d);process.stdout.write(j.taskMode||'')}catch{process.stdout.write('')}" 2>/dev/null)

# Message mode is exempt -- those tasks use team_send_message
if [ "$TASK_MODE" = "message" ]; then
    echo '{}'
    exit 0
fi

if [ "$HAS_RESULTS" = "yes" ]; then
    echo '{}'
    exit 0
fi

# No results delivered -- retry
node -e "
  process.stdout.write(JSON.stringify({
    decision: 'retry',
    systemMessage: 'You have NOT called team_send_results yet. You MUST deliver your findings before exiting. Call team_send_results now with the specific data requested in your task instruction.'
  }));
"
exit 0

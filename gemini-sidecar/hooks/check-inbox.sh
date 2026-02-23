#!/bin/bash
# gemini-sidecar/hooks/check-inbox.sh
# @ai-rules:
# 1. [Pattern]: CLI hook script -- checks sidecar inbox, injects messages into LLM context.
# 2. [Pattern]: Gemini AfterTool uses systemMessage. Claude PreToolUse uses additionalContext inside hookSpecificOutput.
# 3. [Constraint]: Exit 0 always -- hook failure must not block the agent's tool execution.
# 4. [Constraint]: Empty inbox = silent exit (no output). Only inject when messages exist.
# 5. [Gotcha]: $MSGS contains raw JSON with double quotes -- must use node for proper escaping.

MSGS=$(curl -sf "http://localhost:${SIDECAR_PORT:-9090}/messages" 2>/dev/null)
[ -z "$MSGS" ] || [ "$MSGS" = "[]" ] && exit 0

if [ "${AGENT_CLI}" = "claude" ]; then
    node -e "
      const m = process.argv[1];
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'allow',
          additionalContext: '[TEAM MESSAGES] ' + m
        }
      }));
    " "$MSGS"
else
    node -e "
      const m = process.argv[1];
      process.stdout.write(JSON.stringify({
        decision: 'allow',
        systemMessage: '[TEAM MESSAGES] ' + m
      }));
    " "$MSGS"
fi
exit 0

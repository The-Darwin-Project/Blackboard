---
description: "Acknowledge intermediate turns during active agent execution. Reply to agent huddles. Signal wait state."
tags: [intermediate, temporal-context, huddle]
---
# Intermediate Awareness

An agent is currently working on this event. You are seeing a progress update,
environment signal, or an agent huddle requesting guidance.

## Tool Selection

| Situation | Tool | NOT |
|-----------|------|-----|
| Agent is working, you are waiting for its result | `wait_for_agent` | Do NOT use `wait_for_user` -- the user is not involved |
| Agent huddles a question mid-task | `reply_to_agent` | -- |
| You need to tell the user something while agent works | `wait_for_user` | Only if user input is actually needed |
| You need to send an unsolicited message to an agent | `message_agent` | -- |
| Agent is working normally, nothing to do | No tool call | Just observe with a brief note |

CRITICAL: `wait_for_user` pauses the event until the user responds. Do NOT call it when you are waiting for an AGENT. Use `wait_for_agent` instead.

## When an agent is working (most common)

Produce a brief 1-2 sentence observation. If this is the first intermediate turn for this agent dispatch, call `wait_for_agent` to signal the wait state. Otherwise, just observe.

Examples:

- First progress: call wait_for_agent("Waiting for Developer to complete pagination implementation")
- Subsequent progress: "Developer pushing to branch. Agent in progress." (no tool call)
- "QE running Playwright tests. Awaiting results." (no tool call)

## When an agent huddles (reply_to_agent available)

An agent is asking for your guidance via team_huddle. You MUST reply:

1. Read the huddle content carefully.
2. Call reply_to_agent(agent_id, message) with actionable guidance.
3. Keep replies concise -- the agent is waiting and blocked until you reply.

If the agent reports completion, acknowledge and let them finish.
If the agent reports a problem, provide specific next steps.
If the agent asks a question, answer it directly.

Examples:

- Agent huddles "Implementation done, pushed to branch feature/fix-123"
  -> reply_to_agent(agent_id, "Acknowledged. Continue with PR creation.")
- Agent huddles "2 test failures on dark theme component"
  -> reply_to_agent(agent_id, "Noted. Focus on the dark theme gap, fix and re-run tests.")

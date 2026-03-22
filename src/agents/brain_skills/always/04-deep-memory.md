---
description: "Consult deep memory before routing to agents"
tags: [memory, triage, history]
---
# Deep Memory

Before routing to an agent, consult past events if the situation involves:

1. Past events, history, or "what happened" questions
2. Recurring issues or symptoms you have seen before
3. Service status, health, or operational queries

Skip this only for urgent anomalies (chaotic domain) or user-approved plans awaiting execution.

Deep memory surfaces past events with similar symptoms, their root causes, and what fixed them.

- If a past event matches closely, use its root cause and fix to skip investigation and act directly.
- If the data answers the user's question directly, respond to the user without dispatching an agent.
- If no relevant history, proceed normally with agent routing.

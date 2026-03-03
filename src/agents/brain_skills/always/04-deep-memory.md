---
description: "Consult deep memory before routing to agents"
tags: [memory, triage, history]
---
# Deep Memory

MANDATORY: Before calling select_agent, you MUST call consult_deep_memory or lookup_journal if the event involves:
1. Past events, history, or "what happened" questions
2. Recurring issues or symptoms you have seen before
3. Service status, health, or operational queries

Skip this ONLY for: urgent anomalies (chaotic domain) or user-approved plans awaiting execution.

Deep memory returns past events with similar symptoms, their root causes, and what fixed them.
- If a past event matches closely (score > 0.6), use its root cause and fix to skip investigation and act directly.
- If the data answers the user's question directly, respond via wait_for_user -- do NOT dispatch an agent.
- If no match or low scores, proceed normally with agent routing.

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
Use this context to guide your classification and agent instructions, not to replace investigation.

- For **user/chat events**: If the data answers the user's question directly, respond without dispatching an agent.
- For **automated events** (headhunter, aligner, timekeeper): Memory informs but does NOT replace investigation.
  Always dispatch an agent to verify the current state. Past root causes may not match the current failure.
  Include relevant memory context in the agent's task_instruction so it can validate or correct the hypothesis.
- If **Lessons Learned** appear in the results, treat them as classification guidance (how to prioritize
  failure types, what to look for) rather than specific incident history.
- If no relevant history, proceed normally with agent routing.

---
description: "Consult deep memory before routing to agents"
tags: [memory, triage, history]
---
# Deep Memory

## Mandatory Consultation (TRIAGE phase)

For **automated events** (headhunter, aligner, timekeeper): deep memory
consultation is MANDATORY during triage -- not conditional. Automated events
are repetitive by nature; the same service, pipeline, or bot will produce
similar events across days and weeks. Skipping memory means the Ts calibration
operates blind and past root causes are rediscovered from scratch.

For **user events** (chat, slack): consult past events if the situation involves:

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

## Reference Facts

Deep memory also surfaces **Reference Facts** -- static infrastructure knowledge such as namespace mappings,
cluster endpoints, team ownership conventions, and historical deployment decisions.

- Reference Facts have a `confidence` score (0.0-1.0) and optional `valid_until` expiry.
- If a fact is marked **STALE**, verify it via `lookup_service` or agent investigation before acting on it.
- For **user/chat events**: reference facts can directly answer factual questions (e.g., "who owns service X?",
  "what namespace does Y deploy to?") without dispatching agents.
- Reference facts complement K8s Observer: Observer has **live state** (CPU, memory, replicas),
  knowledge has **conventions and historical context** (ownership, naming rules, architectural decisions).
- Do NOT treat reference facts as authoritative for live state -- always cross-reference with Observer for
  current metrics and pod status.

Fix proposal authorization (Propose and Prompt) is available during dispatch phase via dispatch/deep-memory-fixes.md.

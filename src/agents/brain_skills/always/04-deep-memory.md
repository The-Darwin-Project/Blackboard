---
description: "Consult deep memory before routing to agents"
tags: [memory, triage, history]
tools: [consult_deep_memory, lookup_journal]
---
# Deep Memory

## Mandatory Consultation (TRIAGE phase)

For **automated events** (headhunter, aligner, timekeeper): deep memory
consultation is MANDATORY during triage -- not conditional. Automated events
are repetitive by nature; the same service, pipeline, or bot will produce
similar events across days and weeks. Skipping memory means the Ts calibration
operates blind and past root causes are rediscovered from scratch.

For **user events** (chat, slack): consult when the situation involves past
events, recurring symptoms, or operational queries. Skip only for urgent
anomalies (chaotic domain) or user-approved plans awaiting execution.

Deep memory surfaces past events with similar symptoms, their root causes,
and what fixed them. Use this context to guide classification and agent
instructions -- not to replace investigation.

- **User events**: if the data answers the user's question directly, respond
  without dispatching an agent.
- **Automated events**: memory informs but does NOT replace investigation.
  Past root causes may not match the current failure. Include relevant memory
  context in the agent's task_instruction so it can validate or correct the
  hypothesis.
- **Lessons Learned**: treat as classification guidance (how to prioritize
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

## Temporal and Structured Filters

Deep memory supports optional structured filters alongside semantic search.
These narrow results by recency, event duration, or service scope.

Use filters when the question has a clear temporal or service dimension.
Semantic search alone handles most queries — filters add precision when
the user asks about specific time periods, long-running events, or
particular services. When uncertain, prefer fewer filters. If filtered
results return empty, the response will indicate which filters were applied
so you can adjust.

Filters narrow the **Past Events** section only. Lessons Learned and
Reference Facts are never filtered by time or service — they represent
timeless patterns and static infrastructure knowledge.

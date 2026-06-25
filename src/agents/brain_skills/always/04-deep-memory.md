---
description: "Consult deep memory before routing to agents"
tags: [memory, triage, history]
requires:
  - dispatch/deep-memory-fixes.md
tools: [consult_deep_memory, lookup_journal]
---
# Deep Memory

## Mandatory Consultation (TRIAGE phase)

Automated systems produce repetitive events — the same service, pipeline, or
bot triggers similar failures across days and weeks. Without memory
consultation, each occurrence starts from scratch: Ts calibration has no
baseline, known root causes are rediscovered via agent dispatch, and patterns
visible across events remain invisible within one.

For **automated events** (headhunter, aligner, timekeeper): deep memory
consultation is MANDATORY during triage -- not conditional.

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

Reference Facts are static infrastructure knowledge — they answer "who owns
this?", "where does this deploy?", "what is the convention?" These are
questions that don't change between events and shouldn't require agent
investigation to answer.

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

Semantic search alone handles most queries well. Structured filters add
precision when the question has an explicit temporal dimension ("what happened
last week?") or service scope ("failures in service X") — without filters,
semantically similar but irrelevant results from other time periods or services
dilute the response.

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

---
description: "Cynefin sense-making framework for domain classification"
tags: [cynefin, classification, triage]
---
# Cynefin Sense-Making Framework

Before deciding how to respond to an event, classify it into a domain:

## CLEAR (Known knowns -- Best Practice)
- Pattern: Known issue with a proven fix (e.g., high CPU -> scale up)
- Constraints: Tightly constrained, no creativity needed
- Flow: Sense -> Categorize -> Respond
- Action: Skip Architect. Send sysAdmin directly with the established fix.
- Example: "CPU > 80% on a service with 1 replica" -> scale to 2 via GitOps

## COMPLICATED (Known unknowns -- Good Practices)
- Pattern: Issue needs expert analysis (e.g., intermittent errors, performance degradation)
- Constraints: Governing constraints, multiple valid approaches
- Flow: Sense -> Analyze -> Respond
- Action: Send sysAdmin to investigate, then Architect to analyze options, then decide.
- Example: "Error rate spike from unknown cause" -> investigate -> plan -> execute

## COMPLEX (Unknown unknowns -- Emergent Practice)
- Pattern: Novel situation, no clear cause-effect (e.g., cascading failures, new feature request)
- Constraints: Enabling constraints, high freedom
- Flow: Probe -> Sense -> Respond
- Action: Run a small safe-to-fail probe first. Observe result. Adapt.
- Example: "User asks to add a feature" -> Architect reviews codebase (probe) -> plan based on findings

## CHAOTIC (Crisis -- Novel Practice)
- Pattern: System down, cascading failures, critical security breach
- Constraints: No constraints, act first
- Flow: Act -> Sense -> Respond
- Action: Immediate stabilization (rollback, scale up, disable feature flag). Investigate AFTER stable.
- Example: "All pods CrashLoopBackOff" -> rollback last deployment immediately -> then investigate

## DISORDER (Default)
- You don't know which domain. Ask sysAdmin to investigate first to gather data.

## Classification Protocol

classify_event is MANDATORY before any agent dispatch. The system enforces this structurally --
select_agent is not available until you classify. Base your classification on:
1. The event evidence (what happened)
2. Deep memory results (how similar events were classified historically)
3. Your own analysis -- NOT the source's suggestion

The source's domain label is a hint, not a classification. You must assess independently.

## Reclassification

classify_event is always available. You can and should reclassify when evidence changes:
- Agent reports unexpected complexity: reclassify upward (CLEAR -> COMPLICATED or COMPLEX)
- Investigation reveals unknown root cause: reclassify to COMPLEX
- System enters crisis mid-event: reclassify to CHAOTIC
- Probe results clarify the situation: reclassify downward (COMPLEX -> COMPLICATED)
- Stabilization confirmed: reclassify from CHAOTIC to COMPLICATED for root cause analysis

Each reclassification is recorded in the conversation as a brain.triage turn.
The pipeline adapts immediately: tool availability changes on the next turn.

## Domain-Specific Behavior

After classification, the system enforces domain-appropriate constraints:
- CLEAR: Full tool set. Act directly on known patterns.
- COMPLICATED: Full tool set. Analyze, then act.
- COMPLEX: close_event is blocked until at least 2 agent rounds complete (probe-sense-respond).
- CHAOTIC: Only select_agent + notify available. No defer, no wait. Stabilize first, then reclassify.

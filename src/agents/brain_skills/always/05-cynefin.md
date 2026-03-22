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

## DISORDER (Initial State)

- DISORDER means no one has assessed the situation yet. You must classify before acting.
- Events from assessed sources arrive with a suggested domain -- treat it as a hypothesis, not a fact.
- Base your classification on the evidence, deep memory results, and your own analysis.

## Reclassification

Reclassify when evidence changes during an event:

- Agent reports unexpected complexity: reclassify upward (CLEAR -> COMPLICATED or COMPLEX)
- Investigation reveals unknown root cause: reclassify to COMPLEX
- System enters crisis mid-event: reclassify to CHAOTIC
- Probe results clarify the situation: reclassify downward (COMPLEX -> COMPLICATED)
- Stabilization confirmed: reclassify from CHAOTIC to COMPLICATED for root cause analysis

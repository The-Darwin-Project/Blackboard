---
description: "Cynefin sense-making framework for domain classification"
tags: [cynefin, classification, triage]
---
# Cynefin Sense-Making Framework

## Cross-Issue Correlation (before classifying)

When multiple issues surface from the same event trace, system, or timeframe, apply a correlation check BEFORE classifying each independently:

1. **Shared PV Check**: Do these symptoms observe the same process variable? If two issues both measure the same system output, they may be the same error from different observation points.
2. **Root Cause Collapse Test**: If I fix one issue, does the other disappear? If yes, classify the shared root cause, not the individual symptoms.
3. **Controller Action Smell Test**: Am I proposing separate controller actions for symptoms that share a single error signal? One mechanism that closes the shared error is the target.

Before deciding how to respond to an event, classify it into a domain:

## CLEAR (Known knowns -- Best Practice)

- Pattern: Known issue with a proven fix (e.g., high CPU -> scale up)
- Constraints: Tightly constrained, no creativity needed
- Flow: Sense -> Categorize -> Respond
- Action: Enter the CLEAR domain loop (see domain/clear.md for the dual-rhombus strategy).

## COMPLICATED (Known unknowns -- Good Practices)

- Pattern: Issue needs expert analysis (e.g., intermittent errors, performance degradation)
- Constraints: Governing constraints, multiple valid approaches
- Flow: Sense -> Analyze -> Respond

## COMPLEX (Unknown unknowns -- Emergent Practice)

- Pattern: Novel situation, no clear cause-effect (e.g., cascading failures, new feature request)
- Constraints: Enabling constraints, high freedom
- Flow: Probe -> Sense -> Respond

## CHAOTIC (Crisis -- Novel Practice)

- Pattern: System down, cascading failures, critical security breach
- Constraints: No constraints, act first
- Flow: Act -> Sense -> Respond

## DISORDER (Initial State)

- DISORDER means no one has assessed the situation yet. You must classify before acting.
- Events from assessed sources arrive with a suggested domain -- treat it as a hypothesis, not a fact.
- Base your classification on the evidence, deep memory results, and your own analysis.

## Reclassification

Reclassification is available at every decision node in the domain control loops.
Use it when evidence or understanding contradicts the current domain. The default
is to continue the current strategy — reclassification is the exception, not the rule.

Reclassification swaps the active domain control loop. The domain skill unloads
and the new domain's strategy loads on the next turn.

<bridge ref="domain/{event.domain}" trigger="classify_event">
After classification, the domain-specific control loop loads and guides your
strategy. Each domain has its own decision nodes with dual rhombuses
(domain + phase) at every decision point. See 03-control-theory.md for the
outer loop and navigation model.
</bridge>

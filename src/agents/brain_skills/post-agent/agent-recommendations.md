---
description: "Never drop agent recommendations. Evaluate against user intent."
requires:
  - source/{event.source}.md
  - always/04-deep-memory.md
tags: [agent-results, recommendations, memory]
---
# Agent Recommendations

## Capture Numeric Findings

Numbers are the trajectory data that grounds future decisions. Without recorded measurements, your escalation, close, or re-dispatch decision is based on impressions rather than data — and Deep Memory has no concrete signal for future events encountering the same pattern.

When an agent's report contains quantifiable data (error counts, durations,
versions, replica counts, queue depths), call record_observation for each
measurable signal before deciding the next action. These numbers become
the trajectory that grounds your escalation, close, or re-dispatch decision.

## Reassess Domain After Agent Results

The Cynefin domain classification is a snapshot from triage time. Agent investigation may reveal that the situation is simpler or more complex than initially classified — a domain mismatch means you're applying the wrong practice type.

After each agent completes, consider whether the domain classification still holds:

- **Downgrade**: If the agent's findings simplify the situation (e.g., root cause is now known, or the fix already exists), reclassify if needed.
- **Upgrade**: If the user added new requests during execution, the agent reported unexpected complexity, or the scope grew beyond the initial classification. Call `classify_event` before dispatching the next agent.

## Cross-Reference History First

Institutional memory prevents repeating failed approaches and validates promising ones. Without this check, you may apply a fix the system already tried and rejected, or miss a pattern that has been successfully resolved multiple times before with the same approach.

Before acting on any agent recommendation, consult deep memory with the agent's key findings (service name, symptom, proposed fix). This lets you:

1. Detect if the same fix was tried before and failed -- escalate to user instead of repeating.
2. Spot recurring patterns -- if this is the 3rd time the same symptom appears, flag it.
3. Validate the fix -- if history shows a similar fix succeeded, proceed with higher confidence.
4. Correct timing estimates -- if an agent's recommended defer duration is shorter than what operational history shows, use the historical duration.

When history contradicts the agent's recommendation, prefer the historical data and note the override.

Skip this only when the agent's report is a simple acknowledgment with no actionable recommendation.

When SecurityAnalyst reports findings with auto-fixable CVEs, dispatch Developer to implement the recommended version bumps. When SecurityAnalyst reports only human-review items (major bumps, no-fix-available), escalate to the user with the full findings table.

## Evaluate Recommendations

An agent recommendation is a data signal that must produce a response — act, observe, or ask. Silently dropping a recommendation breaks the feedback loop: the agent invested a full dispatch cycle producing findings that vanish without affecting the event's trajectory.

- When an agent's response includes a recommendation or unresolved issue, you MUST take one of three paths:
  1. **Act**: dispatch the next agent step immediately, OR
  2. **Observe**: schedule observation via defer with an evidence-backed sampling interval (Ts), OR
  3. **Ask**: summarize findings and ask the user or escalate.
- NEVER silently drop an agent's recommendation.
- When an agent recommends "re-check in N minutes": defer for the recommended duration, then route back to the same agent to actually re-check. Do not defer again without dispatching -- deferring on stale data is a no-op loop.
- When an agent result is a terminal response (the dispatch is complete), do NOT defer waiting for sub-tasks the agent mentioned. Route to the next action or check with the user.
- Agent progress messages during an active dispatch are informational status updates, not recommendations. Only the final agent result contains actionable recommendations.

## When an Action Fails and Alternatives Exist

When an agent reports that an action did not produce the expected result and suggests alternatives, those alternatives are potential next steps — not just information for humans. Before escalating, consider whether the alternatives are within Darwin's capability.

If the agent's report mentions a concept, command, or mechanism that is unfamiliar, search for it. The model has access to web search — documentation for CI commands, API patterns, and status pages is available. An unfamiliar alternative is a knowledge gap, not a dead end.

## Remediation Plans from Agents

When an agent produces a plan turn (structured steps in frontmatter), treat it as
a remediation proposal -- not a pre-approved execution plan. The plan-activation skill
handles step dispatch. Before escalating a failure to incident creation, verify
plan steps have been attempted or triaged.
- When executing an Architect plan and the agent reports back:
  1. Check if the report includes updated step statuses.
  2. If all steps are completed, proceed to verification/close.
  3. If a step failed, decide: retry, skip, or escalate to user.
  4. If the agent's recommendation conflicts with the plan, prefer the agent's recommendation -- they have fresher context.

## Cross-Event Fix Proposals

When deep memory surfaces a validated fix for the current error signature, the
proposal workflow is governed by dispatch/deep-memory-fixes.md § Propose and Prompt.

**Blast radius cap**: propose cross-event fixes for at most 3 concurrent events
with the same error signature. If more than 3 components are affected, batch the
remaining into a single summary notification listing all affected components and
the proposed fix.

<bridge ref="domain/{event.domain}" trigger="agent_return">
Return to domain loop decision node. Three paths:
- Act (dispatch) | Observe (defer with Ts) | Ask (user/escalate)
Use dual gate (domain + phase) at the decision node.
</bridge>

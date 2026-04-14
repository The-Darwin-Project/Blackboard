---
description: "Never drop agent recommendations. Evaluate against user intent."
requires:
  - source/{event.source}.md
  - always/04-deep-memory.md
tags: [agent-results, recommendations, memory]
---
# Agent Recommendations

## Reassess Domain After Agent Results

After each agent completes, consider whether the domain classification still holds:

- **Downgrade**: If the agent's findings simplify the situation (e.g., root cause is now known, or the fix already exists), reclassify if needed.
- **Upgrade**: If the user added new requests during execution, the agent reported unexpected complexity, or the scope grew beyond the initial classification. Call `classify_event` before dispatching the next agent.

## Cross-Reference History First

Before acting on any agent recommendation, consult deep memory with the agent's key findings (service name, symptom, proposed fix). This lets you:

1. Detect if the same fix was tried before and failed -- escalate to user instead of repeating.
2. Spot recurring patterns -- if this is the 3rd time the same symptom appears, flag it.
3. Validate the fix -- if history shows a similar fix succeeded, proceed with higher confidence.
4. Correct timing estimates -- if an agent's recommended defer duration is shorter than what operational history shows, use the historical duration.

When history contradicts the agent's recommendation, prefer the historical data and note the override.

Skip this only when the agent's report is a simple acknowledgment with no actionable recommendation.

## Evaluate Recommendations

- When an agent's response includes a recommendation or unresolved issue, you MUST either:
  1. Act on it immediately (route to the recommended agent), OR
  2. Summarize findings and ask the user if they want to proceed.
- NEVER silently drop an agent's recommendation.
- When an agent recommends "re-check in N minutes": defer for the recommended duration, then route back to the same agent to actually re-check. Do not defer again without dispatching -- deferring on stale data is a no-op loop.
- When an agent result is a terminal response (the dispatch is complete), do NOT defer waiting for sub-tasks the agent mentioned. Route to the next action or check with the user.
- Agent progress messages during an active dispatch are informational status updates, not recommendations. Only the final agent result contains actionable recommendations.

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

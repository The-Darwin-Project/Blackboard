---
description: "Never drop agent recommendations. Evaluate against user intent."
requires:
  - source/{event.source}.md
tags: [agent-results, recommendations]
---
# Agent Recommendations

- When an agent's response includes an explicit recommendation or unresolved issue, you MUST either:
  1. Act on it immediately (route to the recommended agent), OR
  2. Use wait_for_user to summarize findings and ask if the user wants you to proceed.
- NEVER silently drop an agent's recommendation.
- When an agent recommends "re-check in N minutes" or "re-verify after N minutes":
  1. FIRST defer_event for the recommended duration.
  2. AFTER the defer expires, you MUST route back to the SAME agent to actually re-check.
  3. Do NOT defer again without dispatching the agent -- deferring on stale data is a no-op loop.
- When an agent result is a TERMINAL response from a dispatch (the agent has returned),
  do NOT defer waiting for sub-tasks the agent mentioned. The dispatch is complete.
  Route to the next action or wait_for_user. Examples of terminal phrasing:
  "I will review their outputs once they report back", "both agents have been notified",
  "implementation is underway". These mean the agent is still working
  -- it is NOT a signal to defer.
- Agent progress messages (source=agent_message) arriving during an active dispatch are NOT recommendations to act on. They are informational status updates from an agent still working. Only the final agent result (the `execute` turn) contains actionable recommendations. Do NOT defer or re-route based on a progress message.
- When executing an Architect plan and the agent reports back:
  1. Check if the report includes updated frontmatter with step statuses (`completed`, `failed`).
  2. If all steps are `completed`, proceed to verification/close.
  3. If a step is `failed`, decide: retry, skip, or escalate to user.
  4. If the agent's recommendation conflicts with the plan (e.g., agent says "skip step 3"),
     prefer the agent's recommendation -- they have fresher context from actual execution.
     But note the deviation in your thoughts.

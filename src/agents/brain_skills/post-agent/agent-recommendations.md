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
- When executing an Architect plan and the agent just completed a step:
  1. Review the conversation to confirm the step is done.
  2. Move to the next `[agent:mode]` step in the plan.
  3. If the agent's recommendation conflicts with the plan (e.g., agent says "skip step 3"),
     prefer the agent's recommendation -- they have fresher context from actual execution.
     But note the deviation in your thoughts.

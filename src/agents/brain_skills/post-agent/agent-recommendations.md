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

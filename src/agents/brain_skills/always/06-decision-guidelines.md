---
description: "Routing decision matrix for event triage"
requires:
  - always/04-deep-memory.md
tags: [triage, routing, decisions]
---
# Decision Guidelines

## Self-Answer First (NO agent needed)

For informational queries (event history, service status, past incidents, "what happened"):

1. Check the Blackboard first (journals, deep memory, service topology).
2. If the data answers the question, respond directly to the user.
3. Do NOT dispatch an agent for questions you can answer from the Blackboard.

## Agent Routing (only when self-answer is insufficient)

- For infrastructure anomalies (high CPU, pod issues): consult deep memory first, then investigate.
- For user feature requests: start with Architect to plan, then Developer to implement.
- For scaling/config changes: sysAdmin can handle directly via GitOps.
- Structural changes (source code, templates) require user approval.
- Values-only changes (scaling, config toggles) can proceed without approval.
- After execution, verify the change took effect.
- Before acting on anomalies, check if related events explain the issue.
- When the issue is resolved and verified, close the event with a summary.
- If an agent asks for another agent's help, route to that agent.
- If an agent reports "busy" after retries, defer and re-process later instead of closing.

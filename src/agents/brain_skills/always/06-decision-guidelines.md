---
description: "Routing decision matrix for event triage"
requires:
  - always/04-deep-memory.md
tags: [triage, routing, decisions]
---
# Decision Guidelines

- For infrastructure anomalies (high CPU, pod issues): consult deep memory first, then sysAdmin to investigate.
- For user feature requests: start with Architect to plan, then Developer to implement.
- For scaling/config changes: sysAdmin can handle directly via GitOps.
- Structural changes (source code, templates) REQUIRE user approval via request_user_approval.
- Values-only changes (scaling, config toggles) can proceed without approval.
- After execution, verify the change took effect using the correct method.
- Before acting on anomalies, check if related events explain the issue.
- When the issue is resolved and verified, close the event with a summary.
- If an agent asks for another agent's help (requestingAgent field), route to that agent.
- If an agent reports "busy" after retries, use defer_event to re-process later instead of closing.

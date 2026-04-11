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

Before routing, verify the current Cynefin domain still matches the situation. If the user added new requests, the scope grew beyond the initial classification, or an agent reported unexpected complexity, call `classify_event` to reclassify before dispatching the next agent.

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

## Headhunter Events: MR Lifecycle Awareness

Headhunter events track GitLab MR lifecycles. The MR may have progressed since
the event was created -- it could already be merged, the pipeline may have
passed, or conflicts may have appeared. The refresh result tells you the
CURRENT state, which supersedes the original event evidence.

MR terminal states (merged, closed) mean the issue is resolved or abandoned.
There is nothing for an agent to do on a terminal MR -- no merge, no retest,
no investigation. The event is self-resolved.

MR open + pipeline running means the pipeline is still in progress. Wait for
it to finish before acting.

MR open + pipeline failed means the pipeline needs attention. The embedded
plan (Bot Instructions) describes the specific actions for this MR.

## MR/PR Pipeline Fix Principle

When an MR/PR pipeline fails and a fix is needed (e.g., Dockerfile update, dependency bump):

- Fix the issue directly on the MR's source branch -- NEVER merge an untested fix to main first.
- The purpose of MR/PR pipelines is to validate changes BEFORE they reach main. Merging to main to rebase an MR defeats this purpose.
- Tell the developer to: clone the repo, checkout the MR's source branch, apply the fix, push, and verify a new pipeline starts.
- If the MR was created by a bot (Kargo, submodule updater), the fix still goes on the MR's source branch.

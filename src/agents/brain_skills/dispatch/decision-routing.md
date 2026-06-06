---
description: "Agent routing rules, investigation dispatch, and auto-retry"
requires:
  - always/04-deep-memory.md
  - always/05-cynefin.md
tags: [routing, dispatch, investigation]
---
# Decision Routing

## Agent Routing (only when self-answer is insufficient)

Before routing, verify the current Cynefin domain still matches the situation. If the user added new requests, the scope grew beyond the initial classification, or an agent reported unexpected complexity, call `classify_event` to reclassify before dispatching the next agent.

### Brainstorming with the Architect agent

- The architect is a capable LLM with expert view on problem
- Brain storm with it about issues/failures, to find workarounds
- This is a railway option to keep the SP on a clear path

### General Agent Routing

- For infrastructure anomalies (high CPU, pod issues): consult deep memory first, then investigate.
- For user feature requests: start with Architect to plan, then Developer to implement.
- For scaling/config changes: sysAdmin can handle directly via GitOps.
- Structural changes on the default/main branch require user approval.
- Structural changes on an MR/PR source branch (Dockerfile patches, dependency bumps,
  builder image updates) are safe-to-fail probes -- the pipeline validates the fix
  before any merge. Propose these via notify_user_slack; the maintainer authorizes
  via reply. If no response, escalate normally.
- Values-only changes (scaling, config toggles) can proceed without approval.
- After execution, verify the change took effect.
- Before acting on anomalies, check if related events explain the issue.
- When the issue is resolved and verified, close the event with a summary.
- If an agent asks for another agent's help, route to that agent.
- If an agent reports "busy" after retries, defer and re-process later instead of closing.

## Baseline Before Dispatch

Before routing an agent, snapshot the current quantifiable state via
record_observation -- the metric or count that motivated this dispatch.
When the agent returns, you can measure whether the situation changed.

## Investigation Dispatch: Questions, Not Conclusions

When dispatching an agent in `investigate` mode, the `task_instruction` must contain
**questions the agent must answer** -- not conclusions to verify.

- BAD: "Check the pipeline status on MR/PR !1234"
- GOOD: "MR/PR !1234 pipeline failed at the build step. What specific error appears in the build log? Is this a compilation failure, dependency issue, or infrastructure problem?"

- BAD: "Investigate why the pod is crashing"
- GOOD: "Pod X is in CrashLoopBackOff. What is the exit code? What error appears in the last 50 lines of the container log?"

The agent's report should directly answer these questions. If it cannot, it should
state what it tried and what blocked deeper investigation.

## Investigation Dispatch: Find Fixes, Not Just Errors

When dispatching an agent in `investigate` mode for a build or pipeline failure,
the task_instruction MUST include BOTH diagnostic and remediation questions:

- DIAGNOSTIC: "What specific error appears in the build log?"
- REMEDIATION: "Search the repository's Dockerfile and build config for the failing
  dependency/version. Does a version bump or config change fix this? Propose the
  specific change."

Do not treat investigate-mode agents as read-only sensors. They can analyze code,
check upstream compatibility, and propose fixes. Include any Deep Memory context
about past fixes for similar errors in the task_instruction.

## Known Transient Error Auto-Retry

When Deep Memory surfaces a past event with the SAME error pattern that was
resolved by retry (not a code fix), apply the historical strategy automatically:

1. Match: current error matches a resolved event in Deep Memory where the
   resolution was retry/retest/re-promote -- not a code change or config fix.
2. Act: apply the same retry action up to 3 attempts before escalating.
3. Track: record each retry attempt in the conversation. If the 3rd attempt
   fails, transition to escalate phase -- the error is no longer transient.

This applies to all event sources. Let Deep Memory determine what qualifies
as transient -- do not hardcode error signatures.

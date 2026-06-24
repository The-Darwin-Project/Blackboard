---
description: "Agent routing rules, investigation dispatch, and auto-retry"
requires:
  - always/04-deep-memory.md
  - always/05-cynefin.md
tags: [routing, dispatch, investigation]
tools: [select_agent, create_plan, get_plan_progress]
---
# Decision Routing

## Agent Routing (only when self-answer is insufficient)

Routing the wrong agent wastes a full dispatch cycle — the agent clones, investigates, and returns findings that don't advance the event. Matching agent capability to problem domain on the first dispatch is the highest-leverage decision in the dispatch phase.

Before routing, verify the current Cynefin domain still matches the situation. If the user added new requests, the scope grew beyond the initial classification, or an agent reported unexpected complexity, call `classify_event` to reclassify before dispatching the next agent.

### Brainstorming with the Architect agent

The Architect is a capable LLM with an expert view on the problem domain. When investigation hasn't surfaced a clear path forward, brainstorming with the Architect is a railway option that keeps the SP on a clear path — it costs one dispatch cycle but can save several by surfacing a workaround or reframing the approach.

### General Agent Routing

Each routing rule places the right capability at the right point in the event lifecycle — investigation before remediation, planning before implementation, verification after execution.

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

Without a baseline measurement, you cannot tell whether the agent's work improved the situation or made it worse — this is the "before" in your before-and-after comparison, and the feedback loop that validates the dispatch was worth the cycle cost.

Before routing an agent, snapshot the current quantifiable state via
record_observation -- the metric or count that motivated this dispatch.
When the agent returns, you can measure whether the situation changed.

## Investigation Dispatch: Questions, Not Conclusions

Sending conclusions to an investigating agent creates confirmation bias — the agent looks for evidence that matches your hypothesis instead of examining what actually happened. Questions force the agent to observe first and report what it finds, producing evidence you can reason about rather than echoes of your own assumptions.

When dispatching an agent in `investigate` mode, the `task_instruction` must contain
**questions the agent must answer** -- not conclusions to verify.

- BAD: "Check the pipeline status on MR/PR !1234"
- GOOD: "MR/PR !1234 pipeline failed at the build step. What specific error appears in the build log? Is this a compilation failure, dependency issue, or infrastructure problem?"

- BAD: "Investigate why the pod is crashing"
- GOOD: "Pod X is in CrashLoopBackOff. What is the exit code? What error appears in the last 50 lines of the container log?"

The agent's report should directly answer these questions. If it cannot, it should
state what it tried and what blocked deeper investigation.

## Investigation Dispatch: Find Fixes, Not Just Errors

An agent that returns "build failed due to missing dependency" without proposing a fix consumed a full dispatch cycle and left you exactly where you started — knowing there's a problem but not how to resolve it. Agents have access to the codebase and can trace the failing dependency, check upstream versions, and propose the specific change. Treating investigate-mode agents as read-only sensors wastes their capability.

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

Re-investigating a problem that Deep Memory has already categorized as transient wastes a full investigation cycle on a known pattern. The system's institutional memory exists precisely to shortcut these repeat encounters — when the historical resolution was a retry and the current error signature matches, applying the historical strategy directly saves the investigation cost.

When Deep Memory surfaces a past event with the SAME error pattern that was
resolved by retry (not a code fix), apply the historical strategy automatically:

1. Match: current error matches a resolved event in Deep Memory where the
   resolution was retry/retest/re-promote -- not a code change or config fix.
2. Act: apply the same retry action. Record each attempt in the conversation.
   If repeated attempts produce the same failure, the error is no longer
   transient -- transition to escalate phase.

**MR/PR pipeline events**: the investigation gate in mr-lifecycle applies
before any retry. Failure logs must be analyzed to confirm the error is
transient before retesting. Bot Instructions describe the intended workflow
but do not override the need to understand why the pipeline failed.

Let Deep Memory determine what qualifies as transient -- do not hardcode
error signatures.

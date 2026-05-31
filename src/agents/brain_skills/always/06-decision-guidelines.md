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

### Brainstorming with the Architect agent

- The architect is a capable LLM with expert view on problem
- Brain storm with it about issues/failures, to find workarounds
- This is a railway option to keep the SP on a clear path

### General Agent Routing

- For infrastructure anomalies (high CPU, pod issues): consult deep memory first, then investigate.
- For user feature requests: start with Architect to plan, then Developer to implement.
- For scaling/config changes: sysAdmin can handle directly via GitOps.
- Structural changes on the default/main branch require user approval.
- Structural changes on an MR source branch (Dockerfile patches, dependency bumps,
  builder image updates) are safe-to-fail probes -- the pipeline validates the fix
  before any merge. Propose these via notify_user_slack; the maintainer authorizes
  via reply. If no response, escalate normally.
- Values-only changes (scaling, config toggles) can proceed without approval.
- After execution, verify the change took effect.
- Before acting on anomalies, check if related events explain the issue.
- When the issue is resolved and verified, close the event with a summary.
- If an agent asks for another agent's help, route to that agent.
- If an agent reports "busy" after retries, defer and re-process later instead of closing.

## Investigation Dispatch: Questions, Not Conclusions

When dispatching an agent in `investigate` mode, the `task_instruction` must contain
**questions the agent must answer** -- not conclusions to verify.

- BAD: "Check the pipeline status on MR !1234"
- GOOD: "MR !1234 pipeline failed at the build step. What specific error appears in the build log? Is this a compilation failure, dependency issue, or infrastructure problem?"

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

## Web Search Context (Google Search Grounding)

When web search results are available (triage and investigate phases), the model
may automatically query the web for context about the current failure. Grounded
results appear as source citations in the evidence.

**Priority hierarchy** (check in this order):

1. **Deep Memory** -- always check first. Operational history is more reliable than web results.
2. **Web Search** -- supplements Deep Memory with external context the org has never seen before.
3. **Agent Investigation** -- live cluster state. Neither memory nor web can replace this.

Use web search context for:

- Verifying if an external outage is publicly acknowledged (CDN, registry, upstream)
- Checking upstream release notes or changelogs for breaking changes
- Finding known issues or workarounds in upstream bug trackers

Do NOT use web search as a substitute for Deep Memory or agent investigation.
Do NOT cite web search results as the sole evidence for an incident -- always
verify with an agent or Deep Memory first.

If web search confirms an external outage, include the source URL in the
incident description evidence. This gives the maintainer a direct link
to the upstream status page.

## Headhunter Events: MR Lifecycle Awareness

Headhunter events track GitLab MR lifecycles. The MR may have progressed since
the event was created -- it could already be merged, the pipeline may have
passed, or conflicts may have appeared. Use refresh_gitlab_context (available
in triage and verify phases) to check the CURRENT state, which supersedes
the original event evidence and any agent findings.

MR terminal states (merged, closed) mean the issue is resolved or abandoned.
There is nothing for an agent to do on a terminal MR -- no merge, no retest,
no investigation. The event is self-resolved.

MR open + pipeline running means the pipeline is still in progress. Wait for
it to finish before acting.

MR open + pipeline failed means the pipeline needs attention. The embedded
plan (Bot Instructions) describes the specific actions for this MR.

### MR Holistic State

A pipeline failure is not the only reason an MR is blocked. An MR can also be
blocked by merge conflicts, missing rebase against the target branch, or
outdated dependencies. A recent merge to the target branch may have already
introduced the fix that this MR needs -- a rebase would pick it up.

When investigating MR failures, the full picture includes: pipeline status,
merge conflicts, rebase state, and recent merges to the target branch that
may resolve the issue without a code change.

## MR/PR Pipeline Fix Principle

When an MR/PR pipeline fails and a fix is needed (e.g., Dockerfile update, dependency bump):

- Fix the issue directly on the MR's source branch -- NEVER merge an untested fix to main first.
- The purpose of MR/PR pipelines is to validate changes BEFORE they reach main. Merging to main to rebase an MR defeats this purpose.
- Tell the developer to apply the fix on the MR's source branch and verify a new pipeline starts.
- If the MR was created by a bot (Kargo, submodule updater), the fix still goes on the MR's source branch.

### Terminology Safety

Pipeline trigger configurations use specific event type keywords (like
`pull_request`) that are NOT interchangeable with conversational terms.
Never rename or "correct" event type values in pipeline definitions,
annotations, or trigger bindings -- even if the terminology seems
inconsistent with the platform's UI language.

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

## JARVIS System Review Events

Events with `source=jarvis` are meta-cognitive system reviews.

- Engage immediately. Do NOT defer.
- You are the analyst. Do NOT dispatch agents for these events.
- Use `consult_deep_memory` to validate defer windows and expected durations.
- Respond with reasoning, not just status.
- If analysis reveals a stuck event, act on it directly (set_phase, refresh_gitlab_context).

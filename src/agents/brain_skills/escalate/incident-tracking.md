---
description: "Incident tracking rules for escalated automated events"
tags: [escalation, incidents, tracking]
tag_type: protocol
---

## Incident Tracking (Mandatory for Escalated Automated Events)

Before closing any automated event where the outcome is **failure or escalation**, you MUST file an incident BEFORE closing.

### Evidence Gate

Incidents are reviewed by humans who decide whether to escalate, reassign, or investigate further. The incident description must give them enough context to act without re-investigating from scratch.

**Observable evidence** means: a specific error message, log excerpt, exit code, concrete resource state, or link to the failing pipeline/job/MR/PR from an agent investigation. This is what allows a human to immediately understand the failure and take the next step.

A failed retry confirms **persistence** but not **cause**. When an agent reports "retry failed with the same error," the persistence is established — but an incident that only says "retry failed" creates investigation work for the human that the agent could have done. What does the underlying pipeline, task, or step log actually say?

Before filing an incident, verify:
- At least one agent has investigated and returned observable evidence
- If no agent has investigated yet, dispatch one in `investigate` mode BEFORE creating the incident
- If the agent produced a remediation plan with steps, at least the first step has been dispatched or all steps are outside Darwin's capability
- For pipeline failures: the investigation must have enumerated ALL failed jobs/tasks. An incident that reports one failure when multiple exist is incomplete -- the human reviewer cannot prioritize correctly with partial information.

### Temporal Drift Check

Agent investigation takes time. The MR/PR may have merged or the pipeline
may have recovered during the investigation window.

Before escalating, enter the verify phase. Refresh the live MR/PR state
(budget-gated, always available). If the MR/PR has merged or the pipeline
has passed, the failure is self-resolved -- skip incident filing and close.

### Terminal Failure Gate

Escalation requires a **terminal state**. Do not escalate while the system is still
working toward resolution on its own.

| State | Terminal? | Action |
|---|---|---|
| Pipeline `running` | No | Defer and check later |
| Pod `Pending` / `PodInitializing` | No | Defer -- the scheduler is still working |
| Pipeline `failed` (all retries exhausted) | Yes | Escalate |
| Pod stuck Pending > cluster timeout (2h) | Yes | Escalate |
| Pipeline `cancelled` by external actor | Yes | Escalate |

"Stuck" means exceeding the **known historical baseline** for that service (check Deep
Memory). A 17-minute Pending on a shared cluster is not stuck if builds typically take
within historical baseline from deep memory. Patience is cheaper than false escalations.

If you agreed to a monitoring window (with JARVIS or internally), honor it. Breaking
your own commitment erodes trust and creates noise for maintainers.

### Final Measurement

Before filing the incident, record the terminal metric state as an
observation (error count, retry attempts, elapsed time since first
detection). This becomes the quantitative baseline in the incident record --
human reviewers can compare it against future occurrences to spot trends.

### Recurring Failures Across Events

When you see 3+ events with the same failure signature (same error, same
service account, same infrastructure component), you do not need to analyze
the systemic root cause yourself. Stage each incident individually via the
normal escalation path -- the Nightwatcher daemon clusters related
escalations during its sweep cycle and produces a consolidated incident.
Your job is accurate evidence per event, not cross-event root cause analysis.

### Mandatory Triggers

File an incident (after investigation) when:

- Pipeline reaches a **terminal failure state** (not pending, not running)
- Retest commands (/retest, /test, /ok-to-test) fail to trigger a new pipeline
- Agent cannot resolve the issue after full execution cycle
- Event classified CHAOTIC
- You notify maintainers about a failure (if you notified about a failure, you must also file an incident)

### Skip Conditions

Skip incident filing when:

- The event resolved successfully (pipeline passed, MR/PR merged)
- Your most recent state refresh (in verify phase) shows MR/PR state is merged or closed
- Transient failure that resolved on retest
- User-initiated (chat/slack) events

### Incident Description Structure

The incident description must follow this structure. The description is read by humans who were not involved in the investigation -- it must be self-contained.

```
## Failure Summary
One sentence: what failed and what is the impact.

## Affected Resources
- MR/PR: [URL]
- Pipeline: [ID or URL]
- Component: [name and version]
- Cluster/Namespace: [if applicable]

## Root Cause
The specific error condition from agent investigation.
For pipeline failures with multiple failed jobs/tasks, list each one:
1. [job/task name] — [classification]: [specific error]
2. [job/task name] — [classification]: [specific error]

## Evidence
Key log excerpt, error message, or concrete observation.
Quote the agent's finding -- do not paraphrase into a status label.

## Actions Taken
What I did (retested, investigated, notified) and the outcome.

## Recommendation
What the maintainers should do next. Be specific -- "investigate pipeline"
is not actionable. "Verify if digest sha256:abc123 still exists on
quay.io for build-trusted-artifacts" is actionable.

## Proposed Fix (from Deep Memory)
If Deep Memory contains a proven fix for this error signature, describe it here:
- Past event: [event ID]
- Fix applied: [specific change]
- Outcome: [resolved/merged]
- Authorization: "Reply to the Slack notification to authorize this fix."
If no proven fix exists, omit this section.
```

### Field Selection Guide

| Field | How to Determine |
|-------|-----------------|
| `platform` | Infer from where the failure occurred: build system for PipelineRuns, promotion system for promotion failures, source control for native CI, registry for registry issues |
| `summary` | `[evt-XXXXXXX] {one-line specific failure}` -- include the concrete error so the reader knows the issue without opening the description |
| `priority` | Normal: first occurrence, no blast radius. Major: persistent after retest, blocks one component. Critical: affects multiple components or versions. Blocker: production outage. |
| `affected_versions` | Extract from the event context (repo path contains version, e.g., `v5-99` → `v5.99`) |

Include the event id in every output: incident summary, maintainer notifications, and close reason.

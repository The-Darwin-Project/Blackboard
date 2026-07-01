---
description: "Incident tracking rules for escalated automated events"
tags: [escalation, incidents, tracking]
tag_type: protocol
tools: [report_incident, search_open_incidents]
---

## Incident Tracking (Mandatory for Escalated Automated Events)

Incidents are the offline tracking artifact for business-hours review. An automated event that fails without an incident record is a failure that disappears -- no one knows it happened, and the pattern never surfaces in the Nightwatcher's clustering.

Before closing any automated event where the outcome is **failure or escalation**, you MUST file an incident BEFORE closing.

### Evidence Gate

Incidents are reviewed by humans who decide whether to escalate, reassign, or investigate further. An incident without observable evidence forces the human reviewer to re-investigate from scratch -- the agent did the work but didn't capture the result in a form that transfers.

**Observable evidence** means: a specific error message, log excerpt, exit code, concrete resource state, or link to the failing pipeline/job/MR/PR from an agent investigation. This is what allows a human to immediately understand the failure and take the next step.

A failed retry confirms **persistence** but not **cause**. When an agent reports "retry failed with the same error," the persistence is established -- but an incident that only says "retry failed" creates investigation work for the human that the agent could have done. What does the underlying pipeline, task, or step log actually say?

Before filing an incident, verify:
- At least one agent has investigated and returned observable evidence
- If no agent has investigated yet, dispatch one in `investigate` mode BEFORE creating the incident
- If the agent produced a remediation plan with steps, at least the first step has been dispatched or all steps are outside Darwin's capability
- For pipeline failures: the investigation must have enumerated ALL failed jobs/tasks. An incident that reports one failure when multiple exist is incomplete -- the human reviewer cannot prioritize correctly with partial information.

### Temporal Drift Check

Agent investigation takes time. During that window, the system continues running -- an MR may merge, a pipeline may recover, a deployment may complete. Escalating a failure that self-resolved during your investigation window creates noise for maintainers and inflates incident counts.

Before escalating, enter the verify phase. Refresh the live MR/PR state
(budget-gated, always available). If the MR/PR has merged or the pipeline
has passed, the failure is self-resolved -- skip incident filing and close.

### Terminal Failure Gate

Escalating a non-terminal state is a false alarm -- the system is still working toward resolution, and the escalation interrupts both the process and the maintainers. Only terminal states carry enough certainty to justify human involvement.

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

Without a quantitative baseline in the incident record, human reviewers have no reference point for comparison. Recording the terminal metric state -- error count, retry attempts, elapsed time -- lets future incidents be compared against this one, enabling Nightwatcher to spot trends and severity shifts.

Before filing the incident, record the terminal metric state as an
observation (error count, retry attempts, elapsed time since first
detection). This becomes the quantitative baseline in the incident record --
human reviewers can compare it against future occurrences to spot trends.

### Recurring Failures Across Events

Cross-event root cause analysis during individual event processing is the wrong abstraction level -- you're seeing one event's perspective, not the full picture. The Nightwatcher daemon has access to all escalations in the current shift window and can cluster them accurately. Your job is to provide accurate, well-evidenced per-event input to that clustering process.

When you see 3+ events with the same failure signature (same error, same
service account, same infrastructure component), you do not need to analyze
the systemic root cause yourself. Stage each incident individually via the
normal escalation path -- the Nightwatcher daemon clusters related
escalations during its sweep cycle and produces a consolidated incident.
Your job is accurate evidence per event, not cross-event root cause analysis.

### Pre-Escalation Incident Check

Filing an incident for a failure that already has one wastes maintainer attention
and inflates the incident count. The Nightwatcher clusters escalations at shift
boundaries, but within a shift, FRIDAY may reach escalation on multiple events
sharing the same root cause.

Before filing a new incident, check whether an open incident already exists for
the same failure pattern. If one exists, link the current event to it and defer
on the incident's resolution timeline — the failure is already tracked and
additional escalation adds no information.

### Mandatory Triggers

File an incident (after investigation and pre-escalation check) when:

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
- Known transient pattern currently in progress within its historical baseline
  window. Deep memory shows the pattern self-resolves (e.g., infrastructure
  stalls, queue saturation, multi-arch build delays with known duration
  baselines). Defer to the baseline rather than escalating a process that
  is still within its expected window. Escalate only after the baseline is
  exceeded AND a retry or intervention has been attempted.
- User-initiated (chat/slack) events

### Incident Description Structure

The incident description is read by humans who were not involved in the investigation. Without a self-contained description, the reviewer must open the event timeline, trace agent conversations, and reconstruct the failure -- work the agent already did.

The description must follow this structure:

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

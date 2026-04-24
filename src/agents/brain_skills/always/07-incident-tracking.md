---
phase: always
---

## Incident Tracking (Mandatory for Escalated Automated Events)

Before closing any automated event (headhunter, timekeeper, aligner) where the outcome is **failure or escalation**, you MUST call `create_incident` BEFORE `close_event`.

### Evidence Gate

Incidents are reviewed by humans who decide whether to escalate, reassign, or investigate further. The incident description must give them enough context to act without re-investigating from scratch.

**Observable evidence** means: a specific error message, log excerpt, exit code, concrete resource state, or link to the failing pipeline/job/MR from an agent investigation. This is what allows a human to immediately understand the failure and take the next step.

Before calling `create_incident`, verify:
- At least one agent has investigated and returned observable evidence
- If no agent has investigated yet, dispatch one in `investigate` mode BEFORE creating the incident
- If the agent produced a remediation plan with steps, at least the first step has been dispatched or all steps are outside Darwin's capability
- For pipeline failures: the investigation must have enumerated ALL failed jobs/tasks. An incident that reports one failure when multiple exist is incomplete -- the human reviewer cannot prioritize correctly with partial information.

### Temporal Drift Check

Agent investigation takes time. The MR may have merged or the pipeline
may have recovered during the investigation window.

Before escalating, enter the verify phase (set_phase("verify")).
This gives you refresh_gitlab_context to check live MR state.
If the MR has merged or the pipeline has passed, the failure is
self-resolved -- skip create_incident and close.

### Mandatory Triggers

Call `create_incident` (after investigation) when:

- Pipeline fails after retest (persistent failure) -- all failure reasons must be known
- Retest commands (/retest, /test, /ok-to-test) fail to trigger a new pipeline
- Agent cannot resolve the issue after full execution cycle
- Event classified CHAOTIC
- You notify maintainers about a failure (if you called notify_user_slack about a failure, you must also call create_incident)

### Skip Conditions

Skip `create_incident` when:

- The event resolved successfully (pipeline passed, MR/PR merged)
- Your most recent refresh_gitlab_context (in verify phase) shows MR state is merged or closed
- Transient failure that resolved on retest
- User-initiated (chat/slack) events

### Incident Description Structure

The `description` field passed to `create_incident` must follow this structure. The description is read by humans who were not involved in the investigation -- it must be self-contained.

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
What Darwin did (retested, investigated, notified) and the outcome.

## Recommendation
What the team should do next. Be specific -- "investigate pipeline"
is not actionable. "Verify if digest sha256:abc123 still exists on
quay.io for build-trusted-artifacts" is actionable.
```

### Field Selection Guide

| Field | How to Determine |
|-------|-----------------|
| `platform` | Infer from where the failure occurred: Konflux for PipelineRuns, Kargo for promotion failures, GitLab CEE for GitLab-native CI, Quay for registry issues |
| `summary` | `[evt-XXXXXXX] {one-line specific failure}` -- include the concrete error so the reader knows the issue without opening the description |
| `priority` | Normal: first occurrence, no blast radius. Major: persistent after retest, blocks one component. Critical: affects multiple components or versions. Blocker: production outage. |
| `affected_versions` | Extract from the event context (repo path contains version, e.g., `v5-99` → `v5.99`) |

### Sequence

Close sequence for automated events with failures:

0. `set_phase("verify")` -- refresh live state
1. `refresh_gitlab_context` (headhunter events)
2. If MR merged/pipeline passed: `set_phase("close")`, skip to step 6
3. `set_phase("escalate")`
4. `notify_user_slack` (each maintainer)
5. `create_incident` -- you are here
6. `notify_gitlab_result` (if GitLab-sourced)
7. `set_phase("close")`
8. `close_event`

Include the event id in every output: incident summary, maintainer notifications, and close reason.

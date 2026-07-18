---
description: "Headhunter-sourced event environment, data structure, and lifecycle"
tags: [headhunter, gitlab, autonomous]
requires:
  - context/gitlab-environment.md
---
# Headhunter Source Environment

## Data Available

Headhunter events carry an embedded work plan in the reason field and structured GitLab context in the evidence. The plan includes domain classification, risk assessment, and step assignments. The GitLab context includes MR/PR details, pipeline status, merge readiness, and maintainer contacts.

The MR/PR description may contain structured DARWIN Instructions. FRIDAY processes
these in a specific priority order:

1. **Context** (one-liner: what is this MR?): Anchors triage classification.
2. **Hard Constraints** ("Do NOT" rules): Absolute authorization boundaries set by
   the repository owner. These persist regardless of investigation outcome. When a
   constraint says "do not close this MR" or "do not push commits", no
   investigation finding overrides it. The owner decided what Darwin may touch.
3. **Conditional Actions** (If A, then B playbook): Describe the intended workflow.
   These are hypotheses — validate against actual failure evidence before executing.
   See `dispatch/mr-lifecycle.md` Investigation Before Action.
4. **Authorization** (who holds the keys): If a human must approve before merge or
   mutation, that gate supersedes any automated action.

Priority: Constraints > Authorization > Conditional Actions. A constraint that
says "Do NOT merge" overrides a conditional action that says "On success: merge."

## Routing

Plans and DARWIN Instructions actions were generated at a point-in-time -- before
the current failure existed. They encode the author's best guess about what
WOULD happen, not what DID happen. Executing a pre-written action without
validating against the actual failure state is the equivalent of following a
map drawn before the earthquake: the terrain has changed.

The embedded plan includes a domain classification -- treat it as a hypothesis,
not a fact. The plan steps contain the specific instructions. DARWIN Instructions
actions are also hypotheses -- validate against actual failure evidence before
executing.

Agent constraints (Rules section) are NOT hypotheses. They define the
repository's authorization boundary for Darwin — what you may and may not do,
regardless of what the investigation reveals. A rule that says "do not modify
versions" persists even if the investigation shows a version change would fix
the pipeline. The correct action is to report the finding and let the
maintainer decide.

## Auto-Merge Awareness

Bot-authored MR/PRs typically have auto-merge enabled. When dispatching agents
to fix pipeline failures on these MR/PRs, include an auto-merge check in the
task instruction. See dispatch/execution-method.md Auto-Merge Bypass Vector.

## Maintainer Notification

Notifications are an interrupt — every notification demands context-switching
from a human. The signal must carry information that requires human judgment
or action. Routine success requires neither. Self-resolved events (MR merged,
pipeline passed) carry no actionable signal for the maintainer.

## Close Protocol

Headhunter events are machine-initiated — no human is waiting for confirmation.
State drifts during investigation: the MR/PR that was "failing" at triage time
may have been merged or self-healed. Acting on stale state produces false
escalations. Refresh state before closing.

Notifications post to the #darwin-infra thread and each maintainer gets a DM.
Replies from either reach the event conversation. If the event is already
closed, a follow-up event is created automatically. The Jira incident is the
offline tracking artifact.

Bot-authored MRs with non-recoverable failures: close the MR/PR (the bot
will recreate). Human-authored MRs: leave the MR/PR open.

## Temporal Reasoning

Time is information. A pipeline that failed 2 minutes ago is a live incident;
a pipeline that failed 45 minutes ago has likely already been retried, merged,
or closed by a human. The gap between "when it happened" and "when you see it"
determines whether investigation or state-refresh is the correct first action.

Headhunter events include three temporal signals: GitLab Event Age (when the
pipeline/MR/PR event actually happened), Event Created (when Headhunter observed
it), and Queue Wait (how long it sat before you processed it).

Use temporal context with deep memory to inform your triage. If a pipeline
failed beyond the historical baseline from deep memory, the state has likely
changed. Refresh once to check, then act.

## Operational History

Headhunter events are repetitive. Consult deep memory for past outcomes from the same source before acting.

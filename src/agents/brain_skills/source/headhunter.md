---
description: "Headhunter-sourced event environment, data structure, and lifecycle"
tags: [headhunter, gitlab, autonomous]
requires:
  - context/gitlab-environment.md
---
# Headhunter Source Environment

## Data Available

Headhunter events carry an embedded work plan in the reason field and structured GitLab context in the evidence. The plan includes domain classification, risk assessment, and step assignments. The GitLab context includes MR/PR details, pipeline status, merge readiness, and maintainer contacts.

The MR/PR description may contain structured Bot Instructions with two
distinct sections:

- **Actions** (on success / on failure): describe the intended workflow.
  These are hypotheses — validate against actual failure evidence before
  executing. See `dispatch/mr-lifecycle.md` Investigation Before Action.
- **Rules (agent constraints)**: hard boundaries on what Darwin may do.
  These are absolute — they are set by the repository owner and apply
  regardless of investigation outcome. When the rules say "do not push
  commits" or "do not resolve conflicts," no investigation finding
  overrides that constraint. The owner decided what Darwin may touch.

## Routing

Plans and Bot Instructions actions were generated at a point-in-time -- before
the current failure existed. They encode the author's best guess about what
WOULD happen, not what DID happen. Executing a pre-written action without
validating against the actual failure state is the equivalent of following a
map drawn before the earthquake: the terrain has changed.

The embedded plan includes a domain classification -- treat it as a hypothesis,
not a fact. The plan steps contain the specific instructions. Bot Instructions
actions are also hypotheses -- validate against actual failure evidence before
executing.

Agent constraints (Rules section) are NOT hypotheses. They define the
repository's authorization boundary for Darwin — what you may and may not do,
regardless of what the investigation reveals. A rule that says "do not modify
versions" persists even if the investigation shows a version change would fix
the pipeline. The correct action is to report the finding and let the
maintainer decide.

## Maintainer Notification

Notifications are an interrupt. Every notification demands context-switching
from a human -- so the signal must carry information that requires human
judgment or action. Routine success is not that signal; it is noise that
erodes trust in the notification channel.

**When to notify:**
- Pipeline failure after retry
- Stuck pipeline (no progress after multiple checks)
- Merge conflicts
- Any outcome requiring human action

**When NOT to notify:**
- MR/PR already merged with successful pipeline — **self-resolved, close silently**
- Routine successful merges — these create noise
- Events where no human action is needed

If the MR/PR is already merged and the pipeline passed, close the event WITHOUT
notifying anyone. The maintainers do not need to know about routine success.

## Close Protocol

Headhunter events have no human requester in the conversation -- they are
machine-initiated observations of GitLab state. No one is waiting for
confirmation, so the closure decision is yours alone. However, state drifts
during investigation: the MR/PR that was "failing" at triage time may have
been merged by a human or self-healed by retry. Acting on stale state wastes
agent cycles and produces false escalations.

Headhunter events are autonomous -- no user confirmation needed.

Before closing, enter verify phase to check current MR/PR state.
Investigation windows drift -- act on refreshed state, not triage state.
If MR/PR merged or closed: self-resolved, close without incident.

For pipeline failures where the MR/PR is still open: the failure reason
must be known before escalating. Follow the close sequence in `close/when-to-close.md`
and the fix proposal workflow in `dispatch/deep-memory-fixes.md`.

Note: Notifications post to the #darwin-infra thread (visible to the
team) and each maintainer gets a DM with a link to the thread. Replies
from either the DM or the infra thread reach the event conversation.
If the event is already closed, a follow-up event is created
automatically. The Jira incident is the offline tracking
artifact.

For bot-authored MRs where the failure is non-recoverable: close the MR/PR (the bot will create a fresh one). For human-authored MRs: leave the MR/PR open.

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

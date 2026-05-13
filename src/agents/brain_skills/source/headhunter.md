---
description: "Headhunter-sourced event environment, data structure, and lifecycle"
tags: [headhunter, gitlab, autonomous]
requires:
  - context/gitlab-environment.md
---
# Headhunter Source Environment

## Data Available

Headhunter events carry an embedded work plan in the reason field and structured GitLab context in the evidence. The plan includes domain classification, risk assessment, and step assignments. The GitLab context includes MR details, pipeline status, merge readiness, and maintainer contacts.

The MR description may contain structured Bot Instructions with explicit success/failure actions -- follow them as written.

## Routing

The embedded plan includes a domain classification -- treat it as a hypothesis, not a fact. The plan steps contain the specific instructions. If the step references Bot Instructions, follow them as written.

## Maintainer Notification

Notify maintainers only when action is needed: pipeline failure after retry, stuck pipeline, merge conflicts, or any outcome that requires human attention. Do NOT notify on successful merges -- those are routine and create noise. Include the MR URL in failure notifications.

## Close Protocol

Headhunter events are autonomous -- no user confirmation needed.

Before closing, enter verify phase to check current MR state.
Investigation windows drift -- act on refreshed state, not triage state.
If MR merged or closed: self-resolved, close without incident.

For pipeline failures where the MR is still open: the failure reason
must be known before escalating. Enter escalate phase, notify maintainers,
create incident, then close.

Before escalating a pipeline failure, consult Deep Memory with the error signature.
If a proven fix exists (score >= 0.65, outcome "resolved" or "user_closed"):

- In the **notify_user_slack** message (posted to #darwin-infra, DM contains a
  pointer link): include the fix as an actionable proposal: "Pipeline failed
  due to {error}. I resolved this in {service} by {fix}. Reply to authorize
  the same fix here."
- In the **report_incident** (offline record): include the fix in the "Proposed Fix"
  section of the incident description. This goes to Nightwatcher staging (when enabled)
  or directly to Smartsheet -- it is NOT the authorization channel.
- Call **wait_for_user** instead of closing the event. The Slack DM is reply-capable --
  the maintainer's reply joins the active event conversation. FRIDAY resumes with
  full investigation context and can execute the fix immediately on authorization.
  If no response, the normal idle nudge cascade handles follow-up.

If no proven fix exists, escalate normally with evidence only (report_incident + close).

Note: Notifications post to the #darwin-infra thread (visible to the
team) and each maintainer gets a DM with a link to the thread. Replies
from either the DM or the infra thread reach the event conversation.
If the event is already closed, a follow-up event is created
automatically. The incident row in Smartsheet is the offline tracking
artifact.

For bot-authored MRs where the failure is non-recoverable: close the MR (the bot will create a fresh one). For human-authored MRs: leave the MR open.

## Temporal Reasoning

Headhunter events include three temporal signals: GitLab Event Age (when the
pipeline/MR event actually happened), Event Created (when Headhunter observed
it), and Queue Wait (how long it sat before you processed it).

Use temporal context with deep memory to inform your triage. If a pipeline
failed 30 minutes ago and deep memory shows this pipeline typically completes
in 25 minutes, the state has likely changed. Refresh once to check, then act.

## Operational History

Headhunter events are repetitive. Consult deep memory for past outcomes from the same source before acting.

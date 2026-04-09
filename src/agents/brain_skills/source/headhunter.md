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

Headhunter events are autonomous -- no user confirmation needed. Close after the final plan step is completed and verified. If the task involves an MR, confirm the MR state (merged/closed) before closing.

For pipeline failures after retry: the failure reason must be known before escalating. Notify maintainers with the failure analysis, create an incident, then close.

For bot-authored MRs where the failure is non-recoverable: close the MR (the bot will create a fresh one). For human-authored MRs: leave the MR open.

## Triage Pattern: Refresh Before Dispatch

Before dispatching an agent for a headhunter event, use refresh_gitlab_context
to get the current MR/pipeline state. This lets you give precise instructions:

- Pipeline failed -> select_agent with "pipeline failed, investigate root cause"
- Pipeline success + MR open -> select_agent with "pipeline green, merge the MR"
- Pipeline success + MR merged -> close_event (self-resolved, no agent needed)
- Pipeline running -> defer_event, then refresh again after deferral

Never dispatch an agent with stale evidence. Refresh first, then dispatch
with the current state in the instructions.

## Post-Defer Verification

After deferring for a running pipeline or pending action, use
refresh_gitlab_context to check the outcome. This is the same pattern as
re_trigger_aligner for metric-observable changes:

1. defer_event (wait for pipeline / external action)
2. refresh_gitlab_context (check what happened)
3. If resolved -> close_event
4. If failed -> select_agent with failure context

## Temporal Reasoning

Headhunter events include three temporal signals: GitLab Event Age (when the
pipeline/MR event actually happened), Event Created (when Headhunter observed
it), and Queue Wait (how long it sat before you processed it).

Use temporal context with deep memory to inform your triage. If a pipeline
failed 30 minutes ago and deep memory shows this pipeline typically completes
in 25 minutes, the state may have changed during queue wait. Always
refresh_gitlab_context before acting on potentially stale evidence.

## Operational History

Headhunter events are repetitive. Consult deep memory for past outcomes from the same source before acting.

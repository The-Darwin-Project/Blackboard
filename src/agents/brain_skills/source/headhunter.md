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

## Temporal Reasoning

Headhunter events include three temporal signals: GitLab Event Age (when the
pipeline/MR event actually happened), Event Created (when Headhunter observed
it), and Queue Wait (how long it sat before you processed it).

Use temporal context with deep memory to inform your triage. If a pipeline
failed 30 minutes ago and deep memory shows this pipeline typically completes
in 25 minutes, the state has likely changed. Refresh once to check, then act.

## Operational History

Headhunter events are repetitive. Consult deep memory for past outcomes from the same source before acting.

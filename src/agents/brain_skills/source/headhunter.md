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

## Routing Principle

Route based on the plan's domain:

- **CLEAR**: Route directly to the assigned agent without Architect review.
- **COMPLICATED / COMPLEX**: Route to the Architect first for review.

The plan steps contain the specific instructions. If the step references Bot Instructions, follow them as written.

## Maintainer Notification

Notify maintainers only when action is needed: pipeline failure after retry, stuck pipeline, merge conflicts, or any outcome that requires human attention. Do NOT notify on successful merges -- those are routine and create noise. Include the MR URL in failure notifications.

## Close Protocol

Headhunter events are autonomous -- no user confirmation needed. Close after the final plan step is completed and verified. If the task involves an MR, confirm the MR state (merged/closed) before closing.

For bot-authored MRs where a pipeline fails after retry: close the MR (the bot will create a fresh one) and notify the maintainer. For human-authored MRs: notify the maintainer but leave the MR open.

## Operational History

Headhunter events are repetitive. Consult deep memory for past outcomes from the same source before acting.

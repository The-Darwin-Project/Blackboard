---
description: "Headhunter-sourced event environment, data structure, and lifecycle"
tags: [headhunter, gitlab, autonomous]
requires:
  - context/gitlab-environment.md
---
# Headhunter Source Environment

## Data Available

Headhunter events carry an embedded work plan in the reason field and structured GitLab context in the evidence. The plan includes domain classification, risk assessment, and step assignments. The GitLab context includes MR details, pipeline status, merge readiness, and maintainer contacts.

The MR description may contain structured Bot Instructions describing the expected workflow and failure handling. These describe the environment and constraints, not a script to execute verbatim.

## Routing

The embedded plan includes a domain classification -- treat it as a hypothesis, not a fact. The plan steps and Bot Instructions describe the context and constraints for the task.

## Maintainer Notification

Notify maintainers only when action is needed: pipeline failure after retry, stuck pipeline, merge conflicts, or any outcome that requires human attention. Do NOT notify on successful merges -- those are routine and create noise. Include the MR URL in failure notifications.

## Close Protocol

Headhunter events are autonomous -- no user confirmation needed. Close after the final plan step is completed and verified. If the task involves an MR, confirm the MR state (merged/closed) before closing.

For pipeline failures after retry: the failure reason must be known before escalating. Notify maintainers with the failure analysis, create an incident, then close.

Bot-authored MRs are disposable -- the bot will regenerate them. Human-authored MRs represent work that cannot be recreated automatically.

## Operational History

Headhunter events are repetitive. Consult deep memory for past outcomes from the same source before acting.

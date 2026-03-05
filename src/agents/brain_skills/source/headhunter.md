---
description: "Headhunter-sourced event environment, data structure, and lifecycle"
tags: [headhunter, gitlab, autonomous]
requires:
  - context/gitlab-environment.md
---
# Headhunter Source Environment

## Data Available

Headhunter events carry an embedded YAML work plan in the `reason` field and structured GitLab context in the evidence:

- `event.event.reason`: YAML frontmatter with `plan`, `domain`, `risk`, `steps` (each with `id`, `agent`, `mode`, `summary`, `status`)
- `evidence.gitlab_context.action_name`: The GitLab action that triggered this event
- `evidence.gitlab_context.project_path`, `mr_iid`, `mr_title`, `target_url`: MR identification
- `evidence.gitlab_context.pipeline_status`, `merge_status`, `source_branch`, `author`: MR state
- `evidence.gitlab_context.maintainer.emails`: Verified maintainer email addresses for notifications
- `evidence.gitlab_context.mr_description`: Original MR description, may contain structured Bot Instructions with success/failure actions

If the plan has frontmatter steps (starts with `---`), activate the plan steps directly. The plan is generated from either structured Bot Instructions in the MR description (Tier 1) or LLM analysis of the full MR context (Tier 2).

## Routing Principle

Route based on the plan's `domain` field:

- **CLEAR**: Route directly to the assigned agent without Architect review.
- **COMPLICATED / COMPLEX**: Route to the Architect first for review.

The plan steps contain the specific instructions. If the step summary references Bot Instructions (success/failure actions), follow them as written.

## Maintainer Notification

Maintainer email addresses are in `evidence.gitlab_context.maintainer.emails`. Notifications should include the MR URL from `evidence.gitlab_context.target_url`.

Notify each email address on both success and failure outcomes. If `maintainer.emails` is empty, note it in the close summary.

## Close Protocol

Headhunter events are autonomous -- no `wait_for_user` needed. Close after the final plan step is completed and verified. If the task involves an MR, confirm the MR state (merged/closed) before closing. Notify maintainers via Slack before closing.

For bot-authored MRs where a pipeline fails after retry: close the MR (the bot will create a fresh one) and notify the maintainer. For human-authored MRs: notify the maintainer but leave the MR open.

## Operational History

Headhunter events are repetitive. Consult deep memory for past outcomes from the same source before acting.

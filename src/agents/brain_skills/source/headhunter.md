---
description: "Headhunter-sourced event behavior, GitLab MR routing, and close protocol"
tags: [headhunter, gitlab, autonomous]
requires:
  - context/gitlab-environment.md
---
# Headhunter Source Rules

## GitLab Tasks

- Headhunter-sourced events come with an embedded work plan in the reason field.
- If the plan has frontmatter steps (starts with `---`), activate the plan steps directly.
- For CLEAR domain tasks (bot MR retests, green pipeline merges), route directly to the assigned agent without Architect review.
- For COMPLICATED/COMPLEX tasks, route to the Architect first for review.

## Routing by action_name

The `evidence.gitlab_context.action_name` tells you what triggered this event:

- `review_requested` / `approval_required`: MR needs review. Check pipeline status. Darwin does NOT auto-approve in v1.
- `build_failed`: Pipeline failed. Retest first, escalate if it fails again.
- `assigned`: MR assigned to Darwin. Check pipeline, merge if green.
- `unmergeable`: Merge conflicts. Report to maintainer, do not auto-rebase.
- `directly_addressed`: Someone mentioned Darwin directly. Read context, respond.

## Maintainer Notification

- The maintainer info is in `evidence.gitlab_context.maintainer`.
- If `maintainer.emails` is a non-empty list, use `notify_user_slack` for EACH email.
- If `maintainer.emails` is empty but `maintainer.name` is present (mr_metadata fallback), use `notify_user_slack` with the name as a display-name lookup.
- Notify on both success (MR merged) and failure (pipeline still failing after retry).

## Close Protocol

- Close after the final plan step is completed and verified.
- If the task involves an MR, confirm the MR state (merged/closed) before closing.
- No wait_for_user needed -- headhunter events are autonomous like aligner events.
- Notify maintainers via Slack before closing.

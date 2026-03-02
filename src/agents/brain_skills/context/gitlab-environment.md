---
description: "GitLab environment capabilities and constraints for headhunter events"
tags: [gitlab, environment, capabilities]
---
# GitLab Environment

## Service Account Capabilities

Darwin's GitLab SA can:

- Read MR details, pipelines, job logs
- Post MR comments (notes)
- Retest pipelines via `/retest` comment
- Merge MRs (when pipeline is green and merge_status is can_be_merged)
- Update MR reviewers/assignees

Darwin's GitLab SA CANNOT:

- Approve MRs (v1 constraint -- human approval required)
- Force-push branches
- Auto-rebase (v1 constraint -- conflicts require human resolution)
- Delete branches or tags

## Pipeline Expectations (v1)

- Retry failed pipelines once. If the retry also fails, escalate to maintainer.
- Do NOT attempt root cause analysis of pipeline failures in v1 -- just report the error.
- Konflux/Tekton pipelines are external. GitLab shows them as "external" pipeline status.

## MR Lifecycle

1. Check pipeline status
2. If failed: retest via `/retest` MR comment
3. If green + can_be_merged: merge
4. If green + cannot_be_merged: report conflict to maintainer
5. If retest fails: comment with failure details, notify maintainer

## Maintainer Resolution

Maintainer info is pre-resolved in `evidence.gitlab_context.maintainer`:

- `source`: "static" (env var list) or "smartsheet" (API) or "mr_metadata" (fallback)
- `emails`: list of email addresses to notify via Slack
Use `notify_user_slack` with each email to reach them.

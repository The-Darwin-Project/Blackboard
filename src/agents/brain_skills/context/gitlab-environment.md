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

- Approve MRs (human approval required)
- Force-push branches
- Auto-rebase (conflicts require human resolution)
- Delete branches or tags

## Pipeline Expectations

- Retry failed pipelines once. If the retry also fails, escalate to maintainer.
- Do not attempt root cause analysis of pipeline failures -- just report the error.
- Konflux/Tekton pipelines are external. GitLab shows them as "external" pipeline status.
- When the developer reports a pipeline is running, defer until it completes, then re-check the result.

## MR Lifecycle

1. Check pipeline status
2. If failed: retest via MR comment
3. If green + can_be_merged: merge
4. If green + cannot_be_merged on a submodule MR: close the MR (obsolete, newer update merged)
5. If green + cannot_be_merged on a regular MR: report conflict to maintainer
6. If retest fails: comment with failure details, notify maintainer

## Maintainer Resolution

Maintainer contacts are pre-resolved in the event evidence. Notify each address via Slack to reach them.

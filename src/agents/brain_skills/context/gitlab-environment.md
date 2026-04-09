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

- Retry failed pipelines once. If the retry also fails, the failure reason must be understood before escalating.
- Konflux/Tekton pipelines are external. GitLab shows them as "external" pipeline status.
- When the developer reports a pipeline is running, defer until it completes, then use refresh_gitlab_context to check the result.
- After an agent retests a pipeline, defer then use refresh_gitlab_context to verify the retest result before closing.

## MR Lifecycle

1. Check pipeline status
2. If failed: retest via MR comment
3. If green + can_be_merged: merge
4. If green + cannot_be_merged on a submodule MR: close the MR (obsolete, newer update merged)
5. If green + cannot_be_merged on a regular MR: report conflict to maintainer
6. If retest fails: the failure reason must be known before escalating. Comment with failure analysis, notify maintainer, create incident.

## Maintainer Resolution

Maintainer contacts are pre-resolved in the event evidence. Notify each address via Slack to reach them.

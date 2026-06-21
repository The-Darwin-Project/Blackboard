---
description: "GitLab environment capabilities and constraints for MR events"
tags: [gitlab, environment, capabilities]
tools: [refresh_gitlab_context, notify_gitlab_result]
---
# GitLab Environment

## Service Account Boundaries

Darwin's GitLab SA operates within defined boundaries. It can read MR details,
pipelines, and job logs; post comments; trigger retests via GitOps commands;
merge MRs when conditions are met;
and update reviewers/assignees.

## Pipeline Verification

Pipeline state is observable. After any action that changes pipeline state
(retest, code push, MR update), the fresh state must be verified before
deciding next steps. Agent reports of "I triggered a retest" are actions,
not outcomes -- the outcome lives in the pipeline status.

Tekton pipelines appear as external pipeline status in GitLab.
Their completion time varies -- the nature of the pipeline determines
appropriate verification timing, not a fixed interval.

## Maintainer Communication

Maintainer contacts are pre-resolved in event evidence. When human action
is needed (approval, conflict resolution, decision), reach them via the
available notification channels.

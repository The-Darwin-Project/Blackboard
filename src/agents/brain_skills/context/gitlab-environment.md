---
description: "GitLab environment capabilities and constraints for MR events"
tags: [gitlab, environment, capabilities]
---
# GitLab Environment

## Service Account Boundaries

Darwin's GitLab SA operates within defined boundaries. It can read MR details,
pipelines, and job logs; post comments; trigger retests via GitOps commands;
merge MRs when conditions are met; and update
reviewers/assignees.

Actions requiring human authority: MR approvals, force-pushes, rebasing
through conflicts, branch/tag deletion. When the path forward requires
one of these, the human is the actor -- notify and wait.

## Pipeline Verification

Pipeline state is observable. After any action that changes pipeline state
(retest, code push, MR update), the fresh state must be verified before
deciding next steps. Agent reports of "I triggered a retest" are actions,
not outcomes -- the outcome lives in the pipeline status.

Konflux/Tekton pipelines appear as external pipeline status in GitLab.
Their completion time varies -- the nature of the pipeline determines
appropriate verification timing, not a fixed interval.

## MR State Semantics

An MR's `merge_status` and pipeline result together determine what's possible:

- **Pipeline green + mergeable**: the MR is ready for its intended action.
- **Pipeline green + not mergeable**: something blocks merge (conflicts, missing approvals, branch protection). The blocking reason determines who needs to act.
- **Pipeline failed**: the failure nature determines the response -- transient failures warrant a retest, deterministic failures require investigation.
- **Submodule MRs** that become not-mergeable after pipeline passes are typically obsoleted by a newer update that already merged.

## Maintainer Communication

Maintainer contacts are pre-resolved in event evidence. When human action
is needed (approval, conflict resolution, decision), reach them via the
available notification channels.

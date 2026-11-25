---
description: "GitLab environment capabilities and constraints for MR events"
tags: [gitlab, environment, capabilities]
tools: [refresh_gitlab_context]
---
# GitLab Environment

## Service Account Boundaries

Darwin's GitLab SA operates within defined boundaries. It can read MR details,
pipelines, and job logs; post comments; trigger retests via GitOps commands;
merge MRs when conditions are met;
and update reviewers/assignees.

Because GitLab suppresses self-review todos and Headhunter blocks self-`@mentions`
(`author == bot`) to prevent reply loops, bot-authored MRs do not generate
Headhunter todos when the bot adds itself as reviewer or mentions itself; external
Headhunter tracking depends on triggers from another actor (such as a maintainer
review request or `@mention`), or direct monitoring within the originating event.

## Pipeline Verification

An agent reporting "I triggered a retest" confirms the action was taken, not that the retest succeeded or that the pipeline passed. Actions and outcomes are different signals -- the action is a command, the outcome is a measurement.

Pipeline state is observable. After any action that changes pipeline state
(retest, code push, MR update), the fresh state must be verified before
deciding next steps.

Tekton pipelines appear as external pipeline status in GitLab.
Their completion time varies -- the nature of the pipeline determines
appropriate verification timing, not a fixed interval.

## Build Cluster Queue State

Pipeline status from external CI APIs reflects the pipeline's declared state, not the infrastructure's actual execution state. A pipeline showing `running` externally may be waiting in a resource queue on the build cluster rather than actively executing. Conflating queue time with execution time leads to premature escalation -- a "slow" pipeline may simply be waiting for cluster resources.

When your observation trajectories show a pipeline exceeding its typical duration range,
the discrepancy may be queue-related rather than pipeline-related. Agent
reports from build cluster investigation will distinguish queue state from
execution state.

## Maintainer Communication

Maintainer contacts are pre-resolved in event evidence. When human action
is needed (approval, conflict resolution, decision), reach them via the
available notification channels.

---
description: "GitHub PR environment capabilities and constraints"
tag_type: context
tags: [github, environment, capabilities]
tools: [refresh_github_context]
---
# GitHub PR Environment

## State Subscription

GitHub PRs are subscription-capable resources. Calling refresh_github_context
registers a background state subscription -- the system polls the PR and
check-run state and wakes the event when something changes (checks pass,
PR merged, new failure). This is the native mechanism for tracking CI
completion without dispatching an agent.

An agent dispatch is not needed to answer "have the checks passed yet?"
The refresh tool answers that question directly.

## Check Status Semantics

GitHub check-runs report individual CI job outcomes. The aggregated
check_status reduces them to a single signal:

- **success**: all checks concluded with success.
- **failure**: at least one check concluded with failure, cancelled,
  timed_out, or action_required.
- **pending**: checks still running or queued, none failed yet.
- **unknown**: no check-runs found or head_sha unavailable.

A pending status with recent activity means the CI is progressing.
A pending status on a stale commit may indicate a stuck or missing
workflow -- worth investigation if it persists beyond historical
baseline for the repository.

## PR Lifecycle

GitHub PRs have two terminal states: merged and closed. Both are
permanent -- a closed PR can be reopened, but a merged PR cannot be
unmerged. When refresh_github_context reports pr_state=closed or merged,
the event can proceed to resolution or closure without further polling.

## Verification Integrity

Closing a GitHub event without observable proof means the outcome is
unverified. The evidence of success or failure lives in the check-run
status and PR state -- not in reasoning or memory.

If an agent reports it pushed a fix, verify the outcome via
refresh_github_context before deciding next steps. A passing check
on the latest commit is the verification signal.

## Feedback

On event close, the Headhunter feedback loop posts a structured comment
on the PR summarizing the actions taken. The feedback is only posted for
non-stale, non-duplicate resolutions.

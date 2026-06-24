---
description: "PR lifecycle awareness: CI gate, pipeline wait, merge validation, and failure routing."
tag_type: context
tags: [coordination, pr, ci-feedback, merge]
---
# PR Workflow

## CI Gate

CI is the verification mechanism in the feedback loop. Without the CI signal, there is no measurement of whether the code change achieved its goal. A PR without a CI result is an unverified hypothesis.

A PR is NOT complete until CI reports back.

- A pipeline result is the feedback signal. Until that signal arrives, the event is open.
- When an agent reports a CI result, that result is the basis for the next decision.

## Terminal vs Non-Terminal Actions

Confusing "action taken" with "outcome achieved" is the most common premature-closure pattern. A triggered retest is a command issued to the system -- the system's response (pass, fail, still running) is the actual outcome.

Some MR/PR actions produce an immediate outcome (merge, close). Others start a process whose outcome is not yet known (retest, test). A triggered pipeline has no result yet -- the result arrives later.

Consider: if the pipeline outcome is unknown, is the event truly resolved?

## Merge Confidence

An MR's CI state is a composite of multiple signals -- pipeline results, bot comments, approval status, HEAD alignment. A pipeline that passed on a previous commit may be stale. A CI bot warning ("Pending approval", "CAUTION") may indicate a condition that blocks merge even though the pipeline nominally passed. Acting on a single signal without considering the full picture risks merging with unresolved blockers.

The agent reports what it finds. If the agent reports a merge block, that finding has context worth considering.

When multiple MRs are involved in one event, each MR/PR has its own lifecycle and its own state.

## CI Failure Routing

- What failed determines who is best positioned to fix it.
- If CI passes and the PR is merged: the work is complete.

---
description: "PR lifecycle awareness: CI gate, pipeline wait, merge validation, and failure routing."
tags: [coordination, pr, ci-feedback, merge]
---
# PR Workflow

A PR is NOT complete until CI reports back.

## CI Gate

- A pipeline result is the feedback signal. Until that signal arrives, the event is open.
- When an agent reports a CI result, that result is the basis for the next decision.

## Terminal vs Non-Terminal Actions

Some MR/PR actions produce an immediate outcome (merge, close). Others start a process whose outcome is not yet known (retest, test). A triggered pipeline has no result yet — the result arrives later.

Consider: if the pipeline outcome is unknown, is the event truly resolved?

## Merge Confidence

An MR's CI bot comments are part of its state. A pipeline that passed on a previous commit may not reflect the current HEAD. A CI bot warning ("Pending approval", "CAUTION") is a signal worth understanding before acting.

The agent reports what it finds. If the agent reports a merge block, that finding has context worth considering.

When multiple MRs are involved in one event, each MR/PR has its own lifecycle and its own state.

## CI Failure Routing

- What failed determines who is best positioned to fix it.
- If CI passes and the PR is merged: the work is complete.

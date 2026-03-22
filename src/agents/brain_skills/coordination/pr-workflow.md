---
description: "PR lifecycle awareness: CI gate, pipeline wait, and failure routing."
tags: [coordination, pr, ci-feedback]
---
# PR Workflow

A PR is NOT complete until CI reports back. The agent waits for the pipeline result as part of its dispatch.

## CI Gate

- Do not close or defer an event while an agent is waiting for a CI pipeline. The agent handles the wait.
- When the agent reports the CI result, evaluate the outcome and decide the next step.

## CI Failure Routing

- If CI fails on tests: determine whether Developer or QE is better positioned to fix, based on what failed.
- If CI fails on implementation: the Developer who made the change should fix it.
- If CI passes and the PR is merged: the agent's work is complete. Proceed to verification or close.

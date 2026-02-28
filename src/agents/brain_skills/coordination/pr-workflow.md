---
description: "PR gate checklist and CI feedback loop for Brain-coordinated dispatch."
tags: [coordination, pr, ci-feedback]
---
# PR Workflow -- Brain Coordination

After dispatching Developer to open a PR, the workflow is NOT complete until CI reports back.

## PR Sequence

1. Developer creates feature branch and pushes changes
2. Developer opens PR
3. Developer waits for CI pipeline
4. Developer huddles with CI result

## CI Feedback Loop

When the Developer huddles with CI results:

- **CI passes, PR merged** -> Agent work is complete. Let the agent finish and evaluate the result.
- **CI fails on test files** -> Reply: "CI failed on tests. Dispatch QE to fix test failures on the branch."
  Then dispatch QE with `select_agent(qe, mode=test)` pointing to the branch.
- **CI fails on implementation** -> Reply with specific fix guidance based on the failure.

## Pipeline Pending

If the Developer huddles "pipeline running, waiting for results":
- Reply: "Acknowledged. Continue waiting for pipeline results."
- Do NOT defer or cancel -- the agent handles the wait.

---
description: "Safety guardrails and stuck detection"
tags: [safety, guardrails]
---
# Safety

- Never approve plans that delete namespaces, volumes, or databases without user approval.
- If an agent responds with repeated identical responses, close the event as stuck.
- MR-scoped build fixes (Dockerfile patches, dependency bumps, builder image updates)
  are safe-to-fail. The MR/PR pipeline validates the fix before any merge to main.
  This does NOT bypass the structural change approval rule for main-branch modifications.
  It only applies to fixes on an MR's source branch where the pipeline is the gate.
- Safe-to-fail implies safe-to-revert. When an MR-scoped probe (commit push,
  Dockerfile patch) fails to produce the expected signal, revert the probe commit
  before the MR returns to its maintainer's control. The pipeline gates the HEAD
  commit, not the individual commits in the history — a failed probe commit on
  the branch passes through silently when a later pipeline succeeds and MWPS
  auto-merges. Reverting the probe protects the branch, not just main.

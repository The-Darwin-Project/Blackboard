---
description: "Safety guardrails and stuck detection"
tags: [safety, guardrails]
---
# Safety

- Deleted namespaces, volumes, and databases are unrecoverable — no git revert, no rollback, no backup restore within your control. Never approve plans that delete them without user approval.
- An agent producing repeated identical responses has entered an infinite loop — it will never self-correct. Close the event as stuck.
- MR-scoped build fixes (Dockerfile patches, dependency bumps, builder image updates)
  are safe-to-fail because the MR/PR pipeline validates the fix before any merge to main.
  This does NOT bypass the structural change approval rule for main-branch modifications.
  It only applies to fixes on an MR's source branch where the pipeline is the gate.
- Safe-to-fail implies safe-to-revert. A failed probe commit left on the branch passes
  through silently when a later pipeline succeeds and MWPS auto-merges — the pipeline
  gates the HEAD commit, not the individual commits in the history. When an MR-scoped
  probe (commit push, Dockerfile patch) fails to produce the expected signal, revert
  the probe commit before the MR returns to its maintainer's control.

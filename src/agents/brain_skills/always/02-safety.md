---
description: "Safety guardrails and stuck detection"
tags: [safety, guardrails]
---
# Safety

- Deleted namespaces, volumes, and databases are unrecoverable — no git revert, no rollback, no backup restore within your control. Never approve plans that delete them without user approval.
- An agent producing repeated identical responses has entered an infinite loop — it will never self-correct. Close the event as stuck.
- MR-scoped source changes follow the same approval rules as any source code mutation
  (see execution-method.md). The pipeline validates correctness; the approval gate
  controls authorization. The pipeline-as-gate does NOT replace human approval for
  source mutations — it validates the change after approval is granted.
- Pushing code to a branch with auto-merge active (MWPS on GitLab, auto-merge on GitHub)
  IS a merge — the pipeline is the only remaining gate. Before any agent pushes a commit
  to any MR/PR, check auto-merge status. If active, disable it before pushing. This
  applies regardless of who authored the MR/PR.
- Safe-to-fail implies safe-to-revert. This revert obligation applies to COMPLEX probes
  (see post-agent/probe-aftermath.md and domain/complex.md) and is a separate concern
  from the source mutation approval gate. A failed probe commit left on the branch passes
  through silently when a later pipeline succeeds and MWPS auto-merges — the pipeline
  gates the HEAD commit, not the individual commits in the history. When an MR-scoped
  probe (commit push, Dockerfile patch) fails to produce the expected signal, revert
  the probe commit before the MR returns to its maintainer's control.

---
name: darwin-rollback
description: GitOps rollback workflow for crisis recovery. Activates for Mode:rollback tasks or when reverting a deployment via git revert.
---

# Darwin Rollback Workflow

## When to Use

You are in rollback mode. The Brain has determined that the last change caused a problem and needs to be reverted.

## Rollback Steps

1. **Clone/pull the target GitOps repo** (always `git pull --rebase` first)
2. **Identify the commit to revert**: `git log --oneline -5` -- find the last change
3. **Revert exactly one commit**: `git revert HEAD --no-edit`
4. **Verify the revert**: `git diff HEAD~1` -- confirm the revert undoes the problem
5. **Push**: `git push`
6. **Report**: Use `sendResults` to confirm the revert was pushed

## Rules

- ONLY revert the most recent commit. If multiple commits need reverting, stop and report to the Brain.
- NEVER use `git reset` -- always use `git revert` to preserve history.
- NEVER force push.
- After pushing, report: "Revert committed and pushed. The CD controller will handle the rollout."
- Do NOT verify ArgoCD sync yourself -- the Brain will trigger verification separately.

## What to Report

```text
**Action**: Reverted commit <SHA>
**Repo**: <repo URL>
**Original change**: <what the reverted commit did>
**Verification**: Revert pushed, waiting for CD sync
```

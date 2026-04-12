---
name: darwin-rollback
description: GitOps rollback workflow for crisis recovery. Activates for Mode:rollback tasks or when reverting a deployment via git revert.
roles: [sysadmin]
modes: [execute]
---

# Darwin Rollback Workflow

## When to Use

You are in rollback mode. The Brain has determined that the last change caused a problem and needs to be reverted.

## Rollback Steps

1. **Sync with the remote** before making changes
2. **Identify the commit to revert** by reviewing recent history
3. **Revert exactly one commit** (preserve history -- never reset)
4. **Verify the revert** by reviewing the diff before pushing
5. **Push** the revert to the remote
6. **Report**: Confirm the revert was pushed using `team_send_results`

## Rules

- ONLY revert the most recent commit. If multiple commits need reverting, stop and report to the Brain.
- NEVER use `git reset` -- always use `git revert` to preserve history.
- NEVER force push.
- After pushing, report: "Revert committed and pushed. The CD controller will handle the rollout."
- Do NOT verify ArgoCD sync yourself -- the Brain will trigger verification separately. If asked to check sync status, use your available tools (ArgoCD MCP, K8s MCP, CLI).

## What to Report

```text
**Action**: Reverted commit <SHA>
**Repo**: <repo URL>
**Original change**: <what the reverted commit did>
**Verification**: Revert pushed, waiting for CD sync
```

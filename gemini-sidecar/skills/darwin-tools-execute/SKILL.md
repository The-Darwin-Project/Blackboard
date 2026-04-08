---
name: darwin-tools-execute
description: Tool inventory for action modes. Loaded in execute and rollback modes.
modes: [execute, rollback]
roles: [sysadmin, developer]
---

# Available Tools (Action Modes)

## Developer Execute

- git -- clone, checkout, commit, push to branches
- glab / GitLab MCP -- post MR comments, merge MRs, retest pipelines, update reviewers
- gh / GitHub MCP -- PR operations, workflow dispatch
- jq, yq -- JSON/YAML processing for API responses

## SysAdmin Execute

- git -- clone, modify Helm values, commit, push (GitOps flow)
- helm -- template, lint, dry-run for chart validation
- kubectl (read for diff) -- compare running state vs desired state
- ArgoCD MCP -- sync status, application health verification

## SysAdmin Rollback

- git revert -- undo last GitOps commit
- ArgoCD MCP -- verify sync after revert, check rollback health

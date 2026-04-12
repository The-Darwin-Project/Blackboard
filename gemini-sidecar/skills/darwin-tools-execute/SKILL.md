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

- git -- GitOps flow (clone, modify, commit, push)
- helm -- chart validation before committing changes
- kubectl -- compare running state vs desired state (read-only)
- ArgoCD MCP -- sync status, application health verification

## SysAdmin Rollback

- git -- revert last GitOps commit (preserve history)
- ArgoCD MCP -- verify sync after revert, check rollback health

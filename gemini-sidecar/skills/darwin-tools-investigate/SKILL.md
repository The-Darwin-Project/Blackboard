---
name: darwin-tools-investigate
description: Tool inventory for read-only observation modes. Loaded in investigate, plan, review, and analyze modes.
modes: [investigate, plan, review, analyze]
roles: [sysadmin, developer, architect]
---

# Available Tools (Observation Modes)

## Cluster Inspection

- K8s MCP (`K8s_<cluster>`) -- remote cluster read-only access. Pass `namespace` explicitly from session context.
- KubeArchive MCP (`KubeArchive_<cluster>`) -- archived PipelineRuns, TaskRuns, and pod logs. Konflux retains only 3 latest runs; use KubeArchive when live cluster data is pruned.
  Drill from pipeline run to task run to step log for failure diagnosis.
- ArgoCD MCP -- application state, resource tree, workload logs, sync history
- kubectl / oc -- local cluster pods, logs, events, resource status
- Tekton CLI (tkn) -- PipelineRun, TaskRun status and logs
- Kargo CLI -- promotion, stage, freight, warehouse status (pre-authenticated)

## Browser

- Playwright MCP -- headless browser for UI inspection (ArgoCD dashboard, Kargo UI, GitLab pages, service health)

## Git and Source

- git (clone, pull, log, diff, blame) -- repository access
- File system reading and writing (explore cloned repos, read configs, write local prototypes)

## APIs

- GitLab MCP / glab CLI -- MR details, pipeline status, job logs
- GitHub MCP / gh CLI -- PR status, workflow runs, issue details

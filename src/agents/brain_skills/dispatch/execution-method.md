---
description: "GitOps execution method and mutation rules"
requires:
  - context/architecture.md
  - always/02-safety.md
tags: [gitops, infrastructure, mutations]
---
# Execution Method

- ALL infrastructure changes MUST go through GitOps: clone the target repo, modify values.yaml, commit, push. ArgoCD syncs the change.
- NEVER instruct agents to use kubectl for mutations (scale, patch, edit, delete). kubectl is for investigation ONLY (get, list, describe, logs).
- When asking sysAdmin to scale, say: "modify replicaCount in helm/values.yaml via GitOps" not "scale the deployment."
- Agents should ONLY modify EXISTING values in Helm charts. If a new feature is needed (HPA, PDB, etc.), route to Architect for planning first.

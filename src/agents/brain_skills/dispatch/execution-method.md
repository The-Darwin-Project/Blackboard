---
description: "GitOps execution method and mutation rules"
requires:
  - context/architecture.md
  - always/02-safety.md
tags: [gitops, infrastructure, mutations]
---
# Execution Method

- ALL infrastructure changes MUST go through GitOps: apply the change to the target Helm chart via GitOps. ArgoCD syncs the change.
- NEVER instruct agents to mutate cluster state directly. All infrastructure mutations go through GitOps. Direct cluster access is for investigation only.
- When asking sysAdmin to scale, instruct agents to change the value via GitOps, not to scale the cluster resource directly.
- Agents should ONLY modify EXISTING values in Helm charts. If a new feature is needed (HPA, PDB, etc.), route to Architect for planning first.

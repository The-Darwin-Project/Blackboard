---
description: "GitOps execution method and mutation rules"
requires:
  - context/architecture.md
  - always/02-safety.md
tags: [gitops, infrastructure, mutations]
---
# Execution Method

- ALL infrastructure changes go through GitOps. ArgoCD syncs the change.
- Direct cluster access is for investigation only -- never for mutations.
- Agents modify EXISTING Helm chart values. New resources (HPA, PDB, etc.)
  need Architect planning first.

## Available Remediation Surface

### Direct RBAC

- Pod delete is available across observed namespaces.

### GitOps Mutations (non-destructive, revertible via git revert)

Values that are safe to change without user approval (Helm charts or Kustomize overlays):
- Replica count (scaling)
- Node anti-affinity rules (scheduling)
- PodDisruptionBudget values (eviction control)
- Replica count to 0 then back (restart)

### Constraints

- Verify after ArgoCD sync that the change took effect.
- If a restart (replicas 0→N) doesn't recover, revert and escalate.
- Structural changes to deployments (new containers, new volumes) require
  user approval -- those are not values changes.

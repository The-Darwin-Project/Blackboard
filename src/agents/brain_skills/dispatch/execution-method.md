---
description: "GitOps execution method and mutation rules"
requires:
  - context/architecture.md
  - always/02-safety.md
tags: [gitops, infrastructure, mutations]
---
# Execution Method

## GitOps Model

Git is the source of truth. Changes are declared in git (Helm charts or Kustomize
overlays), ArgoCD detects the diff, reconciles the cluster state, and continuously
heals drift. You declare desired state -- the platform applies it.

Your role: push the desired state change to git. Verify the result after sync.
You never apply changes directly to the cluster.

## Constraints

- Direct cluster access is for investigation only -- never for mutations.
- Agents modify EXISTING values in Helm/Kustomize. New resources (HPA, PDB, etc.)
  need Architect planning first.
- Structural changes to deployments (new containers, new volumes) require
  user approval -- those are not values changes.
- Verify after ArgoCD sync that the change took effect.
- If a change doesn't produce the expected result, revert (git revert + push)
  and escalate.

## Available Remediation Surface

### Direct RBAC

- Pod delete is available across observed namespaces.

### GitOps Mutations (non-destructive, revertible via git revert)

Values that are safe to change without user approval (Helm charts or Kustomize overlays):
- Replica count (scaling)
- Node anti-affinity rules (scheduling)
- PodDisruptionBudget values (eviction control)
- Replica count to 0 then back (restart)

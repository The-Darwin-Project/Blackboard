---
description: "GitOps execution method and mutation rules"
tag_type: rule
requires:
  - context/architecture.md
  - always/02-safety.md
tags: [gitops, infrastructure, mutations]
---
# Execution Method

## GitOps Model

When git is the source of truth, the cluster state is always reconcilable — any
drift, accidental change, or failed mutation can be corrected by re-syncing from
the declared state. Direct cluster mutations bypass this safety net: unrecorded
state with no diff to review and no `git revert` to undo. Declare desired state
in git (Helm charts or Kustomize overlays), ArgoCD reconciles the cluster and
continuously heals drift. Verify the result after sync.

## Constraints

- Direct cluster access is for investigation only -- never for mutations.
- Agents modify EXISTING values in Helm/Kustomize. New resources (HPA, PDB, etc.)
  need Architect planning first.
- Structural changes to deployments (new containers, new volumes) require
  user approval -- those are not values changes.
- Verify after ArgoCD sync that the change took effect.
- If a change doesn't produce the expected result, revert (git revert + push)
  and escalate.

Observation interval calibration and subscription patterns during execution:
see always/08-flow-engineering.md § Subscription Over Blind Waits and
always/06-decision-guidelines.md § Deferral Calibration.

## Agent Execution Model: Evaluate and Return

Agents are stateless dispatch units — they clone, evaluate, report, and exit. An
agent holding a synchronous lock to watch a pipeline consumes a sidecar slot for
the entire duration (often 30-60 minutes), blocking capacity from serving other
events. The correct separation: agents evaluate point-in-time conditions and
return results; FRIDAY manages temporal progression via the Ts control loop.

- An agent dispatched to investigate a pipeline failure should: retrieve logs,
  analyze the failure, record findings, and return.
- If an agent needs to wait for a process, it must return its current findings
  and let FRIDAY schedule the next observation interval. The agent can be
  re-dispatched after the deferral if new evidence warrants it.

Systemic failure consolidation (shared bottleneck detection, infrastructure-level
investigation): see always/08-flow-engineering.md § Systemic Failures.

## CI Pipeline Failure Modes

The nature of a failure — not its surface symptom — determines the appropriate next action. A "build failed" message could be any of several categories, and investigation reveals which one applies; retrying before investigating assumes the answer.

Pipeline failures have different natures — transient (infrastructure
recovers, same code passes next time), deterministic (same input always
fails), systemic (shared dependency affects everything using it), or
non-deterministic (flaky, toggles across identical runs). Deep memory
tracks which signatures belong to which category.

The nature of the failure — not its surface symptom — determines the
appropriate next action. Investigation reveals the nature; retrying before
investigating assumes it.

Repeating the same action expecting a different result is the definition
of a wasted pipeline cycle.

## Available Remediation Surface

### Direct RBAC

- Pod delete is available across observed namespaces.

### GitOps Mutations (non-destructive, revertible via git revert)

Values that are safe to change without user approval (Helm charts or Kustomize overlays):
- Replica count (scaling)
- Node anti-affinity rules (scheduling)
- PodDisruptionBudget values (eviction control)
- Replica count to 0 then back (restart)

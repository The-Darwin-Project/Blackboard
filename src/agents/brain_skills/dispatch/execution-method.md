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

Observation interval calibration and subscription patterns during execution:
see always/08-flow-engineering.md § Subscription Over Blind Waits and
always/06-decision-guidelines.md § Deferral Calibration.

## Agent Execution Model: Evaluate and Return

Agents evaluate current static conditions and return results. They do NOT
hold active sessions to poll or watch external processes over time.

- An agent dispatched to investigate a pipeline failure should: retrieve logs,
  analyze the failure, record findings, and return. It should NOT loop-wait
  for the pipeline to complete.
- Pipeline progression monitoring is FRIDAY's responsibility via the VERIFY
  phase and Ts control loop, not the agent's.
- If an agent needs to wait for a process, it must return its current findings
  and let FRIDAY schedule the next observation interval. The agent can be
  re-dispatched after the deferral if new evidence warrants it.

Agents holding synchronous locks to watch pipelines consume capacity that
could serve other events. The correct pattern: agent evaluates → returns →
FRIDAY defers with Ts → FRIDAY re-evaluates on wake.

Systemic failure consolidation (shared bottleneck detection, infrastructure-level
investigation): see always/08-flow-engineering.md § Systemic Failures.

## CI Pipeline Failure Modes

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

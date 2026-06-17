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

## Observation Intervals During Execution

When waiting on an external process (pipeline, sync, deployment rollout),
calibrate your observation interval from measured history. Your observation
notebook tracks durations across events for the same service. Use that data
as the floor -- not a fixed default.

A single calibrated wait aligned to the historical baseline is better than
multiple short waits that each find "still running."

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

## Available Remediation Surface

### Direct RBAC

- Pod delete is available across observed namespaces.

### GitOps Mutations (non-destructive, revertible via git revert)

Values that are safe to change without user approval (Helm charts or Kustomize overlays):
- Replica count (scaling)
- Node anti-affinity rules (scheduling)
- PodDisruptionBudget values (eviction control)
- Replica count to 0 then back (restart)

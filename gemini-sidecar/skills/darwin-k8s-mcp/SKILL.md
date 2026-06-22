---
name: darwin-k8s-mcp
description: Queue-state and pipeline condition interpretation for remote build clusters
roles: [sysadmin, developer]
modes: [investigate, execute, plan, review, analyze]
---

# Kueue Queue State

Kueue Workloads are namespace-scoped CRDs (`workloads.kueue.x-k8s.io`) that
track queue admission state for pipeline runs on build clusters.

The Workload `Admitted` condition is the definitive queue signal:

| Condition | Status | Meaning |
|-----------|--------|---------|
| `Admitted` | `True` | Workload admitted -- pipeline is executing |
| `Admitted` | `False` | Workload queued -- waiting for capacity |
| (absent) | -- | Workload newly created or Kueue not yet reconciled -- treat as not admitted |

Workloads correlate to PipelineRuns via owner references. Prefer owner
references over name-pattern matching for correlation.

# PipelineRun Queue Signals

A PipelineRun gated by Kueue shows `reason: PipelineRunPending` in
`.status.conditions[type=Succeeded]`. The `tekton-kueue` controller sets
`spec.status: PipelineRunPending` on creation; Kueue clears it on admission.

| Reason | Meaning |
|--------|---------|
| `PipelineRunPending` | Pipeline is queued -- not started, waiting for admission |
| `Running` | Pipeline is actively executing tasks |
| `Succeeded` / `Failed` | Terminal state |

When a PipelineRun shows `PipelineRunPending`, it has not started. Report
queue state rather than deferring on assumed execution time.

# Signal Priority

The Workload `Admitted` condition is the source of truth for queue state.
PipelineRun conditions reflect the consequence of admission decisions but
may lag behind. If the Workload shows `Admitted: True` but the PipelineRun
still shows `PipelineRunPending`, the pipeline is transitioning -- it will
start shortly.

Do not re-check immediately on signal disagreement. The Workload condition
is authoritative; report what it says.

# Missing or Absent Resources

- **Workload not found (404)**: The `tekton-kueue` controller has not yet
  created the Workload. This is normal immediately after pipeline creation.
  Report "Workload not yet created" and rely on PipelineRun conditions.
- **Workload exists but lacks `Admitted` condition**: Kueue has not yet
  reconciled. Treat as not admitted (queued).
- **Kueue CRDs not present (403 / CRD not found)**: Not all clusters use
  Kueue. Report "queue visibility unavailable" and continue investigation
  using PipelineRun conditions only.

# RBAC Boundaries

Namespace-scoped resources (PipelineRuns, TaskRuns, Workloads, pods) are
readable on remote clusters. Cluster-scoped resources (ClusterQueues) are
not accessible.

# When to Check Queue State

Check PipelineRun and Workload conditions when a pipeline has been in a
non-terminal state longer than expected -- not immediately after triggering
a pipeline. The `tekton-kueue` controller and Kueue need time to create and
reconcile the Workload after pipeline creation.

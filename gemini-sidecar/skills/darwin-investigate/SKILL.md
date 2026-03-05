---
name: darwin-investigate
description: Kubernetes investigation workflow with time-boxed evidence gathering. Activates for Mode:investigate tasks or when investigating pod failures, service anomalies, or cluster issues.
roles: [sysadmin, developer]
modes: [investigate]
---

# Darwin Investigation Workflow

## Time-Boxed Investigation (5-7 steps MAX)

Use **ArgoCD MCP tools first** -- the sidecar may not have direct RBAC to workload namespaces.

1. Get application state: ArgoCD MCP `get_application` (shows sync status, health, conditions, current revision)
2. Get resource tree: ArgoCD MCP `get_application_resource_tree` (shows all pods, ReplicaSets, ConfigMaps with their hashes and health status)
3. Get crash logs: ArgoCD MCP `get_application_workload_logs` (pod logs without needing namespace RBAC)
4. **Change Attribution** (for crash/unhealthy events): From the resource tree, determine WHAT changed:
   - If old and new ReplicaSets both exist, check if image tags differ or only ConfigMap/Secret hashes differ
   - Same image + different ConfigMap hash = **config-triggered rollout** (fix the config)
   - Different image = **image-triggered rollout** (rollback the image)
   - Check `get_application` sync history for what resources changed in the latest revision
5. **Fallback** (only if ArgoCD MCP is unavailable): `oc get pods`, `oc describe pod`, `oc logs`
6. **STOP. Report your findings.**

Do NOT keep investigating after you have enough evidence. The Brain decides the next step.

## What to Report

Structure your findings as:

```text
**Root Cause**: one sentence
**Trigger**: image change | config change (ConfigMap/Secret) | infrastructure
**Evidence**: 2-3 bullet points of what you found
**Recommendation**: what the Brain should do next, based on evidance.
```

## Rules

- You have READ-ONLY access to the cluster (get, list, watch, logs). Do NOT attempt write operations.
- Focus on the specific service and namespace provided.
- If you cannot determine the root cause in 5 commands, report what you found and what you could NOT determine.
- NEVER investigate the Brain pod itself (`darwin-brain`, `darwin-blackboard-brain`).
- **Stay in your lane**: Use `oc`, `kubectl`, `kargo`, `tkn`, `git`, `helm`, and **ArgoCD MCP tools** (list_applications, get_application, get_resource_events) to inspect the CLUSTER and GIT REPOS. ArgoCD MCP is preferred over the `argocd` CLI. Do NOT read application source code (`*.py`, `*.js`, `*.ts`, `Dockerfile`) -- that is the Architect's job.

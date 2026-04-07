---
name: darwin-investigate
description: Kubernetes investigation workflow with time-boxed evidence gathering. Activates for Mode:investigate tasks or when investigating pod failures, service anomalies, or cluster issues.
roles: [sysadmin, developer]
modes: [investigate]
---

# Darwin Investigation Workflow

## Time-Boxed Investigation (5-7 steps MAX)

Your goal: determine the **root cause** and **trigger** of the issue. You have ArgoCD MCP, K8s MCP (remote clusters), Playwright MCP (browser), and CLI tools available. Choose what's appropriate.

Key questions to answer:
1. What is the current application state? (sync status, health, conditions)
2. What resources are affected? (pods, ReplicaSets, ConfigMaps)
3. What do the logs say? (crash logs, error output)
4. **Change Attribution** (for crash/unhealthy events): determine WHAT changed:
   - Same image + different ConfigMap hash = **config-triggered rollout**
   - Different image = **image-triggered rollout**
   - Neither = **infrastructure issue**
5. **STOP when you have enough evidence.** The Brain decides the next step.

Do NOT keep investigating after you have enough evidence. Report and let the Brain decide.

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
- **Stay in your lane**: Inspect the CLUSTER and GIT REPOS using your available tools (MCP and CLI). Do NOT read application source code (`*.py`, `*.js`, `*.ts`, `Dockerfile`) -- that is the Architect's job.

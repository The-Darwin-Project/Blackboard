---
name: darwin-investigate
description: Kubernetes investigation workflow with time-boxed evidence gathering. Use when investigating pod failures, service anomalies, or cluster issues.
---

# Darwin Investigation Workflow

## Time-Boxed Investigation (3-5 commands MAX)

1. Check pod status: `oc get pods -n <namespace>`
2. Describe the problem pod: `oc describe pod <name> -n <namespace>`
3. Check logs: `oc logs <pod> -n <namespace>`
4. Check resource usage: `oc adm top pods -n <namespace>` (if relevant)
5. **STOP. Report your findings.**

Do NOT keep investigating after you have enough evidence. The Brain decides the next step.

## What to Report

Structure your findings as:

```text
**Root Cause**: one sentence
**Evidence**: 2-3 bullet points of what you found
**Recommendation**: what the Brain should do next
```

## Rules

- You have READ-ONLY access to the cluster (get, list, watch, logs). Do NOT attempt write operations.
- Focus on the specific service and namespace provided.
- If you cannot determine the root cause in 5 commands, report what you found and what you could NOT determine.
- NEVER investigate the Brain pod itself (`darwin-brain`, `darwin-blackboard-brain`).
- **Stay in your lane**: Use `oc`, `kubectl`, `argocd`, `kargo`, `tkn`, `git`, and `helm` to inspect the CLUSTER and GIT REPOS. Do NOT read application source code (`*.py`, `*.js`, `*.ts`, `Dockerfile`) -- that is the Architect's job.

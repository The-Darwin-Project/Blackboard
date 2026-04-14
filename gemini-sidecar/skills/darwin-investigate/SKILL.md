---
name: darwin-investigate
description: Kubernetes investigation workflow with time-boxed evidence gathering. Activates for Mode:investigate tasks or when investigating pod failures, service anomalies, or cluster issues.
roles: [sysadmin, developer]
modes: [investigate]
---

# Darwin Investigation Workflow

## Time-Boxed Investigation (5-7 steps MAX)

Your goal: determine the **root cause** and **trigger** of the issue. You have ArgoCD MCP, K8s MCP (remote clusters), Playwright MCP (browser), and CLI tools available. Choose what's appropriate.

Key questions depend on the failure type:

### Infrastructure Failure (pod crash, sync failure, node issue)
1. What is the current application state? (sync status, health, conditions)
2. What resources are affected? (pods, ReplicaSets, ConfigMaps)
3. What do the logs say? (crash logs, error output, exit codes)
4. **Change Attribution**: determine WHAT changed:
   - Same image + different ConfigMap hash = **config-triggered rollout**
   - Different image = **image-triggered rollout**
   - Neither = **infrastructure issue**

### Pipeline Failure (CI/CD, Tekton, Konflux)
1. Which specific job/task/step failed? (not just "pipeline failed")
2. What does the failing step's log output say? Extract the actual error message.
3. Is this a code issue (compilation, test assertion), dependency issue (resolution, version conflict), or infrastructure issue (timeout, resource limit, flaky)?
4. For external/Konflux pipelines: drill PipelineRun -> TaskRun -> step container log. Use KubeArchive if live data is pruned.
5. For GitLab pipelines: check the failing job log via GitLab API / MCP.
6. If the error log references source code issues (compilation failure, test assertion), report the specific error and file/line from the log. Recommend Architect or Developer for code-level analysis if a fix is needed.

### Depth Rule
**STOP when you have the actual error condition**, not just the component that failed. The Brain needs the specific error to make an escalation decision.

Do NOT keep investigating after you have enough evidence. Report and let the Brain decide.

## What to Report

Structure your findings with YAML frontmatter (required by team_send_results):

```
---
reasoning: "the specific error condition (e.g., go build failed: undefined reference to X)"
steps:
  - id: check-controller
    agent: sysadmin
    summary: "Check PaC controller pod health on Konflux cluster"
---

**Trigger**: code change | dependency update | config change | infrastructure issue | flaky/intermittent
**Evidence**: 2-3 bullet points including at least one log excerpt or specific error message
**Unanswered**: anything you could not determine and why (permissions, pruned data, external system)
```

- `reasoning` (required): the root cause. Must be a specific error condition.
- `steps` (optional): remediation actions you recommend but cannot perform in your current mode.
  Each step needs `id`, `agent`, `summary`. Omit if no further action needed.

## Rules

- You have READ-ONLY access to the cluster (get, list, watch, logs). Do NOT attempt write operations.
- Focus on the specific service and namespace provided.
- If you cannot determine the root cause in 5 commands, report what you found and what you could NOT determine.
- NEVER investigate the Brain pod itself (`darwin-brain`, `darwin-blackboard-brain`).
- **Stay in your lane**: Inspect the CLUSTER and GIT REPOS using your available tools (MCP and CLI). Do NOT read application source code (`*.py`, `*.js`, `*.ts`, `Dockerfile`) -- that is the Architect's job.

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

### Pipeline Failure (CI/CD, Tekton, Konflux, Kargo)
Pipeline failures can originate from GitLab (MR, push, tag, scheduled), Kargo promotions, or direct Tekton PipelineRuns. The investigation method depends on the source but the principle is the same: **enumerate ALL failed jobs/tasks before attributing root cause.**

1. **Identify the pipeline source** from the event document: Headhunter events have GitLab context, Kargo events have Kargo context (project, stage, promotion, MR URL), Aligner events may reference either.
2. **For GitLab pipelines**: list ALL jobs in the pipeline. A single pipeline can contain multiple jobs, each mapping to a different external CI PipelineRun (e.g., build, SAST scan, cert checks). Do NOT investigate a single PipelineRun on the cluster without first enumerating all jobs in GitLab.
3. **For Kargo promotions**: check which step failed. If CI-related (wait-for-merge, pipeline failure), follow the linked MR URL and enumerate its pipeline jobs. If Kargo-internal (timeout, webhook), report the step error directly.
4. **For direct Tekton/Konflux PipelineRuns**: find the PipelineRun on the cluster, list ALL TaskRuns, identify every failed one.
5. **Drill into each failure**: for GitLab-native jobs, read the job log. For external/Konflux jobs, follow the external CI link to the PipelineRun, then drill TaskRun -> step container log. Use KubeArchive if live data is pruned.
6. Extract the actual error message from each failed job/task. Classify: code (compilation, test assertion), dependency (resolution, version conflict), compliance (cert check, license), infrastructure (image pull failure, timeout, resource limit), or orchestration (Kargo timeout, merge conflict, webhook failure).
7. **Image pull failures take precedence**: `Back-off pulling image` / `ErrImagePull` on a step container means the pod never started and the task never ran. This is a platform-wide infrastructure issue, not a code defect. Report it with higher priority than code/compliance failures.
8. Report ALL failing jobs/tasks with their individual error classifications. Do NOT attribute root cause from a single failure when multiple jobs/tasks failed independently.

### Depth Rule
**STOP when you have the actual error condition**, not just the component that failed. The Brain needs the specific error to make an escalation decision.

**Exception -- pipeline failures**: For pipeline failures (GitLab, Kargo, or direct Tekton), you must enumerate ALL failed jobs/tasks before stopping. Finding one error in one job is not sufficient when the pipeline contains multiple failed jobs or tasks. Each may have a different root cause and different remediation path.

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

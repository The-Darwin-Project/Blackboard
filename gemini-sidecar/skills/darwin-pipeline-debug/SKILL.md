---
name: darwin-pipeline-debug
description: Pipeline failure investigation -- enumerate ALL failed jobs/tasks, follow external CI links, classify errors. Extends darwin-gitlab-ops.
requires: [darwin-gitlab-ops, darwin-pipelines-as-code]
roles: [developer]
---

# Pipeline Debug

Investigate failed pipelines by enumerating ALL failing jobs or tasks, drilling into external CI systems for detail, classifying each error, and retrying if transient.

## Determine Pipeline Source

Pipeline failures can originate from different trigger sources. Identify where the pipeline ran before investigating:

| Source | Where to find jobs/tasks | How to drill into failures |
|--------|-------------------------|---------------------------|
| **GitLab MR pipeline** | GitLab pipeline jobs list (MR → Pipelines tab) | Job trace for native jobs; external CI link for Konflux jobs |
| **GitLab push/tag pipeline** | GitLab pipeline jobs list (project → CI/CD → Pipelines) | Same as MR pipeline |
| **Kargo promotion** | Kargo stage steps (promotion status in Kargo UI/CLI) + linked MR pipeline | Kargo step error message; then follow linked MR pipeline if failure is CI-related |
| **Tekton PipelineRun (direct)** | K8s MCP or KubeArchive — list TaskRuns in the PipelineRun | TaskRun → step container logs |
| **Konflux build (no GitLab)** | K8s MCP or KubeArchive — find PipelineRun by component + commit | TaskRun → step container logs |

Use the event document to determine the source: Headhunter events have GitLab context, Kargo events have Kargo context (project, stage, promotion ID, MR URL), Aligner events may reference either.

## Step 1: Enumerate ALL Failed Jobs/Tasks (CRITICAL)

A pipeline can contain multiple jobs or tasks. Each may map to a separate execution environment (e.g., distinct Konflux PipelineRuns). The aggregation point (GitLab, Kargo, or the PipelineRun itself) reports failure if ANY job/task fails.

**You MUST enumerate all jobs or tasks before investigating any single failure.**

### For GitLab pipelines (MR, push, tag, scheduled)
1. Retrieve the pipeline and list ALL jobs (not just the first failed one).
2. Identify every job with a `failed` status.
3. For each failed job, note whether it has a log (GitLab-native) or only shows "external" status (Konflux/external CI).

### For Kargo promotions
1. Check the Kargo promotion status to identify which step failed (e.g., `wait-for-merge`, `auto-merge`, `wait-for-update`).
2. If the failed step is CI-related (wait-for-merge blocked by pipeline failure): follow the linked MR URL from the Kargo context and enumerate the MR pipeline jobs as above.
3. If the failed step is Kargo-internal (timeout, webhook, freight error): report the Kargo step error directly.

### For direct Tekton/Konflux PipelineRuns (no GitLab)
1. Find the PipelineRun on the cluster (K8s MCP, KubeArchive, or CLI).
2. List ALL TaskRuns in the PipelineRun.
3. Identify every TaskRun with a failed status.

Do NOT stop at the first failure you find. Multiple jobs/tasks can fail independently for different reasons. Report ALL of them.

## Step 2: Drill Into Each Failure

### GitLab-native jobs
Read the job trace (last 50 lines) to extract the error message.

### External CI jobs (Konflux, Tekton)
GitLab external jobs link to an external CI system. Follow that link to find the corresponding PipelineRun:

1. Get the external CI URL from the GitLab job, or locate the PipelineRun by component name + commit SHA on the cluster.
2. Use K8s MCP, KubeArchive MCP, or CLI tools to find the PipelineRun.
3. List ALL TaskRuns in that PipelineRun and check each status.
4. For failed TaskRuns, read the step container logs.

### Kargo step failures
For Kargo-internal failures (not CI-related), extract the error from the promotion status. Common patterns:
- `wait-for-merge` timeout: CI pipeline blocked the merge — investigate the MR pipeline.
- `auto-merge` failure: merge conflicts or permissions — check MR merge status.
- `wait-for-update` failure: submodule/image update step failed — check the Tekton TaskRun that performed the update.

If the external link is unavailable or the data is pruned, state what you could not access and why.

## Step 3: Error Classification

After collecting errors from ALL failed jobs/tasks, classify each one:

### Infrastructure failures (take precedence in reporting)
- **Image pull failure**: `Back-off pulling image`, `ErrImagePull`, `ImagePullBackOff` on a step container. This means the pod never started and the task never ran. These are platform-wide issues affecting all pipelines that use the same image.
- **Transient infrastructure**: network timeout, registry connectivity, CDN mirror 404, resource limit eviction, pod eviction by descheduler.

### Code/build failures
- **Compilation error**: build failure, missing dependency, test assertion.
- **Compliance failure**: certification check failure (e.g., `HasLicense`), policy violation.

### Promotion/orchestration failures
- **Kargo timeout**: promotion step exceeded its deadline (e.g., 6h wait-for-merge).
- **Merge conflict**: MR cannot be merged due to conflicting changes.
- **Webhook/callback failure**: external system did not report back to GitLab/Kargo.

### Reporting priority
When multiple jobs/tasks fail for different reasons, infrastructure failures (image pull, platform outage) take priority in the report because they indicate systemic issues beyond the current pipeline. Code/compliance and orchestration failures are still reported but noted as potentially independent.

## Step 4: Retry or Report

- If ALL failures are transient: retest using the appropriate pipeline trigger command.
- If any failure is non-transient: report all failures and recommend escalation. Do NOT retest if a non-transient failure exists alongside transient ones.
- For Kargo promotion failures: recommend re-promotion only if the underlying CI issue is resolved.

## Pipeline Timing

After retesting:

1. Check pipeline status immediately. If `running` or `pending`:
   - Report back with current state. The Brain will defer and re-dispatch you later to check the result.
2. If `success`: report that retry resolved the issue.
3. If `failed`: enumerate failed jobs/tasks again (Step 1) and report updated errors.

Do NOT poll in a loop -- report the current state and let the Brain handle the timing.

## Scope

- Enumerate ALL failed jobs/tasks regardless of pipeline source
- For external CI jobs, follow the link to the external system for detailed logs
- For Kargo promotions, distinguish CI failures from Kargo-internal failures
- Classify each failure independently
- Retry pipeline once ONLY if all failures are transient
- When retry fails: all failure reasons must be determined before reporting
- Do NOT modify code or config to fix the pipeline

## Critical: No @mentions

Do NOT tag individual users (`@username`) in MR comments or anywhere else. Do NOT query project/group members to find usernames to tag. MR comments must only describe what happened -- the Brain handles all human notifications via Slack.

## Reporting Results

Always end your response with a clear recommendation for the Brain.
Do NOT include GitLab usernames or @mentions -- the Brain has its own maintainer list.

Report format when multiple jobs/tasks failed:

```
Pipeline source: {GitLab MR | GitLab push | Kargo promotion | Tekton direct}
Failed jobs/tasks (N total):
1. [job-name] — {error classification}: {specific error}
2. [job-name] — {error classification}: {specific error}

Priority: {infrastructure | code | compliance | orchestration}
```

- **Transient (retry succeeded)**: "Pipeline green after retry. Recommend merging."
- **Pipeline running**: "Pipeline retested, currently running."
- **Persistent failure**: "Pipeline still failing after retry. N jobs/tasks failed: {summary of each}. Recommend notifying maintainer with failure details."

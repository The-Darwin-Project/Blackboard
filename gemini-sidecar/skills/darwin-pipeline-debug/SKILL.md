---
name: darwin-pipeline-debug
description: Pipeline failure investigation -- read failed job logs, identify error type, retry and check. Extends darwin-gitlab-ops.
requires: [darwin-gitlab-ops]
roles: [developer]
---

# Pipeline Debug

Investigate failed pipelines: read job logs, classify the error, retry if transient.

## Read Failed Job Log

Get the last 50 lines of the most recent failed job:

```bash
# Get failed jobs for pipeline
glab api "/projects/:id/pipelines/:pipeline_id/jobs" | jq '.[] | select(.status == "failed") | {id, name, stage}'

# Get job trace (last 50 lines)
glab api "/projects/:id/jobs/:job_id/trace" | tail -50
```

## Error Classification (v1)

After reading the log, classify:

- **Transient**: network timeout, registry pull failure, flaky test -> retest via `/retest`
- **Real failure**: compilation error, missing dependency, test assertion -> report to maintainer

## Pipeline Timing

Konflux/Tekton pipelines take 20-30 minutes. After retesting:

1. Check pipeline status immediately. If `running` or `pending`:
   - Report back: "Pipeline retested, currently running. Recommend re-checking in 5 minutes."
   - The Brain will defer the event and re-dispatch you later to check the result.
2. If `success`: report that retry resolved the issue.
3. If `failed`: read the new failed job log and report the error.

Do NOT poll in a loop -- report the current state and let the Brain handle the timing.

## v1 Scope

- Read failed job log and report error type
- Retry pipeline once via `/retest` comment
- Check result after retry -- if still running, report and let Brain defer
- Do NOT attempt root cause analysis
- Do NOT modify code or config to fix the pipeline

## Reporting Results

Always end your response with a clear recommendation for the Brain:

- **Transient (retry succeeded)**: "Pipeline green after retry. Recommend merging and notifying maintainer via Slack."
- **Pipeline running**: "Pipeline retested, currently running. Recommend re-checking in 5 minutes."
- **Persistent failure**: "Pipeline still failing after retry. Error: {description}. Recommend notifying maintainer via Slack with failure details."

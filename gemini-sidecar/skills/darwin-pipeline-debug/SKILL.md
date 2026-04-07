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

After retesting:

1. Check pipeline status immediately. If `running` or `pending`:
   - Report back with current state. The Brain will defer and re-dispatch you later to check the result.
2. If `success`: report that retry resolved the issue.
3. If `failed`: read the new failed job log and report the error.

Do NOT poll in a loop -- report the current state and let the Brain handle the timing.

## Extended Investigation

When GitLab job logs are insufficient (e.g., external pipelines showing only "external" status), the failure reason must still be determined. You have K8s MCP, Playwright MCP, and CLI tools available -- choose the appropriate one based on where the pipeline executed.

## Scope

- Read failed job log and report error type
- Retry pipeline once via `/retest` comment
- Check result after retry -- if still running, report and let Brain defer
- When retry fails: the failure reason must be determined before reporting
- Do NOT modify code or config to fix the pipeline

## Critical: No @mentions

Do NOT tag individual users (`@username`) in MR comments or anywhere else. Do NOT query project/group members to find usernames to tag. MR comments must only describe what happened -- the Brain handles all human notifications via Slack.

## Reporting Results

Always end your response with a clear recommendation for the Brain.
Do NOT include GitLab usernames or @mentions -- the Brain has its own maintainer list.

- **Transient (retry succeeded)**: "Pipeline green after retry. Recommend merging."
- **Pipeline running**: "Pipeline retested, currently running."
- **Persistent failure**: "Pipeline still failing after retry. Error: {description}. Recommend notifying maintainer with failure details."

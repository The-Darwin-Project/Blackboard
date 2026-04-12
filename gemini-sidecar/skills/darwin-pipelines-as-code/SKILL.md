---
name: darwin-pipelines-as-code
description: "Pipeline trigger commands for Pipelines-as-Code (PaC) and vanilla GitLab CI. Single source of truth for /retest, /test, /ok-to-test, and /cancel."
requires: [darwin-gitlab-ops]
roles: [developer, sysadmin]
---

# Pipeline Trigger Commands

Pipeline retests and cancellations are triggered by posting specific commands as MR/PR comments. Two CI environments exist -- choose the right commands for the environment.

## Pipelines as Code (PaC)

PaC pipelines are Tekton PipelineRuns triggered by a controller that watches MR/PR comments. The following commands are recognized:

| Command | Behavior |
|---------|----------|
| `/retest` | Re-run **failed** PipelineRuns for the current commit. Skips runs that already succeeded (duplicate suppression). |
| `/retest <pipelinerun-name>` | **Always** triggers a new run for the named PipelineRun, even if a previous run succeeded. |
| `/test` | Re-trigger **all** matched PipelineRuns for the current commit. |
| `/test <pipelinerun-name>` | Re-trigger only the named PipelineRun. |
| `/ok-to-test` | Authorize pipeline execution for first-time or external contributors (trust gate). |
| `/cancel` | Cancel **all** running PipelineRuns on the MR/PR. |
| `/cancel <pipelinerun-name>` | Cancel only the named PipelineRun. |

## Vanilla GitLab CI

Vanilla GitLab CI pipelines are triggered by the GitLab CI/CD service, not a Tekton controller. The `/retest` comment is recognized by GitLab as a pipeline retry. The `/test`, `/ok-to-test`, and `/cancel` commands are PaC-specific and have no effect on vanilla GitLab CI pipelines.

## Command Selection

| Situation | Command |
|-----------|---------|
| Transient failure (network, registry, flaky test) | `/retest` |
| Need to re-run a specific PipelineRun regardless of prior result | `/retest <pipelinerun-name>` |
| Re-trigger all pipelines (e.g., after external dependency fix) | `/test` |
| First-time contributor PR needs CI authorization | `/ok-to-test` |
| Stuck or runaway pipeline consuming resources | `/cancel` |

## Expected Behavior After Posting

- `/retest` with duplicate suppression: if all runs for the current commit already succeeded, no new run is created. Post `/retest <name>` to force a re-run.
- `/ok-to-test` authorization: the contributor is trusted for this MR/PR. Subsequent pushes trigger pipelines automatically without another `/ok-to-test`.
- After posting any trigger command, check pipeline status to confirm it was accepted (status changed to `running` or `pending`). Report the current state and return -- do not poll.

## Failure Modes

- **Closed MR/PR**: Commands do not work on closed merge/pull requests. If the MR is closed, the command is silently ignored.
- **Permissions**: The comment author must have sufficient permissions. If Darwin's service account lacks authorization, the command has no effect and no error is returned.
- **No matching PipelineRun**: `/retest <name>` or `/test <name>` with a non-existent PipelineRun name produces no pipeline. Check the PipelineRun name against the repository's PaC configuration.
- **Command not recognized**: If the repository uses vanilla GitLab CI and a PaC-only command (`/test`, `/ok-to-test`, `/cancel`) is posted, it appears as a regular comment with no CI effect.

## Reference

[Pipelines as Code GitOps Commands](https://pipelinesascode.com/docs/guides/gitops-commands/)

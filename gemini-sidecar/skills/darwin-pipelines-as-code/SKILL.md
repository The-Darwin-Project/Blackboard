---
name: darwin-pipelines-as-code
description: "Pipeline trigger commands for Pipelines-as-Code (PaC) across GitHub/GitLab and vanilla GitLab CI. Single source of truth for /retest, /test, /ok-to-test, and /cancel."
roles: [developer, sysadmin]
---

# Pipeline Trigger Commands

Pipeline retests and cancellations are triggered by posting specific commands as MR/PR comments (or re-running GitHub Actions workflows when appropriate). Choose the right mechanism for the event's VCS context:

- **`gitlab_context`** (see `darwin-gitlab-ops`): supports PaC (on PaC-enabled repos) or vanilla GitLab CI.
- **`github_context`** (see `darwin-github-ops`): supports PaC GitOps comments on PaC-enabled repos, or `gh run rerun` for GitHub Actions workflows. On Prow-managed GitHub repos, NEVER post `/lgtm`, `/approve`, `/hold cancel`, or `/override`.

## Pipelines as Code (PaC — GitLab & GitHub)

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

## Vanilla GitLab CI & GitHub Actions

- **Vanilla GitLab CI (`gitlab_context`)**: triggered by the GitLab CI/CD service, not a Tekton controller. `/retest` is recognized by GitLab as a pipeline retry; `/test`, `/ok-to-test`, and `/cancel` are PaC-specific and have no effect.
- **GitHub Actions (`github_context`)**: triggered by GitHub workflow events (`pull_request`, `push`). Standard GitHub Actions workflows do not listen to `/retest` comments unless a PaC or custom workflow is configured — inspect `.tekton/` vs `.github/workflows/` before commenting.

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
- After posting any trigger command, check pipeline/check-run status to confirm it was accepted (status changed to `running` or `pending`). Report the current state and return -- do not poll.
- On subsequent dispatches, if the pipeline is still non-terminal, check queue state on the build cluster (see `darwin-k8s-mcp`) and include it in the report.

## Failure Modes

- **Closed MR/PR**: Commands do not work on closed merge/pull requests. If the MR/PR is closed, the command is silently ignored.
- **Permissions**: The comment author must have sufficient permissions. If Darwin's service account lacks authorization, the command has no effect and no error is returned.
- **No matching PipelineRun**: `/retest <name>` or `/test <name>` with a non-existent PipelineRun name produces no pipeline. Check the PipelineRun name against `.tekton/` in the repository.
- **Command not recognized**: If the repository uses vanilla GitLab CI or GitHub Actions without PaC, PaC-only commands appear as regular comments with no CI effect.

## Reference

[Pipelines as Code GitOps Commands](https://pipelinesascode.com/docs/guides/gitops-commands/)

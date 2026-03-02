---
name: darwin-mr-lifecycle
description: MR lifecycle operations -- pipeline check, retest, merge, conflict reporting. Extends darwin-gitlab-ops.
requires: [darwin-gitlab-ops]
roles: [developer, sysadmin]
---

# MR Lifecycle Operations

Handles the full MR lifecycle: check pipeline, retest, merge, and conflict reporting.
This skill assumes `darwin-gitlab-ops` is loaded (same roles guarantee this).

## Retest Pipeline

Post a `/retest` comment on the MR to trigger a pipeline rerun:

```bash
glab api /projects/:id/merge_requests/:iid/notes -f body="/retest"
```

After posting, check pipeline status:

```bash
glab api "/projects/:id/pipelines?ref=:source_branch&order_by=updated_at&per_page=1"
```

## Pipeline Timing

Konflux/Tekton pipelines take 20-30 minutes. After retesting:

1. Check pipeline status immediately. If `running` or `pending`:
   - Report back: "Pipeline triggered, currently running. Recommend re-checking in 5 minutes."
   - The Brain will defer the event and re-dispatch you later to check the result.
2. If `success`: proceed to merge.
3. If `failed`: read the failed job log and report the error.

Do NOT poll in a loop -- report the current state and let the Brain handle the timing.

## Merge MR

Only merge when pipeline is green AND merge_status is `can_be_merged`:

```bash
glab api -X PUT /projects/:id/merge_requests/:iid/merge
```

## Safety Rules

- NEVER force-push to any branch
- NEVER merge with a red/failed pipeline
- NEVER auto-rebase -- if merge_status is `cannot_be_merged`, report conflicts to maintainer
- NEVER delete branches after merge (let GitLab's auto-delete handle it)

## Conflict Reporting

If merge_status is `cannot_be_merged`:

1. Post an MR comment describing the conflict:

```bash
glab api /projects/:id/merge_requests/:iid/notes -f body="Darwin: Merge conflicts detected. Manual rebase required. Notifying maintainer."
```

1. In your response to the Brain, recommend sending a Slack notification to the maintainer about the conflict. The Brain owns Slack -- you do not have Slack access.

## Reporting Results

Always end your response with a clear recommendation for the Brain:

- **Success**: "MR merged successfully. Recommend notifying maintainer via Slack."
- **Pipeline running**: "Pipeline triggered, currently running. Recommend re-checking in 5 minutes."
- **Failure**: "Pipeline still failing after retry. Recommend notifying maintainer via Slack with failure details."
- **Conflict**: "Merge conflicts detected. Recommend notifying maintainer via Slack to rebase."

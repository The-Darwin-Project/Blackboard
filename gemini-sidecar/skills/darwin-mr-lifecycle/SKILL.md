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

After retesting:

1. Check pipeline status immediately. If `running` or `pending`:
   - Report back with current state. The Brain will defer and re-dispatch you later to check the result.
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

## Conflict / Unmergeable Handling

If merge_status is `cannot_be_merged`:

**For automated submodule MRs** (branch starts with `submodule-`, author is a bot):

- This means a newer submodule update already merged to main. The MR is obsolete.
- Close the MR with a comment explaining why:

```bash
glab api /projects/:id/merge_requests/:iid/notes -f body="Darwin: Closing this MR -- a newer submodule update has already been merged to main, making this one obsolete."
glab api -X PUT /projects/:id/merge_requests/:iid --field state_event=close
```

**For all other MRs:**

- Post an MR comment describing the conflict:

```bash
glab api /projects/:id/merge_requests/:iid/notes -f body="Darwin: Merge conflicts detected. Manual rebase required. Notifying maintainer."
```

- In your response to the Brain, recommend sending a Slack notification. The Brain owns Slack and knows who to notify -- do NOT include usernames or @mentions in your recommendation.

## Critical: No @mentions

Do NOT tag individual users (`@username`) in MR comments or anywhere else. Do NOT query project/group members to find usernames to tag. MR comments must only describe what happened -- the Brain handles all human notifications via Slack.

## Reporting Results

Always end your response with a clear recommendation for the Brain.
Do NOT include GitLab usernames or @mentions -- the Brain has its own maintainer list.

- **Success**: "MR merged successfully."
- **Pipeline running**: "Pipeline triggered, currently running."
- **Failure**: "Pipeline still failing after retry. Recommend notifying maintainer with failure details."
- **Conflict (submodule)**: "Closed obsolete submodule MR -- newer update already merged to main."
- **Conflict (other)**: "Merge conflicts detected. Recommend notifying maintainer to rebase."

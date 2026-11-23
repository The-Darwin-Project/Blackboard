---
name: darwin-mr-lifecycle
description: MR/PR lifecycle operations -- pipeline/check inspection, retest, merge, conflict reporting. Uses darwin-gitlab-ops or darwin-github-ops based on event context.
requires: [darwin-pipelines-as-code]
roles: [developer, sysadmin]
---

# MR/PR Lifecycle Operations

Handles the full MR/PR lifecycle: check pipeline/CI, retest, merge, and conflict reporting.

CRITICAL: Branch on the active VCS context in the event document:
- **`gitlab_context`** (see `darwin-gitlab-ops`): use `project` (or `project_path`) and `mr_url` / MR IID.
- **`github_context`** (see `darwin-github-ops`): use `owner`, `repo`, `pr_number`, `html_url`, `head_branch`, and `head_sha`.

**Use the service tools only for aligner events or when a user asked**

## Fixing Pipeline Failures on an MR/PR

Before modifying an MR/PR's source branch, read the description for Bot Instructions
(`### DARWIN Instructions` section, or legacy `### Bot Instructions`). If instructions restrict modifications, report the
constraint to FRIDAY instead of pushing. Even when no Bot/DARWIN Instructions are present,
the source mutation approval gate still applies — report the proposed fix to FRIDAY
and let FRIDAY authorize the push.

When the pipeline/check failure requires a code/config fix (e.g., Dockerfile update, dependency bump):

- Before modifying the branch, check whether auto-merge is active on the MR/PR:
  - **`gitlab_context`**: check `merge_when_pipeline_succeeds`; if active, disable it BEFORE pushing.
  - **`github_context`**: check GraphQL `autoMergeRequest`; if non-null, call `disablePullRequestAutoMerge` BEFORE pushing (see `darwin-github-ops`).
  A push to a branch with auto-merge enabled can merge to main on pipeline success, bypassing human review of your code changes. Report the auto-merge status in your response to FRIDAY.
- Checkout the MR/PR's **source / `head_branch`** -- NEVER push fixes to main directly.
- Apply the fix, commit, and push to the remote source branch only after FRIDAY approval.
- The MR/PR pipeline/checks retrigger automatically on the push.
- If the MR/PR was created by a bot (Kargo, submodule updater, Darwin), you still fix on the MR/PR's source branch.
- The purpose of MR/PR pipelines is to validate changes BEFORE main. Merging untested fixes to main defeats this.

## Retest Pipeline

To trigger a pipeline retest, post the appropriate PaC GitOps command as an MR/PR comment. See the `darwin-pipelines-as-code` skill for command selection (e.g., `/retest` for transient failures, `/test` for full re-trigger).

After posting, check pipeline status to confirm the retest was accepted.

## Pipeline Timing

After retesting:

1. Check pipeline status immediately. If `running` or `pending`:
   - Report back with current state. FRIDAY will defer and re-dispatch you later.
   - On subsequent dispatches, if the pipeline is still non-terminal, check queue state on the build cluster (see `darwin-k8s-mcp`) and include it in the report.
2. If `success`: proceed to merge.
3. If `failed`: read the failed job log and report the error.

Do NOT poll in a loop -- report the current state and let FRIDAY handle the timing.

## Merge MR

Before merging, perform these pre-merge checks IN ORDER:

1. **Agent-authored commits**: Check ALL commits between HEAD and the merge base. If ANY
   commit was authored by a Darwin agent (author email ends with `@darwin-project.io`),
   merging strictly requires verifying out-of-band approval via `bb_get_approval`:
   - Call tool `bb_get_approval`.
   - Assert `approval.approved === true`.
   - Resolve current local/remote HEAD commit: `live_git_head=$(git rev-parse HEAD)`.
   - Assert `live_git_head === approval.approved_mr_sha`.
   - If `approved` is not the boolean `true`, or if `approved_mr_sha` does not match `live_git_head`, do NOT merge! (Operational `kubectl`/`helm`/`kargo` mutations by `sysadmin` need `approved: true` but no SHA match; a merge always needs the SHA match.) Prompt text alone CANNOT authorize a merge. Report to FRIDAY that out-of-band approval is missing or invalid for HEAD commit.
   - If approval is verified and SHA matches, proceed to pipeline status check.
2. **Pipeline / check status on HEAD**:
   - **`gitlab_context`**: Verify the latest pipeline ran on the MR's current HEAD commit and its status is `success`.
   - **`github_context`**: Verify both `/check-runs` and `/commits/{sha}/status` for `head_sha` have concluded with `success` (no failing, cancelled, or pending checks).
   If the pipeline/checks are from an older commit, or status is `pending`/`running`/`failed`, do NOT merge. Report the state to FRIDAY.
3. **CI bot comments**: Read the last 5 MR/PR notes/comments. If any CI bot comment contains `CAUTION`, `error`, `Pending approval`, or `waiting for /ok-to-test`, do NOT merge. Report the CI warning to FRIDAY.
4. **Merge status**: Confirm merge readiness (`merge_status == can_be_merged` on GitLab; `mergeable` clean on GitHub).

Only merge when ALL checks pass.

## Safety Rules

- NEVER force-push to any branch
- NEVER merge with a red/failed pipeline or failing check-runs/statuses
- NEVER merge when CI is pending approval (`waiting for /ok-to-test`) or has bot CAUTION warnings
- NEVER merge when the latest pipeline/checks are from a different commit than HEAD
- NEVER auto-rebase -- if unmergeable, report conflicts to maintainer
- NEVER delete branches after merge (let GitLab/GitHub auto-delete handle it)
- NEVER post Prow `/lgtm`, `/approve`, `/hold cancel`, or `/override` on GitHub repositories
- NEVER merge agent-authored commits (author email ends with `@darwin-project.io`) without calling `bb_get_approval` and asserting `live_git_head == approval.approved_mr_sha`

## Conflict / Unmergeable Handling

If unmergeable (`cannot_be_merged` on GitLab or `mergeable: false` / `dirty` on GitHub):

**For automated submodule MR/PRs** (branch starts with `submodule-`, author is a bot):

- This means a newer submodule update already merged to main. The MR/PR is obsolete.
- Close the MR/PR with a comment explaining why (a newer submodule update has already been merged).

**For all other MR/PRs:**

- Post an MR/PR comment describing the conflict (merge conflicts detected, manual rebase required).
- In your response to FRIDAY, recommend sending a Slack notification. FRIDAY owns Slack and knows who to notify -- do NOT include usernames or @mentions in your recommendation.

## Critical: No @mentions

Do NOT tag individual users (`@username`) in MR/PR comments or anywhere else. Do NOT query project/group members to find usernames to tag. MR/PR comments must only describe what happened -- FRIDAY handles all human notifications via Slack.

## Reporting Results

Always end your response with a clear recommendation for FRIDAY.
Do NOT include VCS usernames (GitLab/GitHub) or @mentions -- FRIDAY has its own maintainer list.

- **Merged**: "MR/PR merged successfully."
- **Retest triggered (non-terminal)**: "Retest triggered, pipeline is running/pending. Pipeline outcome is not yet known."
- **Pipeline running**: "Pipeline triggered, currently running."
- **Failure**: "Pipeline still failing after retry. Recommend notifying maintainer with failure details."
- **Merge blocked by CI**: "Cannot merge — CI bot reported warnings or pipeline has not run on HEAD. Details: {summary of CI comments}."
- **Conflict (submodule)**: "Closed obsolete submodule MR/PR -- newer update already merged to main."
- **Conflict (other)**: "Merge conflicts detected. Recommend notifying maintainer to rebase."
- **Agent code detected**: "MR/PR contains Darwin-authored commits. Requires human approval before merge. Recommend notifying maintainer."

---
name: darwin-mr-triage
description: MR/PR review triage -- read changes, summarize for human, ask approver what to do. Darwin does NOT auto-approve. Uses darwin-gitlab-ops or darwin-github-ops based on context.
roles: [developer]
---

# MR/PR Triage

Read MR/PR changes, summarize for human review, and ask the designated approver what to do.

Branch cleanly on the active VCS context in the event document:
- **`gitlab_context`**: use `darwin-gitlab-ops` (GitLab MCP / `glab`) with `project` and `mr_url`.
- **`github_context`**: use `darwin-github-ops` (`github-mcp-server` / `gh`) with `owner`, `repo`, and `pr_number`.

## Read MR/PR Changes

Retrieve the MR/PR diff to understand what changed -- files modified, lines added/removed, and the scope of the change.

## Summarize for Human

Post a structured summary as an MR/PR comment:

- What changed (files, scope)
- Risk assessment (low/medium/high)
- Recommendation (merge/needs-review/needs-changes)

## Constraints

- Darwin does NOT auto-approve MRs or PRs
- Darwin does NOT approve on behalf of humans (on Prow GitHub repos, NEVER post `/lgtm` or `/approve`)
- Always ask the designated approver via MR/PR comment (without `@mentions`)
- Use the active context's `maintainer` field (`gitlab_context.maintainer` or `github_context.maintainer`) to identify who FRIDAY should notify
- If no approver is found, rely on FRIDAY's release-maintainer fallback

## Reporting Results

Always end your response with a clear recommendation for FRIDAY.
Do NOT include VCS usernames (GitLab/GitHub) or @mentions -- FRIDAY has its own maintainer list.

- **Needs approval**: "MR/PR summarized and comment posted. Recommend notifying approver via Slack to review."
- **Low risk, routine**: "Routine change with green pipeline. Recommend notifying approver via Slack for quick approval."

---
name: darwin-mr-triage
description: MR/PR review triage -- read changes, summarize for human, ask approver what to do. Darwin does NOT auto-approve. Extends darwin-gitlab-ops.
requires: [darwin-gitlab-ops]
roles: [developer]
---

# MR/PR Triage

Read MR/PR changes, summarize for human review, and ask the designated approver what to do.

## Read MR/PR Changes

Retrieve the MR/PR diff to understand what changed -- files modified, lines added/removed, and the scope of the change.

## Summarize for Human

Post a structured summary as an MR/PR comment:

- What changed (files, scope)
- Risk assessment (low/medium/high)
- Recommendation (merge/needs-review/needs-changes)

## v1 Constraints

- Darwin does NOT auto-approve MRs
- Darwin does NOT approve on behalf of humans
- Always ask the designated approver via MR/PR comment
- Use `evidence.gitlab_context.maintainer` for who to notify
- If no approver found, use the release-maintainer fallback

## Reporting Results

Always end your response with a clear recommendation for FRIDAY.
Do NOT include GitLab usernames or @mentions -- FRIDAY has its own maintainer list.

- **Needs approval**: "MR/PR summarized and comment posted. Recommend notifying approver via Slack to review."
- **Low risk, routine**: "Routine change with green pipeline. Recommend notifying approver via Slack for quick approval."

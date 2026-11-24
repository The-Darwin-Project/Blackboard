---
name: darwin-github-ops
description: "GitHub environment context: repository resolution, multi-org authentication, merge guards, and API conventions for GitHub PRs and Issues."
roles: [architect, sysadmin, developer, qe, security_analyst, code_reviewer]
---

# GitHub Operations

## Repository and Context Resolution (CRITICAL)

When working on an Event from Headhunter, the event document contains the authoritative repository coordinates in the **GitHub Context** (`github_context`) or **GitHub Issue Context** (`github_issue_context`) section.
**Use THAT `owner`, `repo`, `pr_number` / `issue_number`, `html_url`, `head_branch`, and `head_sha` for all API calls and git operations.**

Extract from the event document:
- `owner` / `repo` -- target repository (`{owner}/{repo}`)
- `pr_number` or `issue_number` -- target pull request or issue number
- `html_url` -- canonical GitHub PR/Issue URL
- `head_branch` / `head_sha` -- PR source branch and current head commit SHA (PR events)

## Pre-Configured Multi-Org Authentication

GitHub tools are pre-configured for multi-org GitHub App authentication. You do not need to manage credentials manually:

- **`gh` CLI wrapper (`/usr/local/bin/gh`)**: resolves the per-org installation token from `/tmp/gh-token-map.json` (mode `0600`) based on the repository remote before execing `.gh-real`, falling back to `GH_TOKEN`. Never read `/tmp/gh-token-map.json` directly (blocked by mutation/permission hooks).
- **GitHub MCP (`github-mcp-server`)**: auto-configured native GitHub MCP tools (`github-mcp-server`). Prefer MCP tools for structured PR/issue/check reads and API calls; use `gh` / `gh api` as fallback.
- **`git-credential-darwin`**: supplies per-org credentials automatically to `git fetch`, `git clone`, and `git push`.

## Arrival Comment and No-@mentions

When dispatched to work on a GitHub PR or Issue, post a brief arrival comment announcing your task:

Format: `Darwin ({role}): {one sentence describing your actual task}`

- Post **once** on arrival for standard PR (`darwin-review`) and Issue (`darwin-work`) events.
- For `review_feedback` and `mention` events, Headhunter already posted the tracking comment and eyes reaction — do NOT post a duplicate arrival comment.
- Do not post progress updates to the PR/Issue — use `team_send_message` for updates to FRIDAY.
- **CRITICAL — No `@mentions`**: NEVER tag individual users (`@username`) in PR/Issue comments or query org/collaborator lists to find usernames. FRIDAY handles all human notifications via Slack.

## GraphQL Auto-Merge Guard (Before Any Push)

On GitHub, pushing a commit as a writer does **NOT** cancel armed auto-merge. Before pushing any commit to a PR's `head_branch`, check `autoMergeRequest` and disable it first:

```bash
gh pr view <pr_number> --repo <owner>/<repo> --json id,autoMergeRequest
```

If `autoMergeRequest` is non-null, call GraphQL `disablePullRequestAutoMerge` using the PR's GraphQL node `id` BEFORE pushing:

```bash
gh api graphql -f query='mutation($id: ID!) { disablePullRequestAutoMerge(input: {pullRequestId: $id}) { pullRequest { number autoMergeRequest { enabledAt } } } }' -f id=<node_id>
```

- Agent-authored commits (`*@darwin-project.io`) are NEVER merged, auto-merged, or re-armed for auto-merge without explicit human out-of-band approval (`bb_get_approval` with `approved === true` and `live_git_head === approval.approved_mr_sha`).

## Inline Review Comment Replies

When responding to PR review feedback:

1. Post ONE summary comment on the PR mapping each feedback item `id` to the fixing commit SHA (or explaining why an item was declined / needs clarification).
2. Post an in-thread reply on each inline review comment. Prefer `github-mcp-server` tools for posting review replies; when falling back to `gh api`, pass the body via a single-quoted heredoc (`-F body=@- <<'EOF'`) rather than double-quoted shell arguments so untrusted backticks or `$(...)` cannot trigger bash expansion:

```bash
gh api -X POST /repos/{owner}/{repo}/pulls/{n}/comments/{id}/replies -F body=@- <<'EOF'
Fixed in <short-sha>: <summary>
EOF
```

- NEVER resolve review threads — resolving threads is the human reviewer's responsibility.

## Check-Runs vs Commit Statuses

GitHub splits CI results across two APIs for a given `head_sha`:

- **Check Runs (`GET /repos/{owner}/{repo}/commits/{sha}/check-runs`)**: GitHub Actions, Pipelines-as-Code (PaC), and GitHub Apps (`/check-runs`).
- **Commit Statuses (`GET /repos/{owner}/{repo}/commits/{sha}/status`)**: Legacy commit status contexts such as Prow and Jenkins (`/commits/{sha}/status`).

Always inspect **both** `/check-runs` and `/commits/{sha}/status` for `head_sha` when evaluating CI state or enumerating failed jobs. Follow `details_url` / `target_url` to inspect external Tekton/Konflux PipelineRuns when a check links out to a build cluster.

## Prow Slash-Command Prohibition

On Prow-managed repositories, **NEVER** post `/lgtm`, `/approve`, `/hold cancel`, or `/override` (and never ask another bot to). Darwin never approves or overrides human merge gates.

For `review_feedback` and `mention` events, do NOT add or remove `darwin-*` labels — those events stay outside the `darwin-review` label state machine.

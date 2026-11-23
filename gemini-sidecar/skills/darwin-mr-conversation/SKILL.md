---
name: darwin-mr-conversation
description: MR/PR comment thread interaction -- read threads, respond concisely. Uses darwin-gitlab-ops or darwin-github-ops based on context.
roles: [developer, sysadmin]
---

# MR/PR Conversation

Read MR/PR comment threads, understand context, and respond concisely.

Branch cleanly on the active VCS context in the event document:
- **`gitlab_context`**: use `darwin-gitlab-ops` (GitLab MCP / `glab`) with `project` and MR IID to read MR discussions/notes and post replies.
- **`github_context`**: use `darwin-github-ops` (`github-mcp-server` / `gh`) with `owner`, `repo`, and `pr_number` to read issue/review comments and reply inline via `POST /repos/{owner}/{repo}/pulls/{n}/comments/{id}/replies` or PR summary comments.

## Read MR/PR Discussions

Retrieve the MR/PR discussion threads (and inline review comments on GitHub PRs) to understand the context and history of the conversation.

## Post a Comment

Post a concise, actionable response as an MR/PR comment (or inline review thread reply on GitHub). Prefix summary comments with `Darwin:` to identify automated responses.

## Guidelines

- Always reference the original comment or discussion when responding (and on GitHub, reply in-thread on inline comments; NEVER resolve review threads)
- Keep responses concise and actionable
- Do NOT tag individual users (`@username`) in MR/PR comments -- FRIDAY handles all human notifications via Slack
- If the question is about code: investigate and answer
- If the question is about process/approval: escalate to maintainer
- If unsure about the answer: say so explicitly and escalate

## Reporting Results

Always end your response with a clear recommendation for FRIDAY.
Do NOT include VCS usernames (GitLab/GitHub) or @mentions -- FRIDAY has its own maintainer list.

- **Answered**: "Responded to MR/PR comment thread. No further action needed."
- **Needs human**: "Question requires human judgment. Recommend notifying maintainer via Slack to respond on the MR/PR."
- **Escalation**: "Unable to resolve. Recommend notifying maintainer via Slack for guidance."

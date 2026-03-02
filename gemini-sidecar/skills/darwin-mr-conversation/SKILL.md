---
name: darwin-mr-conversation
description: MR comment thread interaction -- read threads, respond, tag users. Extends darwin-gitlab-ops.
requires: [darwin-gitlab-ops]
roles: [developer, sysadmin]
---

# MR Conversation

Read MR comment threads, understand context, respond concisely, and tag users.

## Read MR Discussions

```bash
glab api /projects/:id/merge_requests/:iid/discussions
```

## Post a Comment

```bash
glab api /projects/:id/merge_requests/:iid/notes -f body="Darwin: your response here"
```

## Guidelines

- Always reference the original comment or discussion when responding
- Keep responses concise and actionable
- Tag users by @username in MR comments when they need to take action
- If the question is about code: investigate and answer
- If the question is about process/approval: escalate to maintainer
- If unsure about the answer: say so explicitly and escalate

## Reporting Results

Always end your response with a clear recommendation for the Brain:

- **Answered**: "Responded to MR comment thread. No further action needed."
- **Needs human**: "Question requires human judgment. Recommend notifying maintainer via Slack to respond on the MR."
- **Escalation**: "Unable to resolve. Recommend notifying maintainer via Slack for guidance."

---
name: darwin-branch-naming
description: Branch naming convention for Darwin agents
roles: [developer, qe]
---

# Branch Naming Convention

When creating feature branches, always use: `feat/evt-{EVENT_ID}`

Example: `feat/evt-2cb52e7f`

Both Developer and QE MUST use the same branch name. Read the event ID from the event document
in your working directory at `events/event-{id}.md` (e.g., `/data/gitops-developer/events/event-2cb52e7f.md`).

Do NOT create descriptive branch names (e.g., feat/customer-invoice-system).
The event ID ensures Developer and QE push to the same branch without coordination.

---
name: darwin-branch-naming
description: Branch naming convention for Darwin agents
roles: [developer, qe]
---

# Branch Naming Convention

When creating feature branches, always branch from the latest remote main:

```bash
git fetch origin
git checkout -b feat/evt-{EVENT_ID} origin/main
```

Example: `feat/evt-2cb52e7f`

Both Developer and QE MUST use the same branch name. Read the event ID from the event document
in your working directory at `events/event-{id}.md` (e.g., `/data/gitops-developer/events/event-2cb52e7f.md`).

Do NOT create descriptive branch names (e.g., feat/customer-invoice-system).
Do NOT branch from local main -- always use `origin/main` to avoid carrying stale merge history.

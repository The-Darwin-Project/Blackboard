---
name: darwin-pr-template
description: PR creation template for consistent, well-structured pull requests. Use when opening a PR.
roles: [developer]
modes: [implement]
---

# PR Template

When creating a pull request with `gh pr create`, use this structure:

## Title Format

```Txt
feat: <short description> (evt-{EVENT_ID})
```

Examples:

- `feat: add admin authentication with session cookies (evt-78fe9a5f)`
- `feat: add product reviews and detail modal (evt-ed3ed4fa)`

## Body Format

```log
## Summary
<1-2 sentences: what this PR does and why>

## Changes
- `file.py` -- <what changed>
- `file.html` -- <what changed>

## Testing
- <how this was tested locally>
- <which tests were added>

## Event
evt-{EVENT_ID}
```

## Rules

- Title MUST start with `feat:` for features or `fix:` for bug fixes
- Title MUST include the event ID in parentheses
- Body MUST list changed files with one-line descriptions
- Body MUST reference the event ID
- Do NOT include AI-generated disclaimers or "co-authored-by" lines
- Keep the summary under 3 sentences

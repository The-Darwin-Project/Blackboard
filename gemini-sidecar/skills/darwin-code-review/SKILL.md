---
name: darwin-code-review
description: Code and MR/PR review workflow for plan mode. Use when reviewing merge requests, pull requests, or code changes.
roles: [architect]
modes: [plan]
---

# Darwin Code Review Workflow

## When to Use

You are in review mode. The Brain wants a code review, NOT an implementation plan. Do NOT produce a plan or write code.

## Review Process

1. **Fetch the diff**: Obtain the MR/PR diff for the changes under review
2. **Read the context**: Check related files to understand the impact
3. **Assess each change** against the criteria below

## Review Criteria

For each finding, assign a severity:

- **HIGH**: Security issues, data loss risk, breaking changes, missing error handling
- **MEDIUM**: Logic errors, missing edge cases, performance concerns, API contract violations
- **LOW**: Style issues, naming, documentation gaps, minor improvements

## Output Format

Structure your review with YAML frontmatter wrapping the body:

```text
---
reasoning: "APPROVE | REQUEST CHANGES | NEEDS DISCUSSION: brief justification"
---

## Review Summary
<1-2 sentence overview>

## Findings
| Severity | File | Issue |
| -------- | ---- | ----- |
| HIGH     | path/to/file.py:42 | Description of the issue |
| MEDIUM   | path/to/file.py:88 | Description of the issue |
```

The `reasoning` field is required by `team_send_results`. It must come FIRST, before the review body.

## Rules

- Do NOT produce an implementation plan. This is a review, not a planning task.
- Do NOT modify any files. Read-only analysis.
- Be specific: cite file paths and line numbers for every finding.
- If the changes look good, say so. Do not invent issues.
- Use `team_send_results` to deliver your review to the Brain.

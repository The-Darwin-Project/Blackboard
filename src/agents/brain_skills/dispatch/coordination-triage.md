---
description: "Dispatch coordination: when to use Developer, QE, or sequential Developer-then-QE."
tags: [dispatch, coordination, developer, qe]
---
# Coordination Triage -- Dispatch Rules

When dispatching work to Developer or QE, use these rules.

## Developer only (select_agent developer)

Use when the task is:
- MR checks, status queries, or read-only investigation (`mode: investigate`)
- Simple code changes, config tweaks, small fixes (`mode: execute`)
- Single write actions: post comment, merge MR, tag release (`mode: execute`)
- No new tests required; change is low-risk

## QE only (select_agent qe)

Use when the task is:
- Writing tests only, no implementation changes (`mode: test`)
- Test verification or quality checks (`mode: test`)
- Verifying a deployment via browser/Playwright (`mode: test`)
- Running existing test suites against a branch (`mode: investigate`)

## Developer then QE (sequential dispatch)

Use when the task requires:
- Feature implementations that need both code and tests
- Bug fixes that need tests to verify the fix
- Architect plans with dev and QE steps
- Tasks mentioning crashes, errors, TypeErrors, or stack traces
- Multiple distinct issues (2+ problems)
- User-reported UI bugs or behavioral regressions

**Sequence:** Dispatch Developer first (`mode: implement`). When Developer completes,
evaluate the result. Then dispatch QE (`mode: test`) to verify.

## Default

- Errors, crashes, bugs, or multiple issues: **Developer then QE**.
- Clearly read-only or single-action: **Developer only**.
- If genuinely unclear: **Developer then QE** (safer to verify).

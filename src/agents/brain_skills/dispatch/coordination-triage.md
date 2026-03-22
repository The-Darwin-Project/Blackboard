---
description: "Dispatch coordination: when to use Developer, QE, or sequential Developer-then-QE."
tags: [dispatch, coordination, developer, qe]
---
# Coordination Triage -- Dispatch Rules

When dispatching work to Developer or QE, use these rules.

## Developer only

Use when the task is:

- MR checks, status queries, or read-only investigation
- Simple code changes, config tweaks, small fixes
- Single write actions: post comment, merge MR, tag release
- No new tests required; change is low-risk

## QE only

Use when the task is:

- Writing tests only, no implementation changes
- Test verification or quality checks
- Verifying a deployment via browser
- Running existing test suites against a branch

## Developer then QE (sequential dispatch)

Use when the task requires:

- Feature implementations that need both code and tests
- Bug fixes that need tests to verify the fix
- Architect plans with dev and QE steps
- Tasks mentioning crashes, errors, TypeErrors, or stack traces
- Multiple distinct issues (2+ problems)
- User-reported UI bugs or behavioral regressions

Dispatch Developer first for implementation. When Developer completes, evaluate the result. Then dispatch QE to verify.

## When Unclear

If the dispatch choice is unclear, default to Developer then QE -- verification is safer than skipping it.

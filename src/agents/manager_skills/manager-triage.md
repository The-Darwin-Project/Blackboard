# Manager Triage — Dispatch Rules

When analyzing an incoming task, choose the correct dispatch function.

## dispatch_developer (solo)

Use when the task is:

- MR checks, status queries, or read-only investigation
- Simple code changes (typos, config tweaks, small fixes)
- Single write actions: post comment, merge MR, tag release, rollback
- No new tests required; change is low-risk

## dispatch_qe (solo)

Use when the task is:

- Writing tests only (no implementation changes)
- Test verification or quality checks
- Test-only changes; developer has nothing to implement

## dispatch_both (concurrent)

Use when the task requires:

- Feature implementations that need both code and tests
- Bug fixes that need tests to verify the fix
- Architect plans with dev and QE steps; both agents work on the same scope

## Guidance Overrides

- **Architect plan with frontmatter**: If the plan includes step-to-agent mapping (e.g. `assign: developer`, `assign: qe`), follow that mapping. Use the step assignments to decide dispatch.
- **Ops journal**: If similar past tasks succeeded with a specific dispatch, prefer that pattern.

## Default

If unclear, use **dispatch_developer**. Simpler to escalate later than to over-coordinate with both agents.

---
description: "Dispatch coordination: when to use Developer, QE, or sequential Developer-then-QE."
tags: [dispatch, coordination, developer, qe]
---
# Coordination Triage -- Dispatch Rules

## Task Decomposition (before dispatching)

Before dispatching a multi-step task, ask: "Can this be broken into smaller independently-verifiable batches?" If yes, dispatch the first batch only. Evaluate the result. Then dispatch the next. This avoids congestion collapse when agents are loaded and reduces cycle time without adding capacity.

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

## Sequential Dispatch Coordination

When dispatching in a sequential pair (Developer then QE):

- **First agent (Developer)**: Remind them that a teammate will verify after them. They should leave notes about shared concerns -- especially test files they created or modified -- via team coordination.
- **Second agent (QE)**: Include a summary of what the previous agent changed (files, branches, test modifications) so they don't start blind. If the Developer wrote tests, QE should review and extend them, not duplicate.

## Post-Implementation Pipeline (after Developer merge)

When a Developer completes an implementation that resulted in a code merge:

1. **SysAdmin** (mode=investigate) -- validate deployment: confirm new image build, GitOps tag update, pod rollout, service health
2. **QE** (mode=test) -- functional verification: verify the fix works, run tests, check cache/state

Do NOT skip the SysAdmin deployment validation step. The QE cannot verify functional correctness if the new code is not deployed yet.

## Message vs Route Decision

Before dispatching, ask: "Does this need a work plan or just a quick answer?"

| Signal | Tool | Example |
|---|---|---|
| User asks a question about status | message_agent | "What's the pipeline status for MR !36?" |
| User wants something done | select_agent | "Fix the failing test in service X" |
| You need to relay info to a working agent | message_agent | "User says: focus on the executive template" |
| You need an agent to investigate | select_agent | "Check why cache keys are empty" |
| Simple greeting or acknowledgment | message_agent | "User says hi" |
| Multi-step task with verification | select_agent | "Implement fix, run tests, open PR" |

When in doubt, use select_agent -- it has full task tracking. message_agent is for lightweight, single-turn interactions where a full dispatch is overkill.

## Plan Before Routing (COMPLICATED/COMPLEX only)

For COMPLICATED or COMPLEX events, call `create_plan` before `select_agent` to chalk your intended agent sequence on the blackboard. This makes the execution order visible to agents, the dashboard, and yourself for progress tracking.

For CLEAR or CHAOTIC events, route directly -- the routing turn IS the plan. If you later discover the event needs multi-step planning, reclassify via `classify_event` first to unlock `create_plan`.

## When Unclear

If the dispatch choice is unclear, default to Developer then QE -- verification is safer than skipping it.

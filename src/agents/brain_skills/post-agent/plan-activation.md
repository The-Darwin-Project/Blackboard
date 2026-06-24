---
description: "Recognize structured plans from any source, batch by agent, and dispatch efficiently"
tags: [plan, activation, routing, blackboard]
---
# Plan Activation and Routing

Plans appear from multiple sources (FRIDAY, Architect, Headhunter) but all share the same conversation turn structure. Recognizing them consistently — regardless of origin — ensures no plan is missed, double-dispatched, or orphaned on the blackboard.

Plans appear on the blackboard as conversation turns with `action="plan"`. They can come from any source: FRIDAY (via `create_plan`), the Architect (structured result), or Headhunter (bot instructions). The last `action="plan"` turn is the active plan.

Plan turns include `taskForAgent.steps` with agent assignments:

```json
{"steps": [
  {"id": "1", "agent": "developer", "summary": "Add modal HTML"},
  {"id": "2", "agent": "developer", "summary": "Add JS function"},
  {"id": "3", "agent": "qe", "summary": "Verify in browser"}
], "source": "architect"}
```

## Recognize and Group

Grouping consecutive same-agent steps into one dispatch reduces round-trip overhead (clone, context load, return). Dispatching sequentially across agent boundaries ensures each group has the predecessor's results as context.

Read the plan steps from the latest `action="plan"` turn. Group consecutive steps by assigned agent:

- Steps sharing the same agent become one dispatch
- When the agent changes, start a new dispatch group

## Dispatch Principles

**Same-agent plans (most common):**

- Send the entire plan context in a single dispatch to the assigned agent, UNLESS the event is COMPLICATED or COMPLEX -- in that case, dispatch the smallest independently-verifiable batch, evaluate the result, then dispatch the next.
- Implementation changes that modify code need QE verification afterward.

**Mixed-agent plans:**

- Dispatch each agent group sequentially. Complete one before starting the next.
- Include the full plan for context, but specify which steps belong to the current agent.

**Single-step tasks:**

- Dispatch directly to the assigned agent.

## Progress Tracking

Without checking progress before dispatching the next agent, you risk re-dispatching completed steps (wasting a cycle) or dispatching into an incomplete prerequisite (the agent starts from a state the plan didn't intend).

- Use `get_plan_progress` to check which steps are completed before routing the next agent.
- Agents mark steps as completed -- these appear as `plan_step` turns on the blackboard.
- Route the next agent only when their predecessor's steps are completed.

## Failure Handling

- If an agent reports a step failure: decide whether to retry, skip, or escalate to the user.
- If the agent's recommendation conflicts with the plan, prefer the agent's recommendation -- they have fresher context. The agent can create a revised plan turn.

## Agent-Sourced Investigation Plans

Agent-sourced plans are proposed remediation actions, not pre-approved execution plans. The investigation agent identified potential next steps based on its findings, but those steps haven't been validated against available agent capabilities or authorized by the orchestrator.

When an agent (not the Architect or FRIDAY) produces a plan turn with steps, these are
**proposed remediation actions** from an investigation, not a pre-approved execution plan.
Before dispatching agent-sourced plan steps:

1. Verify the steps are actionable with available agents and modes.
2. Dispatch the first step. Evaluate the result before dispatching the next.
3. If all steps are outside Darwin's capability, escalate but include them in the
   incident description as "recommended next steps for the maintainer."

## Special Cases

- If the plan proposed multiple options with trade-offs, present them to the user first. Only begin execution after the user selects an option.
- If there is no plan turn, use your normal routing judgment.
- Structural changes on the default/main branch require user approval before execution.
  MR-scoped build fixes (Dockerfile patches, dependency bumps) are safe-to-fail --
  the pipeline validates before merge. See Decision Guidelines for the authorization workflow.

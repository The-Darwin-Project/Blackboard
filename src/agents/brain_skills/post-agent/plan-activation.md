---
description: "Recognize structured plans from any source, batch by agent, and dispatch efficiently"
tags: [plan, activation, routing, blackboard]
---
# Plan Activation and Routing

Plans appear on the blackboard as conversation turns with `action="plan"`. They can come from any source: the Brain (via `create_plan`), the Architect (structured result), or Headhunter (bot instructions). The last `action="plan"` turn is the active plan.

Plan turns include `taskForAgent.steps` with agent assignments:

```json
{"steps": [
  {"id": "1", "agent": "developer", "summary": "Add modal HTML"},
  {"id": "2", "agent": "developer", "summary": "Add JS function"},
  {"id": "3", "agent": "qe", "summary": "Verify in browser"}
], "source": "architect"}
```

## Recognize and Group

Read the plan steps from the latest `action="plan"` turn. Group consecutive steps by assigned agent:

- Steps sharing the same agent become one dispatch
- When the agent changes, start a new dispatch group

## Dispatch Principles

**Same-agent plans (most common):**

- Send the entire plan context in a single dispatch to the assigned agent.
- Implementation changes that modify code need QE verification afterward.

**Mixed-agent plans:**

- Dispatch each agent group sequentially. Complete one before starting the next.
- Include the full plan for context, but specify which steps belong to the current agent.

**Single-step tasks:**

- Dispatch directly to the assigned agent.

## Progress Tracking

- Use `get_plan_progress` to check which steps are completed before routing the next agent.
- Agents mark steps via `bb_update_plan_step` -- these appear as `action="plan_step"` turns on the blackboard.
- Route the next agent only when their predecessor's steps are completed.

## Failure Handling

- If an agent reports a step failure: decide whether to retry, skip, or escalate to the user.
- If the agent's recommendation conflicts with the plan, prefer the agent's recommendation -- they have fresher context. The agent can create a revised plan turn.

## Special Cases

- If the plan proposed multiple options with trade-offs, present them to the user first. Only begin execution after the user selects an option.
- If there is no plan turn, use your normal routing judgment.
- Structural changes (modifying code, templates, schemas) require user approval before execution.

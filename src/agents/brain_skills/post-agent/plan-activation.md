---
description: "Recognize Architect structured plans, batch by agent, and dispatch efficiently"
tags: [plan, activation, architect, routing]
---
# Plan Activation and Routing

When the Architect returns a structured plan, it includes a YAML frontmatter with step assignments:

```yaml
steps:
  - {id: 1, agent: developer, mode: implement, summary: "Add modal HTML", status: pending}
  - {id: 2, agent: developer, mode: implement, summary: "Add JS function", status: pending}
  - {id: 3, agent: qe, mode: test, summary: "Verify in browser", status: pending}
```

## Recognize and Group

Read the plan steps. Group consecutive steps by assigned agent:

- Steps sharing the same agent become one dispatch
- When the agent changes, start a new dispatch group

Send the full Architect plan as the work order. The agent reads it and follows the steps.

## Dispatch Principles

**Same-agent plans (most common):**

- Send the entire plan in a single dispatch to the assigned agent.
- Implementation changes that modify code need QE verification afterward.

**Mixed-agent plans:**

- Dispatch each agent group sequentially. Complete one before starting the next.
- Include the full plan for context, but specify which steps belong to the current agent.

**Single-step tasks:**

- Dispatch directly to the assigned agent.

## Failure Handling

- If an agent reports a step failure: decide whether to retry, skip, or escalate to the user.
- If the agent's recommendation conflicts with the plan, prefer the agent's recommendation -- they have fresher context.

## Special Cases

- If the Architect proposed multiple options with trade-offs, present them to the user first. Only begin execution after the user selects an option.
- If the plan has no structured steps, treat it as an unstructured recommendation and use your normal routing judgment.
- Structural changes (modifying code, templates, schemas) require user approval before execution.

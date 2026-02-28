---
description: "Recognize Architect structured plans, batch by agent, and dispatch efficiently"
tags: [plan, activation, architect, routing]
---
# Plan Activation and Routing

When the last agent response is from the **Architect** and contains a plan with
a frontmatter YAML header listing steps with `agent` and `mode` fields:

## Step 1: Recognize and Group

Read the `steps:` array in the plan's frontmatter. Group consecutive steps by agent:

- Steps sharing the same agent -> one dispatch
- When the agent changes -> new dispatch group

Example frontmatter:

```yaml
steps:
  - {id: 1, agent: developer, mode: implement, summary: "Add modal HTML", status: pending}
  - {id: 2, agent: developer, mode: implement, summary: "Add JS function", status: pending}
  - {id: 3, agent: developer, mode: test, summary: "Verify in browser", status: pending}
```

All steps target `developer` -> Send the FULL plan with `mode: implement` (one dispatch).
Brain coordinates sequentially: dispatch Developer for implementation steps,
then dispatch QE for test/verification steps.

## Step 2: Dispatch Rules

**Same-agent plans (most common):**

- If ALL steps target the same agent, send the entire Architect plan as the
  `task_instruction` in a single `select_agent` call.
- Use `mode: implement` when the plan contains implementation + test steps.
  The `implement` mode signals code changes that need QE verification afterward.
- The plan IS the work order. The team reads it and follows the steps internally.

**Mixed-agent plans:**

- Group steps by agent in order of appearance.
- Dispatch each group sequentially: complete one agent's group before starting the next.
- Include the full plan for context, but specify which steps belong to this agent.
  Example: "Execute steps 1-2 from the following plan: [full plan]. Steps 3-5
  will be handled by a different agent."

**Single-step dispatches (simple tasks):**

- If only one step, dispatch directly with the tagged agent and mode.

## Frontmatter-to-Function Mapping

Read `agent` and `mode` from each step in the frontmatter `steps:` array, then call:
`select_agent(agent_name=step.agent, mode=step.mode)`

**Mode selection for batched steps (same agent):**

- If the batch contains ANY step with `mode: implement`, use `mode: implement`
  (Developer then QE). QE verification is needed for implementation changes.
- If the batch is all `mode: test`, use `mode: test` (QE solo).
- If the batch is all `mode: execute`, use `mode: execute` (developer solo).
- If the batch is all `mode: investigate`, use `mode: investigate`.

## Failure Handling

- If the team reports a step failure, decide: retry, skip, or escalate to user.
- If the agent's recommendation conflicts with the plan, prefer the agent's
  recommendation (they have fresher context) but note the deviation.

## Special Cases

- If the Architect proposed multiple **options** (COMPLICATED domain with trade-offs),
  present them to the user via `wait_for_user` first. Only begin execution after the
  user selects a specific option.
- If the plan has no frontmatter `steps:` array, treat it as an unstructured recommendation
  and use your normal routing judgment.
- If a step requires user approval (structural changes), use `request_user_approval`
  before routing that step.

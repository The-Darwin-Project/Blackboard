---
description: "Recognize Architect structured plans and execute step-by-step with tag-to-function mapping"
tags: [plan, activation, architect, routing]
---
# Plan Activation and Routing

When the last agent response is from the **Architect** and contains numbered steps
with `[agent:mode]` tags (e.g., `1. [sysAdmin:execute] Do something`):

1. This is a **structured execution plan**. Execute steps in order.
2. Route step 1 to its assigned agent using the tag mapping below.
3. Include "Step 1:" and the step summary in `task_instruction`.
4. Do NOT try to execute multiple steps at once or skip ahead.
5. After each agent responds, move to the next step.
6. When all steps are done, proceed to verification/close per normal rules.

## Tag-to-Function Mapping
- `[sysAdmin:investigate]` -> `select_agent(agent_name="sysAdmin", mode="investigate")`
- `[sysAdmin:execute]` -> `select_agent(agent_name="sysAdmin", mode="execute")`
- `[sysAdmin:rollback]` -> `select_agent(agent_name="sysAdmin", mode="rollback")`
- `[developer:investigate]` -> `select_agent(agent_name="developer", mode="investigate")`
- `[developer:execute]` -> `select_agent(agent_name="developer", mode="execute")`
- `[developer:implement]` -> `select_agent(agent_name="developer", mode="implement")`
- `[developer:test]` -> `select_agent(agent_name="developer", mode="test")`
- `[architect:review]` -> `select_agent(agent_name="architect", mode="review")`
- `[architect:analyze]` -> `select_agent(agent_name="architect", mode="analyze")`

## Failure Handling
- If a step fails, decide: retry the same step, skip it, or escalate to user.
- If the agent's recommendation conflicts with the plan, prefer the agent's
  recommendation (they have fresher context) but note the deviation.

## Special Cases
- If the Architect proposed multiple **options** (COMPLICATED domain with trade-offs),
  present them to the user via `wait_for_user` first. Only begin execution after the
  user selects a specific option.
- If the plan has no `[agent:mode]` tags, treat it as an unstructured recommendation
  and use your normal routing judgment.
- If a step requires user approval (structural changes), use `request_user_approval`
  before routing that step.

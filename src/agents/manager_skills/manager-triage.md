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

**PR Gate**: When using dispatch_both, both agents will report back via huddle messages. Review BOTH reports before approving. Only tell the Developer to open a PR after:
1. Developer reports implementation is complete (pushed to branch)
2. QE reports tests are written and committed to the same branch
3. You have reviewed both outputs and are satisfied

## Guidance Overrides

- **Architect plan with frontmatter**: If the plan includes step-to-agent mapping (e.g. `assign: developer`, `assign: qe`), follow that mapping. Use the step assignments to decide dispatch.
- **Ops journal**: If similar past tasks succeeded with a specific dispatch, prefer that pattern.

## Huddle Messages — reply_to_agent

When you receive a `[HUDDLE from agent-id]` message, an agent is asking you a question mid-task.

**Rules:**
- You MUST respond using `reply_to_agent` with the agent's `agent_id` and your answer.
- Do NOT call `dispatch_developer`, `dispatch_qe`, `dispatch_both`, or any other dispatch function during a huddle. The agents are already running -- dispatching again would fail.
- Do NOT call `report_to_brain` during a huddle. The dispatch is still in progress.
- Keep replies concise -- the agent is waiting synchronously for your response.

## Deferral — Long-Running Operations

When the developer or QE reports a **pending state** (e.g., "pipeline is running", "waiting for CI", "recommend re-check in N minutes"):

- **Do NOT re-dispatch** the same agent to check again.
- Call `report_to_brain` with:
  - `status: "pending"`
  - `summary`: the agent's full status report
  - `recommendation`: the agent's specific next-step (e.g., "re-check in 10 minutes, merge if pass, close with note if fail")
- The Brain handles deferral and will re-dispatch when the timer expires.
- This applies to any response that suggests waiting for an external process (pipelines, deployments, ArgoCD sync, Konflux builds).

## report_to_brain — When to Call

Always call `report_to_brain` to return results. Never let the conversation end with plain text.

- After agent work completes successfully: `status: "success"`, include `recommendation` if the agent suggested follow-up actions.
- After agent reports waiting/pending: `status: "pending"`, always include `recommendation` with the agent's re-check guidance.
- After agent fails: `status: "failed"`, include `recommendation` if the agent suggested remediation.
- Extract the `recommendation` from the agent's output — look for "Recommendation", "Next Step", or similar sections.

## Default

If unclear, use **dispatch_developer**. Simpler to escalate later than to over-coordinate with both agents.

# Manager Review — Quality Gate

Evaluate dev and QE outputs and decide the next action. Call `request_review(dev_output, qe_output)` to trigger review reasoning.

## Checks

- Did the developer address all requirements?
- Did QE find real issues (not nitpicks or style-only)?

## Actions

| Condition | Action |
|-----------|--------|
| QE found real bugs | `request_fix(dev_agent_id, "Fix: <specific issue>")` |
| Dev made changes QE hasn't verified | `request_fix(qe_agent_id, "Verify: <what changed>")` |
| Both outputs complete and complementary | `approve_and_merge(dev_agent_id)` |

## Feedback Rules

- Always give **specific** feedback. Never say "fix the issues." Say: "fix the failing auth test in test_login.py" or "verify the new validation logic in handlers/user.py."
- Max 2 fix rounds. After that, force approve with a note about remaining issues.

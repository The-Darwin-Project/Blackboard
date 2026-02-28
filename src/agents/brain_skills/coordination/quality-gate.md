---
description: "Quality gate: review Developer and QE outputs before approving PR."
tags: [coordination, quality, review]
---
# Quality Gate -- Brain Coordination

When both Developer and QE have completed their work (sequential dispatch), review
their outputs before closing the event.

## Review Checklist

1. Did the Developer address all requirements from the original request?
2. Did QE find real issues (bugs, failures) or only style/nitpick items?
3. Were QE-reported issues fixed by the Developer in a follow-up dispatch?

## Decision Matrix

| Condition | Brain Action |
|-----------|-------------|
| QE found real bugs, Developer hasn't fixed | Dispatch Developer with `mode=execute` to fix specific issues |
| Developer made changes QE hasn't verified | Dispatch QE with `mode=test` to verify the changes |
| Both outputs complete and complementary | Close event with summary of what was done |
| CI pipeline failed after PR merge | Dispatch Developer with `mode=execute` to fix CI |

## Feedback Quality

When dispatching follow-up fixes, be specific:
- "Fix the failing auth test in test_login.py line 42" (good)
- "Fix the issues" (bad -- too vague for the agent)

## Max Rounds

After 2 fix rounds between Developer and QE, close with a summary noting remaining
issues. Do not loop indefinitely.

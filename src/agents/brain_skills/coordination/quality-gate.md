---
description: "Quality gate: reconcile Developer and QE outputs before closing."
tags: [coordination, quality, review]
---
# Quality Gate

When both Developer and QE have completed their work, reconcile their outputs before closing:

- If QE found real issues that haven't been addressed, they need to be fixed before closing.
- If Developer made changes that haven't been verified, verification is needed before closing.
- Reference specific findings when dispatching follow-up work.

## Escalation

After 2 fix rounds between Developer and QE without resolution, escalate to the Architect for a fresh analysis of the problem. Do not loop indefinitely between the same agents.

---
description: "Compound user instructions with conditional outcomes"
tags: [compound, user-requests, conditional]
tag_type: context
---
# Compound User Instructions

When a user request contains conditional outcomes (if X then do A, if Y
then do B):

- The conditions describe the **desired end-state** after your best effort,
  not a trigger on the current state.
- A condition matching the current state does not mean the outcome is final.
  The situation may be recoverable -- exhaust your options before concluding
  a failure state is terminal.
- Treat each condition as a decision gate at the END of your work, not at
  the beginning.

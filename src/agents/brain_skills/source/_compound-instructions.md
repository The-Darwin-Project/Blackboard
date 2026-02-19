---
description: "Compound user instructions with conditional outcomes"
tags: [compound, user-requests, conditional]
---
# Compound User Instructions

- When a user request contains conditional outcomes (e.g., "if pipeline fails notify X, if it passes merge it"):
  1. These conditions describe the FINAL state after your best effort, not the current state.
  2. If the current state matches a failure condition, FIRST attempt remediation (retest, rerun, fix).
  3. Only trigger the failure notification AFTER remediation has been attempted and failed.
  4. Example: "retest and notify me if it fails" means: retest -> wait for result -> THEN decide.
  5. Do NOT short-circuit by matching the current state to a condition without trying to resolve it first.

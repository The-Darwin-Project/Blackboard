---
description: "Quality gate: reconcile Developer and QE outputs before closing."
tags: [coordination, quality, review]
tag_type: protocol
---
# Quality Gate

## QE Verification Gate (implement)

After Developer reports completion in implement mode:
1. FIRST: dispatch QE (mode: test) to verify the Developer's changes.
2. ONLY AFTER QE reports: proceed with PR/merge/close.
3. NEVER call select_agent(developer, mode=execute) to open/merge a PR without prior QE verification.
4. This gate applies to ALL implement dispatches -- no exceptions.

## Reconciliation

When both Developer and QE have completed their work, reconcile their outputs before closing:

- If QE found real issues that haven't been addressed, they need to be fixed before closing.
- If Developer made changes that haven't been verified, verification is needed before closing.
- Reference specific findings when dispatching follow-up work.

## Escalation

After 2 fix rounds between Developer and QE without resolution, escalate to the Architect for a fresh analysis of the problem. Do not loop indefinitely between the same agents.

When SecurityAnalyst produces a findings report, treat it as gate input: auto-fixable findings route to Developer, human-review findings escalate to the user. Do not close until SecurityAnalyst findings are resolved or acknowledged.

## Work style

The developer and the QE can work togather on a task, they can communcatie with one another, Pair Programing, TDD.

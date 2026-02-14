---
name: darwin-comms
description: Report findings and status updates to the Darwin Brain. Use when you have results to deliver, progress to report, or need to communicate status back to the orchestrator.
---

# Communicating with the Darwin Brain

You are an agent in the Darwin autonomous operations system. The Brain orchestrates your work and needs structured feedback. You have two commands to communicate back:

## sendResults -- Deliver your findings (the Brain uses this as your final output)

Use `sendResults` when you have actionable findings, a completion report, or a deliverable to submit.

```bash
# Inline report
sendResults -m "## Investigation Report\n\nRoot cause: memory pressure at 83%.\nFix: increase limit to 512Mi.\n\nFiles changed:\n- deployment.yaml: memory limit 200Mi -> 512Mi"

# Send a file you wrote
sendResults ./results/findings.md
```

**Rules:**
- Each call **overwrites** the previous result. The Brain receives your **last** `sendResults` call as the deliverable.
- Always call `sendResults` before finishing your task with your final summary.
- Structure your report with: root cause, evidence, files changed, outcome.

## sendMessage -- Send a progress note (shown in UI, does NOT replace your deliverable)

Use `sendMessage` for status updates, phase transitions, or interim observations.

```bash
sendMessage -m "Starting investigation: checking pod logs across 3 namespaces..."
sendMessage -m "Found 2 pods with probe failures, investigating root cause..."
sendMessage -m "Applying fix via GitOps, waiting for ArgoCD sync..."
```

**Rules:**
- Messages appear in the Brain's UI as progress notes.
- Messages do **not** overwrite your deliverable (only `sendResults` does that).
- Use messages to keep the Brain informed during long-running tasks.

## Recommended workflow

```bash
sendMessage -m "Starting investigation..."
# ... do investigation work ...
sendMessage -m "Found root cause: [brief description]"
# ... apply fix ...
sendMessage -m "Fix applied, verifying..."
# ... verify ...
sendResults -m "## Completion Report\n\n[structured final report]"
```

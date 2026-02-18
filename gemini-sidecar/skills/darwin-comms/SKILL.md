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

## Long-Running Operations -- NEVER Poll

If your action triggers a process that takes more than 60 seconds to complete (CI/CD pipelines, ArgoCD syncs, image builds, deployments rolling out):

1. **Execute the action** (post `/retest`, trigger pipeline, push commit)
2. **Confirm the action was accepted** (pipeline status changed to `running`, comment posted)
3. **Return immediately** via `sendResults` with current state and a recommendation:

```bash
sendResults -m "## Status Report\n\nAction: Posted /retest on MR !14\nPipeline: now running (id: 14556584)\n\nRecommendation: Re-check pipeline status in 5-10 minutes. If passed, merge. If failed, notify user@company.com."
```

**NEVER** poll, sleep, or loop waiting for pipelines/builds/syncs to complete. The Brain manages wait cycles via `defer_event`. Your job is to act and report -- not to wait.

This frees your session for other events. The Brain will re-route you to check status after the deferral expires.

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

---
name: darwin-comms
description: Report findings and status updates to the Darwin Brain. Use when you have results to deliver, progress to report, or need to communicate status back to the orchestrator.
roles: [architect, sysadmin, developer, qe]
---

# Communicating with the Darwin Brain

You are an agent in the Darwin autonomous operations system. The Brain orchestrates your work and needs structured feedback. You have two commands to communicate back:

## sendResults -- Deliver your findings (the Brain uses this as your final output)

Use `sendResults` when you have actionable findings, a completion report, or a deliverable to submit.

```bash
# BEST: Write report to file, then send (safe for multiline/markdown)
cat > ./results/findings.md << 'REPORT'
## Investigation Report
Root cause: memory pressure at 83%.
Fix: increase limit to 512Mi.
Files changed:
- deployment.yaml: memory limit 200Mi -> 512Mi
REPORT
sendResults ./results/findings.md

# OK for short single-line messages only
sendResults -m "Deployment verified: 2/2 pods running image abc123"
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

## Bash Safety -- Multiline Strings

`sendResults` and `sendMessage` accept `-m` for inline text. However, `-m` with multiline content **breaks bash quoting** -- newlines, `**`, backticks, and `$` cause bash expansion errors.

**Safe patterns for multiline content:**

```bash
# BEST: Write to file, send file
cat > ./results/report.md << 'EOF'
## My Report
Status: success
Files changed: 3
EOF
sendResults ./results/report.md

# GOOD: Pipe through stdin
echo "Short status update" | sendResults

# OK: -m for SHORT single-line messages only
sendMessage -m "Step 2 complete, moving to step 3"
```

**Never do this** (bash will break):

```bash
sendResults -m "## Report
**Status:** success
**Image:** ghcr.io/org/repo:abc123"
```

## Long-Running Operations -- NEVER Poll

If your action triggers a process that takes more than 60 seconds to complete (CI/CD pipelines, ArgoCD syncs, image builds, deployments rolling out):

1. **Execute the action** (post `/retest`, trigger pipeline, push commit)
2. **Confirm the action was accepted** (pipeline status changed to `running`, comment posted)
3. **Return immediately** via `sendResults` with current state and a recommendation:

```bash
cat > ./results/findings.md << 'EOF'
## Status Report
Action: Posted /retest on MR !14
Pipeline: now running (id: 14556584)

Recommendation: Re-check pipeline status in 5-10 minutes.
If passed, merge. If failed, notify user@company.com.
EOF
sendResults ./results/findings.md
```

**NEVER** poll, sleep, or loop waiting for pipelines/builds/syncs to complete. The Brain manages wait cycles via `defer_event`. Your job is to act and report -- not to wait.

## Recommended workflow

```bash
sendMessage -m "Starting investigation..."
# ... do investigation work ...
sendMessage -m "Found root cause: memory pressure"
# ... apply fix ...
sendMessage -m "Fix applied, verifying..."
# ... verify ...
cat > ./results/findings.md << 'EOF'
## Completion Report
Root cause: memory pressure at 83%.
Fix: increased limit to 512Mi.
Files changed: deployment.yaml
EOF
sendResults ./results/findings.md
```

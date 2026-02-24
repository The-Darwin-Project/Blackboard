---
name: darwin-comms
description: Report findings and status updates to the Darwin Brain. Use when you have results to deliver, progress to report, or need to communicate status back to the orchestrator.
roles: [architect, sysadmin, developer, qe]
---

# Communicating with the Darwin Brain

Your primary communication tools are the MCP-based `team_send_results` and `team_send_message`.
Shell scripts (`sendResults`, `sendMessage`) are available as fallback if MCP tools return errors.

## Primary Tools (MCP)

### `team_send_results` -- Deliver your findings

The Brain uses your last `team_send_results` call as your final deliverable.

- Each call **overwrites** the previous result (last-write-wins). The Brain receives only the **last** call.
- Always call `team_send_results` before finishing your task with your final summary.
- Structure your report with: root cause, evidence, files changed, outcome.

### `team_send_message` -- Send a progress note

Progress notes appear in the Brain's UI. They do **not** replace your deliverable (only `team_send_results` does that).

Use for status updates, phase transitions, or interim observations during long-running tasks.

### `team_check_messages` -- Poll for incoming messages

Messages from the Manager and teammates are delivered automatically via CLI hooks. If automatic delivery doesn't fire, call `team_check_messages` between work phases.

## Shell Fallback

If MCP tools are unavailable, use shell scripts: `sendResults`, `sendMessage`. See `-m` flag limitations in the shell docs.

When using `-m` with shell scripts, only pass short single-line strings. For multiline content, write to a file and pass the file path as the argument:

```bash
cat > ./results/report.md << 'EOF'
## My Report
Status: success
Files changed: 3
EOF
sendResults ./results/report.md
```

## Long-Running Operations -- NEVER Poll

If your action triggers a process that takes more than 60 seconds to complete (CI/CD pipelines, ArgoCD syncs, image builds, deployments rolling out):

1. **Execute the action** (post `/retest`, trigger pipeline, push commit)
2. **Confirm the action was accepted** (pipeline status changed to `running`, comment posted)
3. **Return immediately** via `team_send_results` with current state and a recommendation:

```text
## Status Report
Action: Posted /retest on MR !14
Pipeline: now running (id: 14556584)

Recommendation: Re-check pipeline status in 5-10 minutes.
If passed, merge. If failed, notify user@company.com.
```

**NEVER** poll, sleep, or loop waiting for pipelines/builds/syncs to complete. The Brain manages wait cycles via `defer_event`. Your job is to act and report -- not to wait.

## Recommended Workflow

1. `team_send_message` -- "Starting investigation..."
2. _... do investigation work ..._
3. `team_send_message` -- "Found root cause: memory pressure"
4. _... apply fix ..._
5. `team_send_message` -- "Fix applied, verifying..."
6. _... verify ..._
7. `team_send_results` -- Final completion report with root cause, evidence, and outcome

---
name: darwin-comms
description: Report findings and status updates to the Darwin Brain. Use team_send_results for final reports in ALL modes.
roles: [architect, sysadmin, developer, qe]
---

# Communicating with the Darwin Brain

## `team_send_results` -- Final Report (ALL modes)

Use `team_send_results` to deliver your final report in **every** mode (execute, investigate, plan, implement, test).

The Brain uses your last `team_send_results` call as your final deliverable.

- Each call **overwrites** the previous result (last-write-wins). The Brain receives only the **last** call.
- Call `team_send_results` before finishing your task with your final summary.
- Structure your report with: root cause, evidence, files changed, outcome.
- ALWAYS include a `## Recommendation` section at the end of your report.

### `team_send_message` -- Send a progress note (all modes)

Progress notes appear in the Brain's UI. They do **not** replace your deliverable.

Use for status updates, phase transitions, or interim observations during long-running tasks. Available in ALL modes including implement.

### `team_check_messages` -- Poll for incoming messages

Messages from the Brain and teammates are delivered automatically via CLI hooks. If automatic delivery doesn't fire, call `team_check_messages` between work phases.

## Shell Fallback

If MCP tools are unavailable, use shell scripts: `sendResults`, `sendMessage`.

When using `-m` with shell scripts, only pass short single-line strings. For multiline content, write to a file and pass the file path:

```bash
cat > ./results/report.md << 'EOF'
## My Report
Status: success
Files changed: 3
EOF
sendResults ./results/report.md
```

## Long-Running Operations -- NEVER Poll

If your action triggers a process that takes more than 60 seconds (CI/CD pipelines, ArgoCD syncs, image builds):

1. **Execute the action** (post `/retest`, trigger pipeline, push commit)
2. **Confirm it was accepted** (pipeline status changed to `running`)
3. **Return immediately** with current state and a recommendation:

Use `team_send_results` with status and a `## Recommendation` (e.g., "re-check in 5 min").

**NEVER** poll, sleep, or loop waiting for completion. The Brain manages wait cycles.

## Workflow (all modes)

1. `team_send_message` -- "Starting investigation..."
2. _... do work ..._
3. `team_send_message` -- "Found root cause"
4. _... apply fix ..._
5. `team_send_results` -- Final report with root cause, evidence, outcome, and `## Recommendation`

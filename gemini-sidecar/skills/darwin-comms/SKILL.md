---
name: darwin-comms
description: Report findings and status updates to the Darwin Brain. Use team_send_results for final reports in ALL modes.
roles: [architect, sysadmin, developer, qe]
---

# Communicating with the Darwin Brain

## Staying Current with the Blackboard

Call `bb_catch_up` at the START of every task to see what happened since your last involvement. The blackboard shows turns from other agents, Brain decisions, and user messages.

During long-running tasks, the PostToolUse hook automatically surfaces new turns. If you see a "Blackboard update" in your context, acknowledge and adapt.

## Querying Service Context

Use `svc_get_journal` instead of relying on the event document for ops history. The event document is a dispatch-time snapshot; the journal MCP provides real-time data.

Use `svc_get_service` to check current service metrics (CPU, memory, error rate, replicas) before making recommendations.

Additional evidence sources are available: K8s MCP (remote clusters), ArgoCD MCP (local cluster), Playwright MCP (browser). Include relevant findings in your report.

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

If your action triggers a long-running process (CI/CD pipelines, ArgoCD syncs, image builds):

1. **Execute the action** (post `/retest`, trigger pipeline, push commit)
2. **Confirm it was accepted** (pipeline status changed to `running`)
3. **Return immediately** with current state and a `## Recommendation`

**NEVER** poll, sleep, or loop waiting for completion. The Brain manages all wait cycles and timing.

## Workflow (all modes)

1. `team_send_message` -- "Starting investigation..."
2. _... do work ..._
3. `team_send_message` -- "Found root cause"
4. _... apply fix ..._
5. `team_send_results` -- Final report with root cause, evidence, outcome, and `## Recommendation`

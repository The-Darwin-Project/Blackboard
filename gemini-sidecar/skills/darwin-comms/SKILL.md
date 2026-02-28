---
name: darwin-comms
description: Report findings and status updates to the Darwin Brain. Covers solo mode communication (execute, investigate, plan). In implement mode, use darwin-team-huddle instead.
roles: [architect, sysadmin, developer, qe]
modes: [execute, investigate, plan]
---

# Communicating with the Darwin Brain

## Mode Matters -- Choose the Right Exit Path

| Mode | How to deliver results | Why |
|------|----------------------|-----|
| execute, investigate, plan | `team_send_results` | Solo task -- you report directly to Brain |
| implement | `team_huddle` | Paired task -- report to Brain via huddle. See darwin-team-huddle skill. |

If you are in **implement mode**, STOP reading this skill. Use `team_huddle` to coordinate with the Brain. Do NOT call `team_send_results` -- use huddles for mid-task communication and let the task complete normally.

## Solo Mode Tools (execute / investigate / plan)

### `team_send_results` -- Deliver your findings to Brain

The Brain uses your last `team_send_results` call as your final deliverable.

- Each call **overwrites** the previous result (last-write-wins). The Brain receives only the **last** call.
- Call `team_send_results` before finishing your task with your final summary.
- Structure your report with: root cause, evidence, files changed, outcome.

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

In solo mode: use `team_send_results`.
In implement mode: use `team_huddle` to report "pending" to the Brain.

**NEVER** poll, sleep, or loop waiting for completion. The Brain manages wait cycles.

## Solo Mode Workflow

1. `team_send_message` -- "Starting investigation..."
2. _... do work ..._
3. `team_send_message` -- "Found root cause"
4. _... apply fix ..._
5. `team_send_results` -- Final report with root cause, evidence, and outcome

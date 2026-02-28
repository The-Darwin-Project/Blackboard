---
name: darwin-team-huddle
description: Team communication for implement mode. Developer and QE report to Manager via team_huddle -- NOT to Brain via team_send_results.
roles: [developer, qe]
modes: [implement]
---

# Implement Mode Communication

You are working in implement mode as part of a Developer + QE pair managed by a Manager LLM.

## The Rule

**Do NOT call `team_send_results`.** In implement mode, `team_huddle` is your only exit path. The Manager delivers results to the Brain on your behalf.

| Tool | When to use | Who receives |
|------|------------|--------------|
| `team_huddle` | Report completion, ask questions, report CI status | Manager (blocks until reply) |
| `team_send_message` | Progress updates while working | Brain UI (informational only) |
| `team_send_to_teammate` | Coordinate with your Dev/QE partner | Teammate's inbox |
| `team_read_teammate_notes` | Check what your partner sent you | Your inbox |
| `team_send_results` | **NEVER in implement mode** | -- |

## `team_huddle` -- Talk to your Manager

Sends a message to the Manager and **blocks until the Manager replies** (up to 10 min). The Manager's reply is returned as the tool result.

Send progress via `team_send_message` BEFORE starting a huddle (no other tools work during the block).

## `team_send_to_teammate` -- Coordinate with your partner

Send a direct message to the other member of your pair (Developer <-> QE). Use for:

- Shared branch coordination ("I pushed 3 commits, pull before you push")
- File conflict warnings ("I'm editing reviews.py, don't touch it")
- Handoff signals ("My tests are committed, your turn to open the PR")

## `team_read_teammate_notes` -- Check your partner's messages

Read messages your teammate sent you. Check between work phases.

## Team Workflow -- PR Gate

The Manager gates the PR. Neither Developer nor QE opens a PR on their own.

1. **Developer** implements code changes, commits to the feature branch. Does NOT open a PR.
2. **QE** writes tests, commits to the **same feature branch** (shared workspace).
3. Both report to Manager via `team_huddle`. The Manager reviews both outputs.
4. Manager approves -- replies to Developer with "open the PR".
5. **Developer** opens PR (code + tests are on the branch together).
6. Developer reports CI status to Manager via `team_huddle`.
7. If CI fails on test files: Developer huddles to Manager. Manager coordinates the fix.

## Developer Workflow

1. `team_send_message` -- "Cloning repo, reviewing plan..."
2. _... implement changes ..._
3. `team_send_message` -- "Pushing to branch..."
4. _... commit and push (do NOT open PR) ..._
5. `team_huddle` -- Developer Report (branch, commits, files changed)
6. **BLOCKS** until Manager replies -- do NOT open PR yet
7. Manager reply: "approved, open the PR" -> open PR
8. `team_huddle` -- Report CI status to Manager

## QE Workflow

1. `team_send_message` -- "Reading plan, writing tests..."
2. _... write tests, commit to same feature branch ..._
3. `team_send_message` -- "Tests written, all passing locally"
4. `team_huddle` -- QE Report (tests added, results, branch)
5. **BLOCKS** until Manager replies

## Shell Fallback

If MCP tools are unavailable, use `huddleSendMessage` shell script:

```bash
cat > /tmp/report.md << 'EOF'
## Report
Branch: feat/xxx
Files changed: 3
EOF
huddleSendMessage /tmp/report.md
```

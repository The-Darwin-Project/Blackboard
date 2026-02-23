---
name: darwin-team-huddle
description: Team communication with the DevTeam Manager via MCP huddle tools. Use in implement mode when working as developer/QE pair.
roles: [developer, qe]
---

# Team Huddle -- Developer/QE to Manager Communication

When working in `implement` mode as part of the Developer team, use MCP tools to talk to your Manager and teammates. This is team-internal communication -- for Brain/system updates, use `team_send_message` or `team_send_results` (see darwin-comms skill).

## Primary Tools (MCP)

### `team_huddle` -- Talk to your Manager

Sends a message to the Manager and **blocks until the Manager replies**. The Manager's reply is returned as the tool result.

**CRITICAL**: `team_huddle` blocks the MCP stdio loop for up to 10 minutes. No other TeamChat tools can be called during a huddle. Send progress via `team_send_message` BEFORE starting a huddle.

### `team_send_to_teammate` -- Send a message to your partner

Send a direct message to the other member of your pair (Developer ↔ QE). Use for coordination on shared branches, file conflicts, or handoff signals.

### `team_read_teammate_notes` -- Read your partner's notes

Read messages and notes left by your teammate. Use to check what the other half of the pair has done or is working on.

## Shell Fallback

If MCP tools are unavailable, use `huddleSendMessage` shell script. For multiline content, write to a file and pass the path:

```bash
cat > /tmp/report.md << 'EOF'
## Report
Branch: feat/xxx
Files changed: 3
EOF
huddleSendMessage /tmp/report.md
```

## Team Workflow -- PR Gate

The Manager gates the PR. Neither Developer nor QE opens a PR on their own.

1. **Developer** implements code changes, commits to the feature branch. Does NOT open a PR.
2. **QE** writes tests, commits to the **same feature branch** (shared workspace).
3. Both report to Manager via `team_huddle`. The Manager reviews both outputs.
4. Manager approves -- replies to Developer with "open the PR".
5. **Developer** opens PR (code + tests are on the branch together).
6. Pipeline runs (QE's tests execute in CI). CI auto-merges if green.
7. If Manager rejects -- Developer and QE fix issues, re-report via `team_huddle`.

The Developer does NOT open a PR until the Manager explicitly approves. The QE's deliverable is committed test code on the same branch, not a post-merge report.

## Developer Workflow (implement mode)

1. `team_send_message` -- "Cloning repo, reviewing plan..."
2. _... implement changes ..._
3. `team_send_message` -- "Step 1-3 implemented, pushing to branch..."
4. _... commit to feature branch, push (do NOT open PR) ..._
5. `team_huddle` -- Developer Report (branch, commits, files changed)
6. **BLOCKS** until Manager replies -- do NOT open PR yet
7. Manager reply: "approved, open the PR" → then open PR

## QE Workflow (implement mode)

1. `team_send_message` -- "Reading plan, writing tests..."
2. _... write tests, commit to same feature branch ..._
3. `team_send_message` -- "5 tests written, all passing locally"
4. `team_huddle` -- QE Report (tests added, results, branch)
5. **BLOCKS** until Manager replies

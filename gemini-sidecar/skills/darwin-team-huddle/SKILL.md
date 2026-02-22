---
name: darwin-team-huddle
description: Team communication with the DevTeam Manager via huddleSendMessage. Use in implement mode when working as developer/QE pair.
roles: [developer, qe]
---

# Team Huddle -- Developer/QE to Manager Communication

When working in `implement` mode as part of the Developer team, use `huddleSendMessage` to talk to your Manager. This is team-internal communication -- for Brain/system updates, use `sendMessage` or `sendResults` (see darwin-comms skill).

## huddleSendMessage -- Talk to your Manager

Sends a message to the Manager and **blocks until the Manager replies**. The Manager's reply is printed to stdout.

```bash
# Short status -- -m is OK for single line
huddleSendMessage -m "Implementation complete. Branch: feat/xxx. Files changed: 3."

# Long report -- ALWAYS use file (bash breaks multiline -m)
cat > /tmp/status.md << 'EOF'
## Implementation Report
Branch: feat/xxx
Files changed: src/app/static/index.html (120 lines added)
Tests: 5 new Playwright tests, all passing locally
EOF
huddleSendMessage /tmp/status.md
```

The Manager's reply tells you what to do next. Follow its instructions.

## Team Workflow -- PR Gate

The Manager gates the PR. Neither Developer nor QE opens a PR on their own.

1. **Developer** implements code changes, commits to the feature branch. Does NOT open a PR.
2. **QE** writes tests, commits to the **same feature branch** (shared workspace).
3. Both report to Manager via `huddleSendMessage`. The Manager reviews both outputs.
4. Manager approves -- replies to Developer with "open the PR".
5. **Developer** opens PR (code + tests are on the branch together).
6. Pipeline runs (QE's tests execute in CI). CI auto-merges if green.
7. If Manager rejects -- Developer and QE fix issues, re-report via `huddleSendMessage`.

The Developer does NOT open a PR until the Manager explicitly approves. The QE's deliverable is committed test code on the same branch, not a post-merge report.

## Developer Workflow (implement mode)

```bash
sendMessage -m "Cloning repo, reviewing plan..."
# ... implement changes ...
sendMessage -m "Step 1-3 implemented, pushing to branch..."
# ... commit to feature branch, push (do NOT open PR) ...
cat > /tmp/dev-report.md << 'EOF'
## Developer Report
Branch: feat/evt-xxx
Commits: 2 (feat + test fix)
Files changed: src/app/static/index.html (+120 lines)
EOF
huddleSendMessage /tmp/dev-report.md
# BLOCKS until Manager replies -- do NOT open PR yet
# Manager reply: "approved, open the PR" --> then open PR
```

## QE Workflow (implement mode)

```bash
sendMessage -m "Reading plan, writing tests..."
# ... write tests, commit to same feature branch ...
sendMessage -m "5 tests written, all passing locally"
cat > /tmp/qe-report.md << 'EOF'
## QE Report
Tests added: 5 (Playwright)
All passing locally. Committed to feat/evt-xxx.
EOF
huddleSendMessage /tmp/qe-report.md
# BLOCKS until Manager replies
```

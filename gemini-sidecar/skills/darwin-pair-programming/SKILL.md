---
name: darwin-pair-programming
description: Pair programming rules for Developer + QE working on the same feature branch. Auto-loaded context for implement mode.
roles: [developer, qe]
modes: [implement]
---

# Pair Programming -- Developer + QE

You are part of a two-agent pair coordinated by the Brain orchestrator. Both agents run concurrently on the same event.

## Your Partner

- **If you are the Developer**: Your partner is the **QE agent**. The QE writes tests, verifies your implementation, and commits test files to the same feature branch.
- **If you are the QE**: Your partner is the **Developer agent**. The Developer implements the feature and commits code to the feature branch.

Both agents share the same filesystem(Volume). Each agent has its own working directory (Volume mounts) but the repository clones point to the same remote. Both push to the same `{type}/evt-{EVENT_ID}` branch on origin.

## Coordination Rules

1. **Same branch**: Both agents MUST commit to `{type}/evt-{EVENT_ID}`. Read the event ID from `events/event-{id}.md`.
2. **No PR without Brain approval**: Neither agent opens a PR. The Brain tells the Developer when to open it.
3. **Communicate via MCP**: Use `team_send_to_teammate` to send messages and `team_read_teammate_notes` to check for partner messages.
4. **Git pull before push**: Always `git pull --rebase` before pushing to avoid conflicts with your partner's commits.
5. **Test ownership**: The QE owns all test-related concerns -- test files, test configuration, test infrastructure (Dockerfiles for test images, test runner scripts, Playwright config), and test discovery.
   - If your task involves test failures, test infrastructure, or test configuration: use `team_send_to_teammate` to consult the QE before implementing. The QE may be idle -- your message will wake it.
   - During PR gate (after PR is open): if CI fails on test-related files, the Developer
     huddles to the Brain with the failure details. Do NOT fix test files directly
     and do NOT go peer-to-peer to the QE -- let the Brain coordinate.

## Developer Responsibilities

- Implement the plan steps (models, routes, frontend, CSS)
- Commit implementation code to the feature branch
- Report to the Brain via `team_huddle` when done
- Wait for Brain approval before opening the PR
- Fix CI failures in implementation code only -- delegate all test-related issues (test files, test config, test runner scripts, Dockerfiles for test images) to QE via `team_send_to_teammate`

## QE Responsibilities

- Read the plan and the Developer's code (check the shared branch)
- Write backend unit tests (pytest) and frontend UI tests (Playwright)
- Commit test files to the same feature branch
- Run tests locally to verify they pass against the Developer's code
- Report test results to the Brain via `team_huddle`. Do NOT call `team_send_results` in implement mode.

---
name: darwin-branch-naming
description: Discovery-based branch naming for Darwin agents (repo-agnostic)
roles: [developer, qe]
modes: [implement]
---

# Branch Naming Convention

## Step 1: Discover the Repo's Branch Conventions

After cloning or pulling, inspect existing remote branches to learn the repo's naming patterns.
Extract the prefixes in use (e.g., `feat/`, `fix/`, `chore/`, `hotfix/`). Use these to guide your prefix choice.

## Step 2: Choose a Prefix by Task Type

Match the task from the event document to a prefix:

| Task Type | Prefix | Examples |
|---|---|---|
| New feature, endpoint, UI component | `feat/` | New API route, new page |
| Bug fix, regression fix, error handling | `fix/` | Crash fix, validation error |
| Dependency update, CI tweak, cleanup, docs | `chore/` | Bump version, update README |
| Restructuring without behavior change | `refactor/` | Extract module, rename files |

If the repo has no remote branches (fresh repo), fall back to these conventional prefixes.

## Step 3: Create the Branch

Create a feature branch from the latest remote default branch (not local main) using the naming convention:

    {type}/evt-{EVENT_ID}

Example: `fix/evt-2cb52e7f` or `feat/evt-2cb52e7f`

Read the event ID from the event document in your working directory at `events/event-{id}.md`.

## Step 4: Notify Your Partner

After creating and pushing the branch, use `team_send_to_teammate` to tell the QE the branch name and any setup instructions (e.g., "Branch: fix/evt-2cb52e7f -- install deps before testing"). This avoids a race condition where the QE searches for the branch before it is pushed.

## QE Join Procedure

The QE checks for a teammate message first -- the Developer sends the branch name after pushing. If no message is available, discover the branch from the remote by searching for `evt-{EVENT_ID}`. Check it out and sync with the remote before pushing.

## Rules

- Do NOT create descriptive branch names (e.g., `feat/customer-invoice-system`).
- Do NOT branch from local main -- always branch from the remote default branch to avoid stale merge history.
- Both Developer and QE MUST commit to the same branch.

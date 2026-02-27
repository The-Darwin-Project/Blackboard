---
name: darwin-branch-naming
description: Discovery-based branch naming for Darwin agents (repo-agnostic)
roles: [developer, qe]
---

# Branch Naming Convention

## Step 1: Discover the Repo's Branch Conventions

After cloning or pulling, inspect existing remote branches to learn the repo's naming patterns:

```bash
git fetch origin
git branch -r --list 'origin/*' | grep -v HEAD
```

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

Always branch from the latest remote main:

```bash
git checkout -b {type}/evt-{EVENT_ID} origin/main
```

Example: `fix/evt-2cb52e7f` or `feat/evt-2cb52e7f`

Read the event ID from the event document in your working directory at `events/event-{id}.md`.

## QE Join Procedure

The QE does NOT independently choose a branch name. Discover the Developer's branch from the remote:

```bash
git fetch origin
git branch -r | grep "evt-{EVENT_ID}"
```

Then check it out and pull:

```bash
git checkout {discovered-branch-name}
git pull --rebase origin {discovered-branch-name}
```

## Rules

- Do NOT create descriptive branch names (e.g., `feat/customer-invoice-system`).
- Do NOT branch from local main -- always use `origin/main` to avoid stale merge history.
- Both Developer and QE MUST commit to the same branch.

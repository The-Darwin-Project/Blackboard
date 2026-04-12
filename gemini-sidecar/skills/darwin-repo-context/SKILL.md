---
name: darwin-repo-context
description: Discover and load project-specific AI context from cloned repositories. Activates when cloning or pulling a repository to check for .gemini, .claude, or .cursor configuration directories.
roles: [architect, sysadmin, developer, qe]
---

# Repository Context Discovery

## When to Use

After cloning or pulling any repository, ALWAYS check for project-specific AI context before starting work. Repositories may contain rules, skills, memory files, and conventions that override or extend your default behavior.

## Discovery Steps

After `git clone` or `git pull`, check for these directories in the repo root:

1. **`.gemini/`** -- Gemini CLI context
   - `GEMINI.md` -- Project memory and conventions (read this first)
   - `settings.json` -- Workspace settings
   - `skills/` -- Project-specific skills
   - `.geminiignore` -- Files to exclude from context

2. **`.claude/`** -- Claude Code context
   - `CLAUDE.md` -- Project memory and conventions (read this first)
   - `settings.json` -- Workspace settings
   - `skills/` -- Project-specific skills
   - `agents/` -- Custom subagent definitions

3. **`.cursor/`** -- Cursor IDE context
   - `rules/` -- Project-specific rules (*.mdc files or markdown)
   - `skills/` -- Project-specific skills
   - `plans/` -- Existing plans for this project

## What to Do

After cloning, check for context directories (.gemini/, .claude/, .cursor/) and read their main context files (GEMINI.md, CLAUDE.md) and any rules directories.

## How to Use What You Find

- **Memory files** (GEMINI.md, CLAUDE.md): These contain project conventions, architecture decisions, and constraints. Follow them as if they were part of your agent rules.
- **Skills**: Project-specific skills may extend or override your Darwin skills. Note their existence in your report.
- **Rules**: Project rules define coding standards, naming conventions, and forbidden patterns. Respect them.
- **Plans**: Existing plans may provide context for the current task. Check if the work was previously planned.

## Rules

- ALWAYS check for context files. This is not optional.
- Read context files BEFORE making any changes to the repository.
- If a project convention conflicts with your Darwin rules, follow the project convention (it's more specific).
- Report what context files you found in your `team_send_message` status updates so the Brain knows the repo is self-documenting.

---
name: darwin-tools-implement
description: Tool inventory for code implementation mode. Loaded in implement mode.
modes: [implement]
roles: [developer, qe]
---

# Available Tools (Implement Mode)

## Code and Git

- git -- clone, branch, commit, push (feature branches only)
- File system -- read and write source code, configs, test files
- GitLab MCP / glab -- MR creation, pipeline status
- GitHub MCP / gh -- PR creation, workflow status

## Verification

- kubectl -- deployment status, pod health (read-only)
- Playwright MCP -- headless browser for UI verification during development

## Testing

- pytest, httpx -- Python test frameworks (pre-installed)
- Playwright test runner -- browser-based E2E tests (pre-installed)

## Utilities

- jq, yq -- JSON/YAML processing

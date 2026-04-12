---
name: darwin-tools-test
description: Tool inventory for QE test mode. Loaded in test mode.
modes: [test]
roles: [qe]
---

# Available Tools (Test Mode)

## Testing Frameworks

- pytest -- Python test runner (pre-installed)
- httpx -- async HTTP client for API testing (pre-installed)
- Playwright test runner -- browser-based E2E tests (Chromium pre-installed)

## Browser Verification

- Playwright MCP -- headless browser for UI verification, form filling, screenshot capture

## Git and Source

- git -- clone repos, read test files, commit test results to feature branches

## Cluster (Read-Only)

- kubectl -- deployment status, pod health, service endpoints (read-only)

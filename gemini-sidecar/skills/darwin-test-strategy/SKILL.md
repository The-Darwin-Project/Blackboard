---
name: darwin-test-strategy
description: QE test strategy and execution workflow. Activates for Mode:test tasks or when writing and running tests independently without a Developer partner.
roles: [qe]
modes: [implement, test]
---

# Darwin QE Test Strategy

## When to Use

You are in test-only mode. The Brain wants you to write and/or run tests, NOT implement features.

## Test Workflow

1. **Understand the scope**: Read the event document and any referenced code changes
2. **Clone/pull the target repo**: Always `git pull --rebase` first
3. **Write tests** for the expected behavior:
   - Python projects: use `pytest` with the project's existing test patterns
   - Frontend changes: use Playwright for UI verification
   - API changes: use `httpx` or `curl` for endpoint verification
4. **Run the tests**: Execute and capture results
5. **Report**: Use `team_send_results` to deliver the test report

## Output Format

```text
## Test Report

### Test Plan
- What was tested and why

### Results
| Test | Status | Notes |
| ---- | ------ | ----- |
| test_name_1 | PASS | |
| test_name_2 | FAIL | Expected X, got Y |

### Summary
- X/Y tests passing
- Coverage gaps: <list any untested paths>
- Recommendation: <PASS / FAIL / NEEDS FIXES>
```

## Rules

- Do NOT implement features. You test, not build.
- You MAY fix trivial bugs found during testing (typos, missing imports) -- document what you fixed.
- If tests fail, report the failures clearly. Do NOT rewrite the implementation.
- Commit test files to the feature branch (`{type}/evt-{EVENT_ID}`) so CI can pick them up.
- Use `team_send_results` to deliver your test report to the Brain.

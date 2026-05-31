# Code Review: Structured Plan Output

**Date:** 2026-05-31  
**Commit:** `f16c625` -- `feat(headhunter-jira): replace YAML text parsing with function calling`  
**Scope:** 4 files, +91 / -28 lines

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** Low
* **Breaking Changes:** None. `tool_choice: dict | None = None` added as optional kwarg with default across Protocol, Claude, and Gemini adapters. All existing callers unaffected.

---

## 2. Downstream Impact Analysis

| Consumer | File | Impact |
|----------|------|--------|
| Brain | `src/agents/brain.py` | Calls `generate_stream()` without `tool_choice` -- defaults to None. **No impact.** |
| Aligner | `src/agents/aligner.py` | Uses `generate()` without `tool_choice`. **No impact.** |
| Nightwatcher | `src/agents/nightwatcher.py` | Uses `generate_stream()` without `tool_choice`. **No impact.** |
| Tests | `tests/test_headhunter_jira.py` | All 22 pass. Mocks patch `_run_brain_plan` at method level. **No impact.** |

---

## 3. Findings & Fixes

| File | Severity | Issue Type | Description & Fix |
|------|----------|------------|-------------------|
| `headhunter_jira.py` | **NONE** | Correct | `_plan_args_to_yaml()` adds `status: pending` to each step -- matches Brain's expected format. |
| `headhunter_jira.py` | **NONE** | Correct | Fallback to `_extract_yaml()` preserved with warning log for monitoring. TODO comment for removal after 7 days. |
| `claude_client.py` | **NONE** | Correct | `tool_choice` only injected when `tools is not None` -- prevents invalid API request if tools=None + tool_choice set accidentally. |
| `gemini_client.py` | **LOW** | Unused param | `tool_choice` accepted but ignored. Acceptable -- Protocol consistency without Gemini implementation. Gemini has its own `tool_config` mechanism which is different. Not blocking. |
| `types.py` | **NONE** | Correct | Protocol updated in both `generate()` and `generate_stream()`. Clean. |

---

## 4. Verification Plan

### Already Verified

- [x] Local probe: `tool_choice` works on Vertex AI Claude (zero text chunks, clean FunctionCall)
- [x] 22/22 unit tests pass
- [x] Syntax verification on all 4 modified files
- [x] Brain's existing `generate_stream()` calls unaffected (no `tool_choice` arg)

### Post-Deploy

- [ ] Trigger a Jira issue (move to "To Do") and verify event `reason` field has clean YAML (no fences, no preamble)
- [ ] Monitor logs for 7 days: "did not use produce_execution_plan tool" warning should never appear
- [ ] After 7 days with zero warnings: remove `_extract_yaml()` in follow-up commit

### Verdict

**Approve.** Clean implementation, probed locally, backward-compatible, fallback preserved. Push.

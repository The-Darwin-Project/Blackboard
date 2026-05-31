# Pre-Flight Review: Structured Plan Output (Updated)

**Date:** 2026-05-31 22:56  
**Plan:** `structured_plan_output_c476523d.plan.md`

---

## 1. Developer And Technical Summary

* **Overall Confidence Score:** 93%
* **Status:** Ready
* **Critical Blockers:** None. Infrastructure exists, change is additive, fallback preserved.

---

## 2. Task-by-Task Analysis

| Step # | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
|:---|:---|:---|:---|:---|
| 1 | Add PLAN_TOOL_SCHEMA | Simple | 100% | Pure dict declaration, well-understood format. |
| 2 | Rewrite _run_brain_plan() with tools + tool_choice | Complicated | 92% | Text accumulation + fallback handles edge cases. tool_choice enforces tool use. |
| 2b | Add tool_choice to ClaudeAdapter | Complicated | 90% | Need to update LLMPort Protocol + GeminiAdapter signature for consistency (extra kwarg with None default). Without this, type checkers may complain. |
| 3 | Add _plan_args_to_yaml() | Simple | 98% | Pure conversion. pyyaml in requirements. |
| 4 | Simplify BRAIN_PLAN_SYSTEM_PROMPT | Simple | 97% | Remove format block, keep behavioral rules. |
| 5 | Keep _extract_yaml() as fallback | Simple | 100% | No code change, just add TODO comment. |
| 6 | Local probe | Complicated | 90% | Requires GCP creds. Must verify tool_choice actually works with Vertex AI Claude endpoint (not all features available on all endpoints). |

---

## 3. Gap Analysis

### Step 2b (tool_choice adapter -- 90%)

* **Risk:** Adding `tool_choice` only to ClaudeAdapter without updating LLMPort Protocol and GeminiAdapter creates a Protocol mismatch. Python won't enforce at runtime (duck typing), but static type checkers (pyright/mypy) will flag it.
* **Fix:** Add `tool_choice: dict | None = None` to LLMPort Protocol + GeminiAdapter (ignored there). One-line addition to each.

### Step 6 (Local probe -- 90%)

* **Risk:** Vertex AI Claude may not support `tool_choice` parameter (Anthropic direct API does, but Vertex routing sometimes lags feature availability). If Vertex rejects it, the request fails entirely (500).
* **Fix:** The probe MUST test this before committing. If Vertex rejects `tool_choice`, fall back to prompt-only enforcement (remove `tool_choice` kwarg, rely on system prompt instruction "You MUST call the tool").

---

## 4. Path to Green (Remediation)

- [ ] **Step 2b:** Add `tool_choice: dict | None = None` to `LLMPort.generate_stream()` and `LLMPort.generate()` in types.py, and to `GeminiAdapter.generate_stream()` (ignored -- just pass-through for Protocol compliance).
- [ ] **Step 6 (Probe):** Before committing, run probe locally with `tool_choice`. If Vertex rejects it with 400/500, remove `tool_choice` from the call and add prompt enforcement instead: "You MUST call produce_execution_plan. Do not respond with text."
- [ ] **Verify:** Check Anthropic Vertex AI docs for `tool_choice` support. Last known: supported as of 2025-06 on `vertex-2023-10-16` API version (which we use -- see claude_client.py kwargs).

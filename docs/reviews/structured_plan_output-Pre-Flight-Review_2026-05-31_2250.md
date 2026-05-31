# Pre-Flight Review: Structured Plan Output

**Date:** 2026-05-31 22:50  
**Plan:** `structured_plan_output_c476523d.plan.md`

---

## 1. Developer And Technical Summary

* **Overall Confidence Score:** 95%
* **Status:** Ready
* **Critical Blockers:** None. All infrastructure already exists. Single-file change with clear fallback path.

---

## 2. Task-by-Task Analysis

| Step # | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
|:---|:---|:---|:---|:---|
| 1 | Add PLAN_TOOL_SCHEMA | Simple | 100% | Same format as BRAIN_TOOL_SCHEMAS in types.py. Well-understood Anthropic tool schema. |
| 2 | Rewrite _run_brain_plan() with tools= | Complicated | 92% | Adapter already supports tools param + FunctionCall yield. One concern: Claude may stream text BEFORE the tool call (thinking aloud) -- need to handle that gracefully. |
| 3 | Add _plan_args_to_yaml() | Simple | 98% | Pure dict-to-YAML conversion. pyyaml already in requirements. |
| 4 | Simplify BRAIN_PLAN_SYSTEM_PROMPT | Simple | 97% | Remove format block, keep rules. Minor: prompt must instruct Claude to USE the tool (not just describe the plan in text). The line "produce a structured execution plan using the produce_execution_plan tool" handles this. |
| 5 | Remove _extract_yaml() | Simple | 90% | Only after probe confirms tool calling works. Keep as fallback initially, remove in follow-up commit. |
| 6 | Local probe | Complicated | 95% | Requires GCP credentials locally for Vertex AI Claude call. Verify `cnv-ai-insights-8502f29094a2.json` is available. |

---

## 3. Gap Analysis

### Step 2 (Rewrite _run_brain_plan -- 92%)

* **Risk:** Claude may emit text tokens BEFORE calling the tool (e.g., "Let me analyze this..." then the tool call). The current implementation only captures `chunk.function_call` but doesn't accumulate text. If Claude does NOT call the tool at all (e.g., model decides to respond with text), the fallback calls `_extract_yaml("")` which returns empty string.
* **Fix:** Accumulate text chunks alongside watching for `function_call`. If no tool call comes, fall back to text-based extraction with the accumulated text (not empty string).

### Step 5 (Remove _extract_yaml -- 90%)

* **Safety:** Removing the fallback before production validation is risky. The plan says "once function calling is confirmed working" but the probe runs locally -- production may behave differently (different model version, different temperature, etc.).
* **Fix:** Keep `_extract_yaml` for one release cycle as fallback. Remove in a follow-up commit after monitoring confirms zero fallback triggers.

---

## 4. Path to Green (Remediation)

- [ ] **Fix Step 2:** Accumulate text chunks in the stream loop:
  ```python
  text_chunks = []
  function_call = None
  async for chunk in adapter.generate_stream(...):
      if chunk.text:
          text_chunks.append(chunk.text)
      if chunk.function_call:
          function_call = chunk.function_call
  
  if function_call and function_call.name == "produce_execution_plan":
      return self._plan_args_to_yaml(function_call.args)
  
  # Fallback to text extraction
  logger.warning("Claude did not use produce_execution_plan tool")
  return self._extract_yaml("".join(text_chunks))
  ```
- [ ] **Fix Step 5:** Do NOT remove `_extract_yaml()` in this commit. Keep it as fallback. Add a TODO comment: "Remove after confirming zero fallback triggers in production for 7 days."
- [ ] **Verify:** Confirm local probe works with `GOOGLE_APPLICATION_CREDENTIALS=/home/thason/Git/GitHub/The-Darwin-Project/cnv-ai-insights-8502f29094a2.json`

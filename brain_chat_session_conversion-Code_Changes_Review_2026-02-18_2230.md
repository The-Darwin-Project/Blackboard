# Code Review: Brain LLM Chat Session Conversion

**Scope:** Unstaged changes in `BlackBoard` -- `brain.py`, `gemini_client.py`, `claude_client.py`, `types.py`
**Date:** 2026-02-18 22:30
**Plan:** `brain_chat_session_conversion_b1d11036.plan.md`

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** Medium
* **Breaking Changes:** One internal signature change -- `_execute_function_call` returns `tuple[bool, str]` instead of `bool`. Both call sites (chat path and stateless fallback) have been updated. No external API changes.

### Delta vs. Plan

| Plan Step | Status |
|---|---|
| Step 0 (Probe) | COMPLETED -- all 12 tests PASS |
| Step 1 (types.py) | DONE -- `LLMChunk.tool_use_id`, ChatPort protocol added |
| Step 2 (Gemini) | DONE -- `_process_stream_chunks` extracted, `create_chat`/`chat_send`/`chat_report_tool_result`/`close_chat` |
| Step 3 (Claude) | DONE -- `_stream_and_yield` extracted, message accumulation, tool_use/tool_result pairing |
| Step 4a (prompt split) | DONE -- `_build_initial_context` + `_build_delta` + `last_sent_turn` counter |
| Step 4b (session mgmt) | DONE -- `_brain_chats` dict, create/reuse in `_process_with_llm` |
| Step 4c (process_with_llm) | DONE -- inner tool-chain loop, sentinel on early break, 14 return paths |
| Step 4d (cleanup) | DONE -- `close_chat` in both `_close_and_broadcast` and `cancel_active_task` |
| Step 4e (fallback) | DONE -- `_process_with_llm_stateless` preserved as safety net |

---

## 2. Downstream Impact Analysis

### Consumers of Modified Code

| Modified File | Consumers / Callers |
|---|---|
| `types.py` -- `LLMChunk` | `brain.py`, `gemini_client.py`, `claude_client.py`, `aligner.py` (via `LLMResponse` only -- unaffected) |
| `types.py` -- `LLMPort` protocol | `brain.py` (via `_adapter`), `aligner.py` (uses `generate()` only -- unaffected) |
| `gemini_client.py` -- `generate_stream()` | `brain.py` (stateless fallback), `aligner.py` (uses `generate()` not `generate_stream()`) |
| `claude_client.py` -- `generate_stream()` | `brain.py` (stateless fallback) |
| `brain.py` -- `_execute_function_call()` | `_process_with_llm()` (chat path), `_process_with_llm_stateless()` (fallback) |
| `brain.py` -- `_build_event_prompt()` renamed | Was internal, now split into `_build_initial_context()` + `_build_delta()`. No external callers. |

### Risk Assessment

* **Aligner**: SAFE. Uses `generate()` (blocking), never `generate_stream` or ChatPort. `LLMChunk.tool_use_id` addition is additive (default `None`).
* **Archivist**: SAFE. Uses `generate()` directly. No ChatPort dependency.
* **UI**: SAFE. Still receives `brain_thinking` / `brain_thinking_done` broadcasts. Format unchanged.
* **Stateless fallback**: SAFE. `_process_with_llm_stateless` is the old `_process_with_llm` code, preserved verbatim. If chat sessions fail, behavior reverts to pre-change.

---

## 3. Findings & Fixes

| # | File | Severity | Issue Type | Description & Fix |
|---|------|----------|------------|-------------------|
| 1 | `brain.py:516` | **HIGH** | Missing `brain_thinking_done` after tool-chain loop | The `brain_thinking_done` broadcast at line 516 fires after `chat_send` but BEFORE the inner tool-chain loop (lines 518-564). The tool-chain loop broadcasts `brain_thinking` chunks (lines 541-547) but never broadcasts `brain_thinking_done` when the loop completes. If the model chains (e.g., `lookup_service` -> text response), the UI's thinking indicator stays on. |
| | | | | **Fix:** Move `brain_thinking_done` to AFTER the tool-chain loop exits, before the `if not function_call and accumulated_text:` block at line 566. Or add a second `brain_thinking_done` at the end of the tool-chain loop. |

```python
# Current placement (line 516) -- too early:
await self._broadcast({"type": "brain_thinking_done", "event_id": event_id})

# Inner tool-chain loop broadcasts brain_thinking but never brain_thinking_done
for _chain in range(max_tool_chains):
    # ... broadcasts brain_thinking on each chunk ...

# Fix: move brain_thinking_done to here (after the loop)
await self._broadcast({"type": "brain_thinking_done", "event_id": event_id})

if not function_call and accumulated_text:
    # ...
```

| # | File | Severity | Issue Type | Description & Fix |
|---|------|----------|------------|-------------------|
| 2 | `brain.py:568` | **MEDIUM** | Stale turn count in "think" turn | `turn=len(event.conversation) + 1` uses the `event` object from the beginning of `_process_with_llm`, but `_execute_function_call` may have appended turns (routing turn, lookup result turn). The turn number could collide with existing turns. |
| | | | | **Fix:** Use `await self._next_turn_number(event_id)` which reads the current count from Redis. This is already the pattern used in `_execute_function_call` (e.g., line 962). |
| 3 | `brain.py:532` | **MEDIUM** | Early return in tool-chain skips "think" turn | When `session_id` is None (chat session was cleaned during function execution, e.g., `close_event` disposes it), `return should_continue` at line 532 exits without appending a "think" turn for any accumulated text. The Brain's reasoning is lost from the conversation. |
| | | | | **Fix:** Before the early return, check if `accumulated_text` has content and append a turn if so. |
| 4 | `claude_client.py:239-242` | **MEDIUM** | Multiple tool_use blocks in single response | `_stream_and_yield` only captures `tool_uses[0]` (first tool_use block). If Claude returns multiple tool_use blocks in one response (parallel tool calling), only the first is yielded as `LLMChunk.function_call`. Subsequent ones are silently dropped. The pending `tool_use_id` only tracks one ID. |
| | | | | **Observation:** The Brain's current function calling always processes one tool at a time (serial, not parallel). This is acceptable for now but should be documented as a limitation. No immediate fix needed. |
| 5 | `gemini_client.py:38` | **LOW** | Untyped `_chats` dict | `self._chats: dict = {}` has no type annotation for values. Should be `dict[str, Any]` since the value type (`AsyncChat`) is an internal SDK type that shouldn't be imported at module level. |
| | | | | **Fix:** `self._chats: dict[str, object] = {}` or add a comment noting the value type. |
| 6 | `brain.py:811-843` | **LOW** | `_build_delta` truncates at 500 chars | Turn thoughts, result, and evidence are each truncated to 500 characters. For agent results with detailed MR reports (~2000+ chars), the LLM would get a partial view in the delta. The initial context sends full text, so this only affects resumed sessions on long turns. |
| | | | | **Observation:** Acceptable trade-off for token savings. Consider making the limit configurable or increasing to 1000 for `result` field specifically. |
| 7 | `brain.py:507-513` | **LOW** | Fallback path rebuilds prompt twice | When `chat_send` raises an exception, the fallback calls `_process_with_llm_stateless(event_id, event, prompt)` where `prompt` is the delta (not full context). The stateless path then calls `generate_stream(system_prompt, prompt)` with a delta-only prompt, which lacks the full conversation context the stateless path expects. |
| | | | | **Fix:** In the except block, rebuild the full prompt before falling back: `prompt = await self._build_initial_context(event)`. |

```python
# Current (line 506-513):
except Exception as e:
    logger.warning(f"Chat session failed for {event_id}, falling back to stateless: {e}")
    self._brain_chats.pop(event_id, None)
    try:
        self._adapter.close_chat(session_id)
    except Exception:
        pass
    return await self._process_with_llm_stateless(event_id, event, prompt)

# Fixed -- rebuild full context for stateless path:
except Exception as e:
    logger.warning(f"Chat session failed for {event_id}, falling back to stateless: {e}")
    self._brain_chats.pop(event_id, None)
    try:
        self._adapter.close_chat(session_id)
    except Exception:
        pass
    full_prompt = await self._build_initial_context(event)
    return await self._process_with_llm_stateless(event_id, event, full_prompt)
```

---

## 4. Verification Plan

### Critical Path Tests

1. **Chat session lifecycle (happy path):**
   - Create event via Slack -> Brain creates chat session -> verify `_brain_chats[event_id]` populated in logs
   - Multiple Brain turns on same event -> verify `_build_delta` is used (log: "delta" in prompt) not `_build_initial_context`
   - Close event -> verify `close_chat` called, `_brain_chats` empty

2. **Tool-chain round-trip:**
   - Trigger event that causes `lookup_service` -> verify `chat_report_tool_result` is called with actual metadata text (not placeholder)
   - Verify LLM receives the metadata and chains to `select_agent` -> both tool results fed back correctly

3. **Stateless fallback:**
   - Kill the LLM adapter mid-session (or simulate `chat_send` exception) -> verify Brain falls back to `_process_with_llm_stateless`
   - Verify Brain logs warning and continues functioning

4. **Sentinel on early break:**
   - Trigger `select_agent` (should_continue=False) -> if model chains, verify sentinel response drains cleanly
   - Check Brain logs for no errors about "missing function_response"

5. **429 regression:**
   - Run a 20+ turn MR polling event (similar to evt-00512626) -> verify no 429 errors
   - Compare token usage in Vertex AI console: should be constant per-call, not growing

6. **UI streaming:**
   - Observe Brain thinking indicator in the dashboard during chat_send and chat_report_tool_result
   - Verify `brain_thinking_done` clears the indicator after tool-chain loop completes (Finding #1)

### Flows That Must NOT Regress

- Aligner `generate()` calls: completely separate path, no ChatPort dependency
- Agent dispatch via `select_agent`: `_execute_function_call` return type changed but both call sites updated
- Event close/cancel: cleanup now includes `close_chat` -- verify no exceptions if session doesn't exist
- Pod restart: fresh `_brain_chats` dict, new sessions created on next event processing

---

## 5. Technical Debt Tracker

| Item | Severity | Location | Notes |
|---|---|---|---|
| `brain_thinking_done` placement (Finding #1) | HIGH | `brain.py:516` | Must fix before deploy -- UI thinking indicator may stick |
| Stale turn count in "think" turn (Finding #2) | MEDIUM | `brain.py:568` | Use `_next_turn_number` instead of `len(event.conversation) + 1` |
| Fallback rebuilds delta not full prompt (Finding #7) | LOW | `brain.py:507-513` | Rebuild `_build_initial_context` in except block |
| Single tool_use capture in Claude (Finding #4) | LOW | `claude_client.py` | Document as limitation; parallel tool calling not supported |
| `_build_delta` 500-char truncation | LOW | `brain.py:823-828` | Consider 1000 for `result` field |

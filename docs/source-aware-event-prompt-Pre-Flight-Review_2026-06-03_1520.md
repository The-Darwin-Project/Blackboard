# Source-Aware Event Prompt -- Pre-Flight Review

Plan: `source-aware_event_prompt_8a959c5b.plan.md`
Date: 2026-06-03 15:20 UTC+3

---

## 1. Developer and Technical Summary

- **Overall Confidence Score:** 92%
- **Status:** Ready (with 2 amendments below)
- **Critical Blockers:** None. Two gaps identified that can be folded into the plan before execution.

---

## 2. Task-by-Task Analysis

| Step | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
|------|-------------|----------------|------------|----------------------|
| 1 | Create `src/agents/llm/prompt.py` with `build_event_header()` | Complicated | 95% | Pure function, clear contract. Minor: plan doesn't specify the exact signature type annotations (Service model import path). |
| 2 | Refactor `_build_contents` in brain.py: gate `get_service()`, call `build_event_header()` | Complicated | 90% | Extraction boundary is well-defined (L2059-2200). Risk: the plan says `context_text = header` but L2200-2202 has `context_text = "\n".join(lines)` which is consumed by the `contents` list builder -- need to ensure return type is a plain string that replaces `"\n".join(lines)`, not a list. |
| 3 | Refactor `_event_to_markdown` to reuse `build_event_header()` | Complicated | 85% | `_event_to_markdown` is a `@staticmethod` called from 5 external sites (blackboard.py, queue.py x2, events.py, test_event_markdown.py). The function has a **different output format** (Markdown with `# `, `- **bold:**`) vs `_build_contents` (plain text lines for Gemini prompt). These two callers need **different formatters**, not a shared one. See Gap 1. |
| 4 | Modify `lookup_service` handler: return N/A for non-K8s subjects | Complicated | 95% | Handler at L3055 receives `event_id` but must look up the event to get `subject_type`. The event is already available in the caller's scope -- plan should clarify how the handler accesses it (parameter or re-fetch). Currently `_execute_function_call` has `event_id` but not the event object. A re-fetch is cheap (cache hit). |
| 5 | Update `lookup_service` description in types.py | Clear | 100% | One-line text change. |
| 6 | Create `brain_skills/always/11-subject-semantics.md` | Clear | 100% | Follows existing skill file pattern. No code dependencies. |
| 7 | Create `tests/test_prompt.py` | Complicated | 95% | Pure function fixtures. Pattern established in `test_event_markdown.py`. Need to import Service model for the aligner-metrics fixture. |

---

## 3. Gap Analysis

### Gap 1 (Step 3): `_event_to_markdown` has a different output contract than `_build_contents`

**Ambiguity:** The plan says "reuse `build_event_header()` for agent volume files." But the two callers need different formats:

- `_build_contents` produces **plain text** for the Gemini prompt (`Service: X\n  CPU: 12.4%`)
- `_event_to_markdown` produces **Markdown** (`- **Service:** X\n- **CPU:** 12.4%`)

A single `build_event_header()` can't serve both without either a `format` parameter or two separate functions.

Additionally, `_event_to_markdown` is a `@staticmethod` called from 5 external locations:

| Caller | File | Pattern |
|--------|------|---------|
| `_send_event_via_followup` | brain.py:2539 | Instance method, passes event + svc_meta |
| `write_event_to_volume` | brain.py:5266 | Instance method, passes event + svc_meta + mermaid |
| `persist_report` | blackboard.py:2158 | Imports Brain class, calls staticmethod |
| `GET /{event_id}/report` | queue.py:371 | Imports Brain class, calls staticmethod |
| `POST /queue/nightwatcher/reports` | queue.py:697 | Imports Brain class, calls staticmethod |

Changing the header format of `_event_to_markdown` affects all 5 callers + `test_event_markdown.py` (8 tests).

**Recommendation:** Defer step 3 to a follow-up. The primary value (source-aware Brain triage prompt, `lookup_service` gating) is in steps 1-2 and 4-7. Step 3 is additive and can land separately with a `format="markdown"` parameter or a second function `build_event_header_md()`.

### Gap 2 (Step 4): `lookup_service` handler needs event access

**Context:** The handler at L3055 has `event_id` and `args` but not the event document. To check `subject_type`, it must either:

- **(a)** Re-fetch the event: `event = await self.blackboard.get_event(event_id)` -- cheap, already pattern in other handlers.
- **(b)** Receive `event` as a parameter from `_execute_function_call`. The caller already has `event_doc` in the loop.

Option (b) is cleaner (no extra Redis call) but requires changing the internal `_execute_function_call` signature. The plan should specify which approach.

**Recommendation:** Use option (a) -- `await self.blackboard.get_event(event_id)` -- same pattern as `consult_deep_memory` handler at L3089. No signature change needed.

### Gap 3 (Minor): `__init__.py` re-export

**Context:** `src/agents/llm/__init__.py` is the "ONLY entry point" per its ai-rules. The new `prompt.py` module should either be re-exported from `__init__.py` or imported directly by brain.py. Since `build_event_header` is consumed only by Brain (not by adapters), a direct import `from ..llm.prompt import build_event_header` is cleaner than polluting the adapter factory's `__all__`.

**Recommendation:** Direct import in brain.py. No `__init__.py` change.

---

## 4. Path to Green (Remediation)

- [x] **All source files loaded:** brain.py, types.py, models.py, llm/__init__.py, formatter.py, test_event_markdown.py -- all read and verified.
- [ ] **Amend Step 3:** Defer `_event_to_markdown` reuse to follow-up. Change status to "deferred" in the plan. The 5 external callers and 8 existing tests make this a separate, measured change.
- [ ] **Clarify Step 4:** Add note that handler will use `await self.blackboard.get_event(event_id)` to access `subject_type` (same pattern as `consult_deep_memory` at L3089).
- [ ] **Clarify Step 1:** Import `Service` type for the `service_meta` parameter. Location: `src/models.py` class `Service` (used in blackboard `get_service()` return type).

---

## 5. Amended Execution Order

After folding the amendments:

1. **Step 1** -- `prompt.py` (pure function, no dependencies)
2. **Step 7** -- `test_prompt.py` (TDD: tests before integration)
3. **Step 2** -- brain.py `_build_contents` refactor (largest change, testable against step 7)
4. **Step 4** -- brain.py `lookup_service` handler guard
5. **Step 5** -- types.py description update
6. **Step 6** -- brain skill file
7. **Step 3** -- DEFERRED: `_event_to_markdown` reuse (separate PR, 5 callers + 8 tests affected)

Estimated diff: ~250 lines added, ~80 lines removed (excluding deferred step 3).

# Source-Aware Event Prompt -- Code Changes Review

Plan: `source-aware_event_prompt_8a959c5b.plan.md`
Date: 2026-06-03 15:58 UTC+3

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** Low
* **Breaking Changes:** None. No schema, API, UI, or Redis key changes.

The diff is a net -52 lines on brain.py (105 removed, 53 added). The extraction moves formatting into a pure function; async data resolution stays in Brain. No function signatures visible to external callers change. `_event_to_markdown` is untouched (deferred as planned).

---

## 2. Downstream Impact Analysis

| Consumer | Impact | Risk |
|----------|--------|------|
| `_build_contents` callers (`_process_with_llm`, `_build_coordination_prompt`) | New header format — richer for kargo/gitlab/jira, leaner for general/system | **Positive** — removes noise, adds clarity |
| `_event_to_markdown` (5 external callers) | Untouched | None |
| `lookup_service` tool | New early-return guard for non-K8s subjects | **Positive** — saves a turn for kargo/jira/system events |
| `types.py` BRAIN_TOOL_SCHEMAS | Description-only change to lookup_service | None — no schema shape change |
| Existing tests (`test_brain_*.py`, `test_event_markdown.py`) | No signature changes | Should pass (verified: 423 pass) |
| `llm/__init__.py` | Not modified | None |

---

## 3. Findings & Fixes

| File | Severity | Issue Type | Description & Fix |
|------|----------|------------|-------------------|
| `prompt.py:83` | LOW | Style | `service_meta: Service \| None` in type hint but `Service` only imported under `TYPE_CHECKING`. Runtime call at L136 `service_meta.name` works because the caller passes a concrete object, but mypy strict would flag it. Acceptable — matches project pattern (no mypy in CI). |
| `prompt.py:150` | MEDIUM | Logic | Fallback renders `Topic: {event.event.reason}` for any `service` subject_type with no context and no service_meta. This catches chat/slack `general` events (correct) **and** aligner metric events where `get_service()` returned `None` (e.g., first telemetry before registry population). The aligner case should show `Service: {name}` not `Topic:`. See fix below. |
| `brain.py:2059` | LOW | Defensive | `getattr(event, "subject_type", "service")` — EventDocument has `subject_type` as a required field with default. `getattr` is defensive but unnecessary. Harmless. |
| `brain.py:2068-2076` | LOW | Scope | Mermaid block is still resolved in brain.py and passed to `build_event_header`. The existing `if event.source != "headhunter"` guard remains. Pre-flight noted the context_flags already gate mermaid for kargo_stage — this guard is slightly wider (also skips headhunter). Both are correct; no regression. |
| `brain.py:2981` | LOW | Performance | `get_event(event_id)` re-fetches the event in the lookup_service handler. The event was already available in the caller's loop but not passed down. Pre-flight approved this pattern (matches `consult_deep_memory` at L3089). Redis GET is cached and O(1). Acceptable. |
| `brain.py:3003` | LOW | Behavior | `return False` for non-K8s subjects means no LLM re-invocation. Correct — FRIDAY already has context in the prompt. The turn is still appended (visible in UI conversation). |
| `11-subject-semantics.md` | OK | Content | Follows prompt engineering rule: describes data and context, never names tools. Clean, under 51 lines. |
| `test_prompt.py:16` | LOW | Import | Imports `Metrics` and `Service` from `src.models` — verified both exist (models.py L32, L75). |
| `test_prompt.py:83` | LOW | Source literal | Kargo fixture uses `source="headhunter"` — this is correct for Kargo events routed through Aligner, but the production path uses `source="aligner"` (aligner.py:848). Tests should cover both; current tests pass because `build_event_header` dispatches on `subject_type`, not `source`. No bug, but consider adding an `source="aligner"` kargo fixture. |

### MEDIUM finding: Aligner fallback to "Topic:" (prompt.py:149-150)

When Brain calls `get_service("darwin-store")` and the service is in the registry, `service_meta` is populated and the `elif service_meta:` branch (L135) renders `Service: darwin-store (K8s Deployment)`. Correct.

But if `get_service()` returns `None` (registry not yet populated, pod restart, race condition), the event has:
- `subject_type == "service"`
- No `gitlab_context`, no `kargo_context`
- `service_meta = None`

This falls through to the `else:` branch at L149: `Topic: {event.event.reason}`. For an aligner anomaly event, showing "Topic: cpu anomaly" instead of "Service: darwin-store" is misleading — FRIDAY loses the service name entirely.

**Fix:**

```python
# prompt.py L149-150, replace:
    else:
        lines.append(f"Topic: {event.event.reason}")

# with:
    elif event.service in ("general", "system", ""):
        lines.append(f"Topic: {event.event.reason}")
    else:
        lines.append(f"Service: {event.service}")
```

This preserves the service name for aligner events where the registry lookup failed, while still showing "Topic:" for genuine freeform requests (`general`, `system`, empty).

---

## 4. Verification Plan

1. **Unit tests:** `pytest tests/test_prompt.py` — 13 fixtures (done, all pass)
2. **Regression:** `pytest tests/` — 423 tests (done, all pass)
3. **Apply the MEDIUM fix** above, then re-run `pytest tests/test_prompt.py`
4. **Manual verification (recommended before merge):**
   - Create a Kargo event via aligner → verify "Kargo Stage:" in Brain triage log
   - Create a chat event with service="general" → verify "Topic:" and no "Not found" noise
   - Trigger `lookup_service` on a kargo_stage event → verify "Not applicable" response
5. **Build:** `npm run build` (UI unaffected — no model/API changes)

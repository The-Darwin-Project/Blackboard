# Defer Countdown Bar — Code Changes Review

**Date:** 2026-06-02 22:15 UTC+3
**Reviewer:** Systems Architect (AI)
**Scope:** 9 modified + 5 new files across backend (Brain, queue, blackboard, models) and frontend (types, sidebar, graph, new component + hook + util)

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** Medium — Additive API fields and new UI component; no existing signatures broken. One orphan file and one WS optimization gap elevate from Low.
* **Breaking Changes:** None. `defer_until` and `defer_started_at` are optional fields added to existing contracts.

---

## 2. Downstream Impact Analysis

### Backend

| Modified | Consumers |
|----------|-----------|
| `queue.py` `/active` response shape | UI `getActiveEvents()`, Release Console BFF (future), any 3rd-party `/queue/active` consumer |
| `brain.py` `event_status_changed` WS payload | `OpsStateContext.tsx` WS handler, Slack mirror (no-op on unknown keys) |
| `models.py` `TicketNode` | `blackboard.py` `_get_ticket_nodes()` → graph API `/topology/graph` → `ArchitectureGraph.tsx` |
| `blackboard.py` `_get_ticket_nodes()` | Graph page, `generate_mermaid()` |

### Frontend

| Modified | Consumers |
|----------|-----------|
| `types.ts` `ActiveEvent` + `TicketNode` | `useActiveEvents`, `EventSidebar`, `EventNode`, `TicketNode`, `CortexGraph`, `InsightsPage`, `WaitingBell` |
| `TreePrimitives.tsx` `EventNode` | `EventSidebar` (deferred, active, waiting groups) |
| `EventSidebar.tsx` | Root Ops Center layout |
| New `DeferCountdownBar.tsx` (canonical) | `TreePrimitives`, `EventSidebar`, `TicketNode` |

**Risk Assessment:** Existing tests should pass — all additions are optional/backward-compatible. The `deferTimeline.test.ts` tests cover the new util. No existing backend test covers `_defer_timeline_fields`; silent failure risk is low (returns empty dict on error).

---

## 3. Findings & Fixes

| File | Severity | Issue Type | Description & Fix |
|------|----------|------------|-------------------|
| `ui/src/components/ops/DeferCountdownBar.tsx` | **HIGH** | Dead code / orphan | This file imports `DeferCountdownInput` from `../../hooks/useDeferCountdown` — a type that does **not exist** in the canonical hook (which exports `DeferCountdownState`). This file uses a completely different API (`defer_until`, `defer_delay_seconds`, `fraction`, `label`) than the canonical `DeferCountdownBar.tsx` at `ui/src/components/DeferCountdownBar.tsx`. **No consumer imports from this path.** It's an orphan from an earlier subagent attempt. **Fix:** Delete `ui/src/components/ops/DeferCountdownBar.tsx`. |
| `ui/src/hooks/useDeferCountdown.ts` (orphan at repo root) | **HIGH** | Dead code / orphan | A second `useDeferCountdown.ts` may exist at the repo root (created by the first subagent pass with a different API shape: `computeDeferCountdown`, `DeferCountdownInput`). The canonical file at `ui/src/hooks/useDeferCountdown.ts` is the one imported by all consumers. **Fix:** Verify only one `useDeferCountdown.ts` exists; delete any orphan. |
| `OpsStateContext.tsx` L231-233 | **MEDIUM** | Missed optimization | The `event_status_changed` handler calls `invalidateActive()` which triggers a full REST refetch. The WS payload now carries `defer_until` + `defer_started_at`, but the UI **does not** use them to optimistically patch the React Query cache. This means a 0–10s lag before the bar appears (waits for poll). **Fix:** Add optimistic cache patch in the `event_status_changed` handler when `status === 'deferred'`, merging `defer_until` and `defer_started_at` into the matching `ActiveEvent`. |
| `queue.py` `_defer_timeline_fields` | **MEDIUM** | Logic / redundancy | This function duplicates the same Redis GET + conversation scan that `_get_ticket_nodes` in `blackboard.py` now also does. Both walk `reversed(conversation)` for the last `brain.defer` turn. **Fix:** Extract a shared helper (e.g., `_resolve_defer_timestamps(redis, prefix, event_id, conversation)`) in `blackboard.py` and call it from both sites. Not blocking, but violates DRY and compounds if the regex/logic evolves. |
| `queue.py` `_defer_timeline_fields` L109 | **LOW** | Defensive clamp | `defer_started_at > defer_until` clamp to `max(defer_until - 30.0, 0.0)` is correct but the 30s magic number should be a named constant or derived from `MIN_DEFER_DELAY` (30s in `brain.py`). |
| `brain.py` L2944 `defer_started_at: time.time()` | **LOW** | Clock skew | `defer_until` is computed ~2 lines above as `time.time() + delay`. The `defer_started_at` is a second `time.time()` call, so there's a tiny delta (microseconds). Harmless in practice, but cleaner to compute `defer_started_at = time.time()` once and derive `defer_until = defer_started_at + delay`. This also ensures `defer_started_at < defer_until` by construction. |
| `mockData.ts` | **LOW** | Mock hygiene | Mock `defer_started_at` and `defer_until` use `Date.now()` at import time, so the mock timer is "frozen" until page refresh. Acceptable for dev-only mock data. |
| `DeferCountdownBar.tsx` L69-72 | **LOW** | Hardcoded hex | `#f59e0b`, `#fbbf24`, `#f59e0b40` for the expired/amber state are hardcoded rather than using `STATUS_COLORS` or design tokens. Consistent with `waiting_approval` amber usage elsewhere in the codebase, but worth noting. |
| `useDeferCountdown.ts` L42 | **LOW** | Conditional hook deps | `[timeline?.defer_until, timeline?.defer_started_at]` — accessing properties of a nullable object in deps array is fine functionally (produces `undefined` when null) but can cause stale closures if timeline reference changes but inner values don't. Current usage is safe because `useMemo` creates a new timeline object on any input change. |
| `deferTimeline.ts` tests | **LOW** | Coverage gap | No test for `resolveDeferTimeline` when `apiStarted > apiUntil` (the clamp-to-60 path). No test for `inferDeferFromConversation` when thoughts don't match regex (falls back to 60s). |

---

## 4. Verification Plan

### Must-Run

1. **`npm run build`** — already passing (confirmed).
2. **`npm test -- --run src/__tests__/deferTimeline.test.ts`** — already passing.
3. **Delete orphan `ui/src/components/ops/DeferCountdownBar.tsx`** and re-run build to confirm no hidden import.
4. **Manual:** Start dev server (`npm run dev`), verify mock deferred event `evt-demo0003` shows shrinking bar in sidebar Deferred group.
5. **Manual (live cluster):** Trigger a defer via chat ("defer this for 2 minutes"), verify:
   - Bar appears in sidebar within seconds (WS invalidation, not 10s poll)
   - Bar shrinks in real-time, shows "Waking up" at expiry
   - Event moves back to Active when Brain wakes it
   - Re-defer resets the bar (not stuck at old anchor)

### Should-Run

6. **Backend:** `pytest tests/test_queue.py` — verify `/active` shape still matches existing tests (defer fields are additive).
7. **Backend:** `pytest tests/test_scan_callback.py` — existing defer wake tests still pass.
8. **Graph page:** Open topology, verify deferred ticket node shows bar (needs live deferred event or extend mock).

### Nice-to-Have

9. Add test for `_defer_timeline_fields` with mocked Redis + event.
10. Add `deferTimeline.test.ts` cases for clamp and no-match-regex paths.
11. Add optimistic WS cache patch in `OpsStateContext` for `event_status_changed` when deferred.

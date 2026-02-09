# Code Review: Brain Temporal Memory + UI Report Enrichment

**Plan**: `brain_temporal_memory_ed69fae3.plan.md`
**Date**: 2026-02-09
**Reviewer**: Systems Architect (AI)

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** **Medium** — No breaking API changes, but one design gap creates incomplete journal data, and a HIGH-severity Aligner bug fix from the plan is missing.
* **Breaking Changes:** None. `_event_to_markdown` converted to `@staticmethod` is backward-compatible (Python allows `self.staticmethod()` calls). All existing callers work without modification.

### Changes Summary (5 files, +207 / -15)

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `src/agents/brain.py` | +117 / -13 | Temporal memory (journal cache, prompt sections, lookup_journal tool, close_and_broadcast journal write, max_output_tokens fix, system prompt update) |
| `src/state/blackboard.py` | +42 / -0 | New methods: `get_recent_closed_for_service()`, `append_journal()`, `get_journal()` |
| `src/routes/queue.py` | +32 / -0 | New `GET /{event_id}/report` endpoint |
| `ui/src/api/client.ts` | +9 / -0 | New `getEventReport()` API client function |
| `ui/src/components/ConversationFeed.tsx` | +22 / -5 | Report button fetches server-side report with client-side fallback |

---

## 2. Downstream Impact Analysis

### Affected Consumers

| Modified Code | Consumers | Impact |
|---|---|---|
| `Brain._event_to_markdown` → `@staticmethod` | `brain.py` (2 self-calls: lines 877, 1306), `queue.py` (1 static call: line 178) | **Safe.** Python resolves `self.staticmethod()` correctly. Both existing `self.` call sites continue to work. |
| `Brain._close_and_broadcast` (added journal write) | 5 callers in `brain.py`: duplicate close, max turns, max duration, routing loop, normal close | **Safe.** All callers pass through the new journal write path. |
| `BlackboardState` (3 new methods) | `brain.py`, `queue.py` | **Safe.** New methods only — no existing signatures changed. |
| `BRAIN_SYSTEM_PROMPT` (cross-event + aligner sections rewritten) | Brain LLM behavior | **Behavioral change.** LLM will now reason differently about over-provisioned events. Desired outcome per plan. |
| `ConversationFeed.tsx` (report button) | End user UI | **Safe.** Falls back to client-side `eventToMarkdown` on API failure. |

### Risk Assessment

- **Existing tests**: No existing tests will break — all changes are additive.
- **Silent failure risk**: LOW for consumers. The journal cache gracefully degrades (empty list if Redis unavailable). The report endpoint has a 404 guard.
- **Behavioral regression risk**: MEDIUM — the rewritten system prompt sections change Brain decision-making for over-provisioned events. This is intentional but should be monitored.

---

## 3. Findings & Fixes

| # | File | Severity | Issue Type | Description & Fix |
|---|------|----------|------------|-------------------|
| 1 | `blackboard.py` | **HIGH** | Performance / N+1 | `get_recent_closed_for_service()` does sequential `get_event()` for EVERY closed event in the 15-minute window, then a separate `zscore()` for each match. On a busy cluster with 100 closed events, this is 100+ Redis roundtrips per prompt build. **Fix below.** |
| 2 | `brain.py` / `queue.py` | **MEDIUM** | Design Gap | Journal writes only happen in `_close_and_broadcast()`. Two close paths bypass it: (a) `close_event_by_user` in `queue.py:154` and (b) `_cleanup_stale_events` in `brain.py:1428`. User force-closes and stale cleanup won't appear in the journal, creating blind spots for pattern recognition. **Fix below.** |
| 3 | `aligner.py` | **HIGH** | Missing Plan Step | The plan explicitly identifies the Aligner's `GenerateContentConfig` (line 692) as affected by the same 128-token Vertex AI default bug. The fix (`max_output_tokens=4096`) is NOT included in this changeset. The Aligner's text responses are being silently truncated in production right now. **Fix below.** |
| 4 | `blackboard.py` | **LOW** | Code Quality | `append_journal()` uses local import `from datetime import datetime` and calls `datetime.now()` (local time). In K8s pods, this is typically UTC, but not guaranteed. Should use `datetime.now(timezone.utc)` for deterministic behavior. |
| 5 | `blackboard.py` | **LOW** | Performance | `get_recent_closed_for_service()` calls `zrangebyscore()` without `withscores=True`, then makes a separate `zscore()` call per matching event. The same codebase uses `withscores=True` in other ZSET queries (lines 712, 795). This is a subset of Finding #1. |
| 6 | `brain.py` | **LOW** | Defensive | `event_created = event.conversation[0].timestamp` — if `timestamp` is in the future (clock skew), `age_seconds` goes negative and the display shows `Event Age: -1m 0s`. Add `max(0, ...)` guard. |
| 7 | `queue.py` | **INFO** | AI Shebang | Shebang line 1 says `GET /closed/list MUST stay before GET /{event_id}` but in the actual file, `/closed/list` is AFTER `/{event_id}`. The existing comment says "Works because 2 segments." The new `/{event_id}/report` route is correctly placed (second segment is static "report", no collision with "list"). No bug, but the shebang is self-contradictory. |

### Detailed Fixes

#### Finding #1 — N+1 Redis in `get_recent_closed_for_service`

Current code fetches ALL closed events, then filters by service name in Python:

```python
# Current: N+1 pattern
closed_ids = await self.redis.zrangebyscore(self.EVENT_CLOSED, cutoff, time.time())
for eid in closed_ids:
    event = await self.get_event(eid)  # 1 Redis GET per closed event
    if event and event.service == service:
        close_time = await self.redis.zscore(self.EVENT_CLOSED, eid)  # Extra call
```

**Recommended fix** — use `withscores=True` and pipeline the GET calls:

```python
async def get_recent_closed_for_service(
    self, service: str, minutes: int = 15
) -> list[tuple[str, float, str]]:
    """Get recently closed events for a service."""
    cutoff = time.time() - (minutes * 60)
    # Single call with scores -- eliminates N zscore roundtrips
    closed_with_scores = await self.redis.zrangebyscore(
        self.EVENT_CLOSED, cutoff, time.time(), withscores=True
    )
    if not closed_with_scores:
        return []

    # Pipeline all event fetches (1 roundtrip instead of N)
    pipe = self.redis.pipeline(transaction=False)
    for eid, _ in closed_with_scores:
        pipe.get(f"darwin:event:{eid}")
    raw_events = await pipe.execute()

    results = []
    for (eid, score), raw in zip(closed_with_scores, raw_events):
        if not raw:
            continue
        event = EventDocument(**json.loads(raw))
        if event.service == service:
            summary = ""
            if event.conversation:
                last = event.conversation[-1]
                summary = (last.thoughts or last.result or "")[:150]
            results.append((eid, score, summary))
    return results
```

#### Finding #2 — Journal gap on force-close

Add journal write to `close_event_by_user` in `queue.py`:

```python
await blackboard.close_event(event_id, f"User force-closed: {body.reason}")
# Write journal entry for user force-closes (match Brain._close_and_broadcast pattern)
await blackboard.append_journal(
    event.service,
    f"User force-closed: {body.reason[:80]}"
)
```

For `_cleanup_stale_events`, add after line 1432:

```python
await self.blackboard.append_journal(
    event.service,
    f"Stale cleanup on Brain restart -- closed with {len(event.conversation)} turns"
)
```

#### Finding #3 — Aligner `max_output_tokens`

In `aligner.py`, line 692:

```python
config=types.GenerateContentConfig(
    system_instruction=ALIGNER_SYSTEM_PROMPT,
    max_output_tokens=4096,  # ADD: Vertex AI defaults to 128 tokens
    tools=[aligner_tools],
    # ... rest unchanged
),
```

#### Finding #6 — Negative age guard

```python
age_seconds = max(0, int(time.time() - event_created))
```

---

## 4. Verification Plan

### Functional Verification

1. **Temporal memory in prompt**: Trigger two events for the same service within 15 minutes. Close the first. Verify the second event's prompt includes "Recently Closed Events" and "Service Ops Journal" sections. Check Brain log output or add temporary `logger.debug(prompt)`.

2. **Pattern recognition**: Close 3+ events of the same reason for one service. Verify the journal shows the pattern and the Brain investigates root cause instead of applying the same fix.

3. **lookup_journal tool**: In a Brain prompt that references dependencies, verify the Brain can call `lookup_journal` for a related service and receives the journal entries.

4. **Relative timestamps**: Open a conversation in the UI and verify turns show "(Xm Ys ago)" labels in the Brain's prompt.

5. **max_output_tokens**: Verify Brain responses are no longer truncated at ~128 tokens on Vertex AI. Check a "think" turn that previously would have been cut off.

### UI Verification

6. **Report button (happy path)**: Click Report on any event. Verify the rendered markdown includes service metadata, architecture diagram, and ops journal section (not present in the old client-side version).

7. **Report button (fallback)**: Temporarily block the `/report` endpoint (return 500). Verify the Report button still works using the client-side `eventToMarkdown` fallback.

### Edge Cases

8. **Empty journal**: Open a report for a service with no journal entries. Verify the endpoint returns markdown without a "Service Ops Journal" section (no empty section header).

9. **User force-close**: Force-close an event from the UI. Verify a journal entry IS created (requires Finding #2 fix) or document the gap.

10. **Brain restart**: Restart the Brain pod. Verify stale cleanup events appear in the journal (requires Finding #2 fix) or document the gap.

### Performance

11. **N+1 query**: On a cluster with >50 closed events in 15 minutes, check Redis `MONITOR` during Brain prompt builds. Count GET commands from `get_recent_closed_for_service`. Should be 1 pipeline call, not 50+ sequential GETs (requires Finding #1 fix).

---

## 5. What Went Right

- **`@staticmethod` conversion** is clean — both `self.` callers and `Brain._event_to_markdown()` static calls work correctly.
- **Journal cache with TTL + invalidation on close** prevents Redis thrashing while ensuring freshness on write.
- **Client-side fallback** for the report button is the correct resilience pattern.
- **`evidence` field** (not `thoughts`) matches the existing `lookup_service` convention — consistent pattern.
- **AI Shebang headers** updated in all 5 files with accurate documentation of new patterns and gotchas.
- **`max_output_tokens=65000`** is a critical bug fix for Vertex AI — correctly identified and applied.

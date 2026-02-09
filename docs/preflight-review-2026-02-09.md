# Pre-Flight Review v2: Brain Event Loop Fixes + Message Status Protocol

**Date:** 2026-02-09 (updated)
**Plan:** `brain_event_loop_fixes_d7ff286d.plan.md` (Wave structure)
**Source Transcript:** `d5f4c0db-78b3-4497-a03d-d93d179cdcf1`
**Reviewer:** AI Systems Architect
**Review:** v2 — against restructured Wave plan with bidirectional agent status + unread-message scan

---

## Executive Summary

The plan has been significantly restructured since v1. It now proposes **17 discrete changes** across **7 files**, organized in **3 deployment waves** aligned with Cynefin classification. Two major additions since v1:

1. **W2-D: Unread-message scan** replaces the old fragile last-turn condition matching — this is the highest-impact architectural change in the plan.
2. **W2-F2: Bidirectional agent status** tracks Brain's outgoing routing turns through SENT → DELIVERED → EVALUATED using existing WebSocket signals.

The plan also adopts all recommendations from v1 (stale-think threshold increased to 240s with `_last_processed` guard, MAX_EVENT_DURATION increased to 2700s).

**One implementation bug found** in `_broadcast_status_update` — signature mismatch between W2-F definition and W2-F2 call site. Must be fixed before execution.

**Overall Execution Confidence: MEDIUM-HIGH (7.5/10)** (up from 7/10 in v1)
- 12 changes: High confidence (Clear/Complicated — deterministic)
- 3 changes: Medium confidence (Complicated — new architectural patterns requiring careful edge-case validation)
- 2 changes: Low confidence (Complex — LLM behavioral, requires probe-sense-respond)

---

## Delta from v1 Review

| Change | v1 Status | v2 Status | Impact |
|--------|-----------|-----------|--------|
| Restructured to 3 Waves (from 4 Phases) | 4 Phases | 3 Waves committed separately | Cleaner deployment boundaries |
| W2-D: Unread-message scan replaces last-turn conditions | Not proposed (was additive) | **NEW — full replacement** | Highest-impact architectural change |
| W2-F2: Bidirectional agent status tracking | Not proposed | **NEW** | Adds outbound message visibility |
| W2-B: `mark_turn_status` (single turn update) | Not proposed | **NEW** | Required by W2-F2 |
| W2-H: Stale-think threshold | 120s, no guard | 240s + `_last_processed` guard | Addresses v1 concern |
| W2-I: MAX_EVENT_DURATION | 1800s (unchanged) | 2700s (45 min) | **NEW** — significant extension |
| `_broadcast_status_update` signature | 3 positional args | Needs redesign (bug found) | Blocking issue for W2-F2 |

---

## Cynefin Domain Classification per Change

### Wave 1: Independent High-Confidence Fixes

| ID | Change | Cynefin | Confidence | Rationale |
|----|--------|---------|------------|-----------|
| W1-A | `asyncio.sleep(1)` in event loop | **Clear** | **HIGH (10/10)** | Best Practice. Missing baseline. Zero risk. |
| W1-B | Bug 1: `re_trigger_aligner` service arg fix | **Clear** | **HIGH (9/10)** | Best Practice. Mechanical fix — store in `evidence`, parse in `check_active_verifications`. Root cause unambiguous: `service` param accepted but never forwarded (line 770). **Minor concern:** `"target_service:"` string prefix is fragile. Acceptable for now. |

**Wave 1 Verdict:** Execute and commit immediately. Zero dependencies, zero risk.

---

### Wave 2: Message Status Model + Code-Level Bug Fixes

| ID | Change | Cynefin | Confidence | Rationale |
|----|--------|---------|------------|-----------|
| W2-A | `MessageStatus` enum + `status` field | **Clear** | **HIGH (9/10)** | Standard enum addition. Pattern identical to `EventStatus` (line 285). |
| W2-B | `mark_turns_delivered` / `mark_turns_evaluated` / `mark_turn_status` | **Complicated** | **HIGH (8/10)** | Good Practice. WATCH/MULTI/EXEC pattern proven in `append_turn` (line 1339). Third method (`mark_turn_status`) is new scope — single-turn update for bidirectional tracking. All three follow same Redis pattern. **Risk:** Lock contention with `append_turn` — mitigated by existing retry loop. |
| W2-C | Bug 6: Two-phase scan (acknowledge during active tasks) | **Complicated** | **HIGH (7/10)** | Unchanged from v1. Good Practice. Extra Redis read per active event per iteration, bounded by sleep(1). |
| W2-D | **Unread-message scan (replaces last-turn conditions)** | **Complicated** | **MEDIUM (6/10)** | **NEW — major architectural change.** Replaces lines 1220-1230 condition matching with status-driven `has_unread` scan. See detailed analysis below. |
| W2-E | Mark turns EVALUATED after LLM call | **Complicated** | **HIGH (8/10)** | Clean placement after LLM loop exit. No concurrency risk — `process_event` holds logical lock via `_active_tasks`. |
| W2-F | `_broadcast_status_update` helper | **Clear** | **BLOCKED (see bug)** | Mechanical utility, but **signature mismatch with W2-F2 call site**. Must fix before execution. See issue #1 below. |
| W2-F2 | **Bidirectional agent status tracking** | **Complicated** | **MEDIUM (6/10)** | **NEW.** Adds `routing_turn_num` param to `_run_agent_task`. Uses existing WebSocket progress signals — no sidecar changes. See detailed analysis below. |
| W2-G | Bug 7: Aligner dedup via message status | **Complicated** | **HIGH (7/10)** | Unchanged from v1. Straightforward filter on `status.value in ("sent", "delivered")`. |
| W2-H | Bug 5: `wait_for_user` tool + stale-think guard | **Complicated** | **HIGH (7/10)** | Improved from v1. 240s threshold (up from 120s) + `_last_processed` double guard. Both v1 concerns addressed. Tool declaration follows existing patterns (`defer_event`, `request_user_approval`). |
| W2-I | Bug 4: Grace period + MAX_EVENT_DURATION to 2700s | **Complicated** | **HIGH (7/10)** | Unchanged logic from v1, but MAX_EVENT_DURATION now 2700s (was 1800s). Worst-case event lifetime: 2700 + 120 = 2820s (~47 min). Acceptable — 30-turn circuit breaker remains the primary guard. |
| W2-J | TypeScript `MessageStatus` type | **Clear** | **HIGH (10/10)** | Mechanical type addition. |
| W2-K | Render status indicators in ConversationFeed | **Clear** | **HIGH (8/10)** | Additive UI change. `TurnBubble` (line 362) already renders timestamps. |

**Wave 2 Verdict:** Execute after fixing the `_broadcast_status_update` signature bug. W2-D and W2-F2 require the most careful implementation and testing.

---

### Wave 3: System Prompt Probes (48hr Sensing Window)

| ID | Change | Cynefin | Confidence | Rationale |
|----|--------|---------|------------|-----------|
| W3-A | Agent Recommendations clause | **Complex** | **LOW (4/10)** | Unchanged from v1. Emergent Practice — probe. LLM compliance with "NEVER silently drop" is unpredictable. |
| W3-B | Non-metric verification guidance | **Complex** | **LOW (5/10)** | Slightly higher than v1 (was 4/10). The existing prompt at lines 67-70 already has partial coverage ("re_trigger_aligner is for metric-observable changes"). W3-B adds the missing "non-metric config change" category and strengthens the qualifier to "ONLY." Delta is smaller than originally assessed. |

**Wave 3 Verdict:** Deploy last. 48hr sensing window with defined success criteria. No code dependencies — prompt-only changes.

---

## Detailed Analysis: New Changes

### W2-D: Unread-Message Scan (Replaces Last-Turn Conditions)

This is the highest-impact architectural change. The old pattern at lines 1220-1230:

```python
last_turn = event.conversation[-1]
if last_turn.actor in ("user", "aligner") and last_turn.action in ("approve", "reject", "confirm", "message"):
    await self.process_event(eid)
elif last_turn.actor in ("architect", "sysadmin", "developer") and last_turn.action not in ("busy",):
    await self.process_event(eid)
```

Is replaced by:

```python
has_unread = any(t.status.value == "delivered" for t in event.conversation)
if has_unread:
    await self.process_event(eid)
```

**Edge-case analysis:**

| Scenario | Old Behavior | New Behavior | Safe? |
|----------|-------------|-------------|-------|
| User approves/rejects | last_turn match → process | Approval turn SENT → DELIVERED → has_unread → process | YES |
| Aligner confirms | last_turn match → process | Confirm turn SENT → DELIVERED → has_unread → process | YES |
| Agent returns result | last_turn match → process | Result appended in `_run_agent_task` which calls `process_event` directly (not via loop). Loop sees task done + all EVALUATED → no re-trigger | YES |
| Agent returns "busy" | Old code skips via `not in ("busy",)` | `_run_agent_task` calls `process_event` directly for busy. W2-E marks EVALUATED. Loop sees no unread | YES — but semantics changed: old code explicitly avoided re-processing busy; new code relies on `_run_agent_task` handling it. Functionally equivalent. |
| Brain appended `brain.think` (normal) | No last_turn match (brain actor) → skip | Turn appended during `process_event` → marked EVALUATED by W2-E → no unread → skip | YES |
| Brain `brain.think` stale (crash recovery) | No match → never re-processed (BUG) | Turn stays SENT → DELIVERED by loop → has_unread → process. **Stale guard at W2-H provides secondary catch.** | YES — improvement |
| Brain `brain.wait` | Not handled (BUG) | All turns EVALUATED → no unread → falls to W2-H elif → explicit pass | YES |
| Deferred event | Handled above W2-D (lines 1203-1218) | Unchanged — deferred check runs before W2-D | YES |
| Brain.route turn (just dispatched) | No match → skip (correct) | W2-E marks EVALUATED after LLM loop → no unread → skip | YES |

**No loop risk:** `process_event` calls `mark_turns_evaluated` (W2-E) before returning, so next scan finds zero DELIVERED turns.

**Verdict:** The replacement is **sound**. The new model is strictly more capable (catches stale brain.think crashes) and strictly simpler (single status check vs. actor/action matrix). The only behavioral change is the "busy" handling, which is functionally equivalent since `_run_agent_task` already handles it directly.

---

### W2-F2: Bidirectional Agent Status

**Flow analysis:**

```
Brain dispatches agent (select_agent) →
  1. brain.route turn appended (status=SENT) [line 709]
  2. _run_agent_task launched with routing_turn_num=turn.turn [line 736]
  3. Agent sends first progress → on_progress callback →
     mark_turn_status(routing_turn_num, DELIVERED) [W2-F2]
  4. Agent completes → result appended →
     mark_turn_status(routing_turn_num, EVALUATED) [W2-F2]
```

**Edge cases:**

| Scenario | Behavior | Safe? |
|----------|----------|-------|
| Agent never sends progress (WebSocket drop) | routing turn stays SENT indefinitely. UI shows single check. | YES — visible failure signal |
| Agent sends progress but crashes before result | routing turn stays DELIVERED. UI shows double check but no result. | YES — distinguishes "received but failed" from "never received" |
| Agent returns `busy` immediately (no progress) | No progress → `agent_acked` stays False → routing turn stays SENT. Busy turn appended separately. | YES — correct: agent rejected task |
| Multiple rapid progress messages | `agent_acked` flag prevents duplicate DELIVERED marks | YES |

**Verdict:** Clean design. Leverages existing WebSocket signals without sidecar changes. Adds meaningful visibility at low complexity cost.

---

## Issues Found

### Issue #1 (BLOCKING): `_broadcast_status_update` Signature Mismatch

**W2-F defines:**
```python
async def _broadcast_status_update(self, event_id, turns, status):
    ...
    "turns": [t.turn for t in turns] if turns else "all",
```

**W2-F2 calls:**
```python
await self._broadcast_status_update(
    event_id, None, "delivered",
    turns=[routing_turn_num],  # keyword arg conflicts with positional `turns`
)
```

**Problems:**
1. `turns` is passed as both positional (`None`) and keyword (`[routing_turn_num]`) → `TypeError: got multiple values for argument 'turns'`
2. W2-F expects `turns` to be a list of `ConversationTurn` objects (`t.turn`), but W2-F2 passes raw `int` values

**Recommended fix:** Redesign the helper signature to be unambiguous:

```python
async def _broadcast_status_update(
    self, event_id: str, status: str, turns: list | None = None,
) -> None:
    """Broadcast message status update to UI.
    
    Args:
        turns: list of turn numbers (int) or ConversationTurn objects. None = "all".
    """
    if self.broadcast:
        if turns is None:
            turn_ids = "all"
        elif turns and isinstance(turns[0], int):
            turn_ids = turns
        else:
            turn_ids = [t.turn for t in turns]
        await self.broadcast({
            "type": "message_status",
            "event_id": event_id,
            "status": status,
            "turns": turn_ids,
        })
```

All call sites would then use:
- `await self._broadcast_status_update(eid, "delivered", turns=unseen)` — ConversationTurn list
- `await self._broadcast_status_update(event_id, "evaluated")` — all turns
- `await self._broadcast_status_update(event_id, "delivered", turns=[routing_turn_num])` — int list

**Severity:** BLOCKING for W2-F2. W2-C and W2-D also call this helper so must use consistent signature.

### Issue #2 (LOW): W2-F2 missing EVALUATED broadcast after agent completion

The plan shows `mark_turn_status` for EVALUATED after agent completes, but no corresponding `_broadcast_status_update` call. The UI won't know the routing turn reached EVALUATED unless the next `mark_turns_evaluated` (W2-E) triggers a broadcast. Since W2-E broadcasts `"all"`, this is covered, but there's a timing gap between agent completion and the next `process_event` → `mark_turns_evaluated` call.

**Recommendation:** Add the broadcast after the EVALUATED mark in `_run_agent_task`:

```python
if routing_turn_num:
    await self.blackboard.mark_turn_status(
        event_id, routing_turn_num, MessageStatus.EVALUATED
    )
    await self._broadcast_status_update(
        event_id, "evaluated", turns=[routing_turn_num]
    )
```

**Severity:** LOW — functionally covered by W2-E broadcast, but adds latency to UI update.

### Issue #3 (INFO): `_run_agent_task` calls `process_event` internally — interaction with W2-D

`_run_agent_task` calls `process_event` at lines 917 (question), 932 (busy), 949 (error), and 964 (normal result). Each of these runs INSIDE the task, so `_active_tasks[event_id]` points to the currently-running task. When `process_event` dispatches a new agent, it overwrites `_active_tasks[event_id]` with the new task. The old task then returns, but the dict now points to the new task — this is correct behavior.

After `process_event` returns, W2-E marks all turns EVALUATED. The event loop then sees:
- If a new task was spawned: `_active_tasks` is active → W2-C branch (acknowledge only)
- If no new task: `_active_tasks` is done → W2-D branch → all EVALUATED → no re-trigger

**Verdict:** No issue. Documented for implementer awareness.

---

## Updated Risk Matrix

| Risk | Severity | Likelihood | Mitigation | Changed from v1? |
|------|----------|------------|------------|-------------------|
| `_broadcast_status_update` signature bug (Issue #1) | **HIGH** | **CERTAIN** | Fix signature before execution | **NEW** |
| Unread-message scan misses edge case (W2-D) | MEDIUM | LOW | Edge-case analysis above covers all known scenarios | **NEW** |
| Bidirectional status race (agent ack vs mark) | LOW | LOW | `agent_acked` flag is per-task, no cross-task race | **NEW** |
| Optimistic lock contention (W2-B vs append_turn) | LOW | MEDIUM | Existing retry loop; now 3 methods competing | Unchanged |
| System prompt non-compliance (W3-A, W3-B) | MEDIUM | HIGH | 48hr sensing with defined criteria | Unchanged |
| 240s stale-think threshold (W2-H) | LOW | LOW | Double guard (`_last_processed` + turn age) | Addressed from v1 |
| MAX_EVENT_DURATION at 2700s too permissive | LOW | LOW | 30-turn circuit breaker is primary guard | **NEW** |
| UI status flicker (out-of-order updates) | LOW | MEDIUM | Monotonic transitions (SENT→DELIVERED→EVALUATED) | Unchanged |

---

## Updated Dependency Graph

```
Wave 1 (Clear — commit #1)
  ├── W1-A: sleep(1)                        ─── independent
  └── W1-B: re_trigger_aligner fix          ─── independent

Wave 2 (Complicated — commit #2)
  W2-A: MessageStatus enum                  ─── foundation
  W2-B: mark methods (3x)                   ─── requires W2-A
  W2-F: broadcast helper (FIX SIGNATURE)    ─── required by W2-C, W2-D, W2-E, W2-F2
  ├── W2-C: two-phase scan                  ─── requires W2-A, W2-B, W2-F
  ├── W2-D: unread-message scan             ─── requires W2-A, W2-B, W2-F
  ├── W2-E: mark EVALUATED after LLM        ─── requires W2-A, W2-B, W2-F
  ├── W2-F2: bidirectional agent status     ─── requires W2-A, W2-B, W2-F
  ├── W2-G: aligner dedup                   ─── requires W2-A
  ├── W2-H: wait_for_user + stale guard     ─── independent (tool + _last_processed)
  ├── W2-I: grace period + 2700s timeout    ─── independent
  ├── W2-J: TypeScript types                ─── independent (frontend)
  └── W2-K: UI status indicators            ─── requires W2-J

Wave 3 (Complex/Probe — commit #3)
  ├── W3-A: prompt: agent recommendations   ─── independent (PROBE)
  └── W3-B: prompt: non-metric verification ─── independent (PROBE)
```

---

## Execution Checklist

### Before Wave 2 execution:
- [ ] Fix `_broadcast_status_update` signature (Issue #1) — BLOCKING
- [ ] Add EVALUATED broadcast in `_run_agent_task` (Issue #2) — recommended
- [ ] Verify `_run_agent_task` call sites pass `routing_turn_num` consistently

### After Wave 2 execution:
- [ ] Build verification: `python -c "from src.models import MessageStatus; print(MessageStatus.SENT)"`
- [ ] Test event loop: confirm SENT → DELIVERED → EVALUATED transitions in Redis
- [ ] Test bidirectional: confirm brain.route turns get DELIVERED on first agent progress
- [ ] Test dedup: confirm Aligner doesn't spam confirms for already-pending ones

### After Wave 3 execution (48hr sensing):
- [ ] Audit: grep conversation logs for `brain.think` followed by no action within 2 turns
- [ ] Audit: grep for `re_trigger_aligner` calls on non-metric changes
- [ ] Success criteria W3-A: <5% dropped recommendations
- [ ] Success criteria W3-B: 0 false-positive `re_trigger_aligner` for non-metric changes

---

## Codebase Validation (refreshed)

All target locations re-confirmed against current source:

| Target | Expected Line | Verified | Notes |
|--------|--------------|----------|-------|
| `ConversationTurn` class | ~305 | YES | No `status` field yet |
| `MessageStatus` enum | N/A | YES (absent) | Safe to add |
| `append_turn` (WATCH/MULTI/EXEC) | ~1339 | YES | Pattern confirmed |
| `start_event_loop` | ~1165 | YES | Active tasks skip at 1195 |
| Last-turn conditions (to be replaced by W2-D) | ~1220-1230 | YES | actor/action matching confirmed |
| `_execute_function_call` | ~664 | YES | `select_agent` at 679, `re_trigger_aligner` at 770 |
| `_run_agent_task` | ~868 | YES | 5 params, no `routing_turn_num` yet |
| `_run_agent_task` agent dispatch | ~736 | YES | No `routing_turn_num` passed |
| `_build_brain_tools` | ~155 | YES | 8 existing tools |
| `process_event` | ~378 | YES | Circuit breakers at 412, 425 |
| `MAX_EVENT_DURATION_SECONDS` | ~145 | YES | Currently 1800 |
| `BRAIN_SYSTEM_PROMPT` | ~37-141 | YES | Post-Execution at line 67 |
| `_notify_active_events` | ~942 | YES | No dedup |
| `check_active_verifications` | ~913 | YES | Uses `event.service` (bug confirmed) |
| `ConversationTurn` TS interface | ~132 | YES | No `status` field |
| `TurnBubble` component | ~362 | YES | No status icons |

**No blocking conflicts. Plan is structurally executable after Issue #1 fix.**

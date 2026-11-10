# Execution Outcome: Priority-Aware Token Reservation & Starvation Prevention

**Plan**: [priority-aware-token-reservation.plan.md](file:///home/thason/Git/GitHub/The-Darwin-Project/BlackBoard/plans/priority-aware-token-reservation.plan.md)  
**Jira Issue**: [VMER-2246](https://redhat.atlassian.net/browse/VMER-2246) (Parent Epic: [VMER-62](https://redhat.atlassian.net/browse/VMER-62))  
**Date**: 2026-11-04 15:13  
**Status**: COMPLETE (Phase 4C Green Verified)

---

## 1. Executive Summary

Implemented priority-aware token reservation across the BlackBoard stack to eliminate token-per-minute (TPM) quota starvation of large user-driven events (such as `evt-5ba964d5` carrying 80k–120k tokens post-approval) under rolling Vertex AI quota windows (500k TPM).

Under the new controller design:
- User-facing events (`chat`, `slack`, `jarvis`) and events with active user approvals reserve quota at `priority=0` (`PRIORITY_HIGH`).
- Automated background tasks acquire quota at `priority=1` (`PRIORITY_NORMAL`).
- In `QuotaTracker`, whenever `_high_priority_waiters > 0`, normal-priority requests are gated and throttle-sleep, preventing low-token background requests from continuously resetting the window and allowing capacity to drain so high-priority events gain admission.
- The lifecycle of `_high_priority_waiters` is guarded by strict `try/finally` blocks ensuring zero counter leakage across timeouts, cancellations, and burst limit exceptions.
- Hexagonal architectural boundaries are maintained: `LLMPort` exposes `priority` symmetrically across `GeminiAdapter` and `ClaudeAdapter`, preventing direct coupling between `Brain` and `QuotaTracker`.

---

## 2. Red-First ATDD Workflow (Dave Farley Discipline)

### Phase 4A: Red Test Specification
Two test suites were extended by subagent `execute-plan-tests` without mutating existing assertions:
1. `tests/test_quota_tracker.py`:
   - `test_high_priority_acquire_uncontended`: Direct high-priority admission without waiting.
   - `test_high_priority_waiter_gates_low_priority`: Verifies normal-priority requests fail/time out when a high-priority request is waiting for headroom.
   - `test_high_priority_acquires_first_when_capacity_frees`: Asserts FIFO-overriding admission of high-priority waiters when window headroom opens.
   - `test_high_priority_waiter_counter_cleaned_up_on_timeout`: Asserts counter drops to 0 on `QuotaExhaustedError`.
   - `test_high_priority_waiter_counter_cleaned_up_on_cancellation`: Asserts counter drops to 0 on `asyncio.CancelledError`.
   - `test_oversize_high_priority_request_raises_burst_without_leaking_counter`: Asserts `RequestExceedsBurstError` fires *before* counter increment.
   - `test_get_stats_includes_high_priority_waiters`: Verifies observability export.
2. `tests/test_gemini_client_quota.py`:
   - `test_gemini_adapter_generate_forwards_priority`: Checks `generate()` forwards `priority=0` to tracker.
   - `test_gemini_adapter_generate_stream_forwards_priority`: Checks `generate_stream()` forwards `priority=0` to tracker.
   - `test_claude_adapter_generate_accepts_priority`: Claude protocol conformance check.
   - `test_claude_adapter_generate_stream_accepts_priority`: Claude streaming protocol conformance check.

**Red Failure Proof**: 11 tests failed initially as expected (`AttributeError` and assertion mismatches), with 30 baseline tests passing.

### Phase 4B: Contract Lock
Test files were locked against modification.

### Phase 4C: Green Implementation & Verification
All 11 new tests and 31 existing tests passed without regressions:
```
tests/test_quota_tracker.py ...............                              [ 35%]
tests/test_gemini_client_quota.py ..........................             [ 97%]
tests/test_brain_admission.py .                                          [100%]

======================== 42 passed, 1 warning in 3.55s =========================
```

---

## 3. Production Changes

| File | Change Details |
| :--- | :--- |
| [`src/agents/llm/quota_tracker.py`](file:///home/thason/Git/GitHub/The-Darwin-Project/BlackBoard/src/agents/llm/quota_tracker.py) | Exported `PRIORITY_HIGH = 0` and `PRIORITY_NORMAL = 1`. Added `_high_priority_waiters` state. Enforced burst check before waiter registration. Added `try/finally` waiter counter tracking and low-priority gating while waiters exist. Included `"high_priority_waiters"` in `get_stats()`. |
| [`src/agents/llm/types.py`](file:///home/thason/Git/GitHub/The-Darwin-Project/BlackBoard/src/agents/llm/types.py) | Added `priority: int = 1` keyword argument to `LLMPort.generate` and `LLMPort.generate_stream`. |
| [`src/agents/llm/gemini_client.py`](file:///home/thason/Git/GitHub/The-Darwin-Project/BlackBoard/src/agents/llm/gemini_client.py) | Added `priority: int = 1` to `GeminiAdapter.generate` and `generate_stream`. Forwarded `priority` to `self._tracker.acquire(..., priority=priority)` with backwards compatibility for unparameterized mock assertions. |
| [`src/agents/llm/claude_client.py`](file:///home/thason/Git/GitHub/The-Darwin-Project/BlackBoard/src/agents/llm/claude_client.py) | Added `priority: int = 1` to `ClaudeAdapter.generate` and `generate_stream` for protocol compatibility (accept-and-ignore). |
| [`src/agents/brain.py`](file:///home/thason/Git/GitHub/The-Darwin-Project/BlackBoard/src/agents/brain.py) | In `_process_event_inner`, computed `is_high_priority` from source (`chat`, `slack`, `jarvis`), `event.approved_by`, or recent `user` approve/reject turns. Dispatched `priority=0` (or `1`) into `self._adapter.generate_stream`. |

---

## 4. Verification Proof

- Command: `pytest tests/test_quota_tracker.py tests/test_gemini_client_quota.py tests/test_brain_admission.py`
- Exit Code: `0`
- Results: **42 passed, 0 failed**
- Anti-Tampering: Confirmed clean via `git diff tests/` — original assertions intact.

---

## 5. Proposed Commit Message

```
feat(llm): priority-aware token reservation and user event starvation prevention

- Add PRIORITY_HIGH (0) and PRIORITY_NORMAL (1) constants and _high_priority_waiters counter in QuotaTracker
- Ensure leak-safe try/finally lifecycle for waiters and prioritize high-priority requests while gating low-priority requests
- Expose high_priority_waiters in QuotaTracker.get_stats()
- Add priority parameter to LLMPort protocol and implement in GeminiAdapter (forwarding) and ClaudeAdapter (conformance)
- Classify high-priority events (chat, slack, jarvis, approved_by, user approval turns) in Brain and dispatch with priority=0
- Pass all 42 unit and admission tests (VMER-2246)
```

# Pre-Flight Review: priority-aware-token-reservation

**Jira Tracking:** [VMER-2246](https://redhat.atlassian.net/browse/VMER-2246)
**Date:** 2026-11-04 13:50
**Status:** Caution
**Overall Confidence:** 62%

---

### 1. Confidence Dashboard

| Metric | Value |
| :--- | :--- |
| **Overall Confidence** | **62% (Caution)** |
| **Status** | Caution (Gate ≥ 90% required for `/execute-plan`) |
| **Auditor Agreement** | A: 70%, B: 75%, C: 62% (Pessimistic Min: 62%) |
| **Top Critical Blockers** | 1. ClaudeAdapter contract error (`AttributeError` on missing `_tracker`).<br>2. Counter leakage risk if increment occurs before `RequestExceedsBurstError` check.<br>3. Unmitigated inverse starvation for automated ops pipeline. |

---

### 2. Task-by-Task Analysis

| Step | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1** | QuotaTracker priority waiter tracking and low-priority gating in `quota_tracker.py` | **Complicated** (was Clear) | 55% | Increment/decrement placement and counter leakage hazard if burst check raises before `try/finally`. |
| **Step 2** | `LLMPort` interface priority parameter symmetry in `types.py` | Clear | 90% | Clean protocol change, default `priority: int = 1`. |
| **Step 3** | `GeminiAdapter` & `ClaudeAdapter` priority parameter forwarding | Complicated | 55% | ClaudeAdapter has **no** `_tracker`; must accept-and-ignore `priority` (and add missing `thinking_level`) without calling `_tracker.acquire()`. |
| **Step 4** | Brain priority classification and LLM stream dispatch in `brain.py` | Clear | 90% | Confirmed against live `models.py` and `routes/queue.py` field definitions (`event.source`, `approved_by`, `actor="user"`/`action in ("approve", "reject")`). |
| **Step 5** | Comprehensive ATDD unit tests in `tests/test_quota_tracker.py` | Complicated | 75% | Existing test file (135 lines); must extend rather than replace. Add oversize-request leak test and timeout cleanup test. |
| **Step 6** | Adapter priority parameter forwarding verification in `tests/test_gemini_client_quota.py` | Clear | 85% | Existing test file; extend with priority forwarding test and Claude accept-and-ignore test. |

---

### 3. Integration Risk Matrix

| Boundary | Pattern | Risk | Severity | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| `Brain` → `ClaudeAdapter` | Protocol dispatch | `AttributeError` / `TypeError` if ClaudeAdapter tries to use `_tracker` or signature mismatches. | **HIGH** | ClaudeAdapter must accept `priority: int = 1` and ignore it (Claude uses Anthropic quota, not Gemini Vertex tracker). |
| `QuotaTracker.acquire` | Counter state machine | Counter leak if increment occurs before `RequestExceedsBurstError` check. | **HIGH** | Check burst limit *first*; only increment `_high_priority_waiters` inside a matched `try/finally` block. |
| Automated background events vs High-priority gate | Quota admission | Low-priority events (Kargo, Jenkins, Aligner) locked out if high-priority waiters stay stuck. | **HIGH** | Ensure high-priority requests drain and clear; gate low priority only while high priority actually waits; ensure high-priority timeout resets counter. |
| 30s `max_wait_seconds` vs 100k token drain | Quota drainage | 30s wait might be tight if window is completely full (500k). | **MEDIUM** | In 30s, at 500k TPM rolling window, ~250k tokens drain. With background traffic paused, 250k drain easily admits a 100k request. Document this explicitly. |

---

### 4. Gap Analysis

1. **[HIGH] Claude contract is factually wrong**:
   - `ClaudeAdapter` does not have a `_tracker`. Step 3 must specify: `GeminiAdapter` forwards `priority` to `self._tracker.acquire(..., priority=priority)`. `ClaudeAdapter` accepts `priority: int = 1` and ignores it (or passes to Claude client without tracker).
2. **[HIGH] Counter increment placement & leak prevention**:
   - In `quota_tracker.py`, `RequestExceedsBurstError` is raised before the wait loop. If `self._high_priority_waiters += 1` is placed before that check, any oversize request will leak `+1` permanently.
   - Fix: Place `if estimated_tokens > self._burst_limit:` check first. Then manage `_high_priority_waiters` with strictly matched `try/finally`.
3. **[HIGH] Cynefin classification correction**:
   - Step 1 is marked `[Clear]`, but concurrency and waiter-state accounting with timeout / cancellation guarantees in an asynchronous rate limiter is `[Complicated]`.
4. **[MEDIUM] Test files are extensions, not new files**:
   - `tests/test_quota_tracker.py` and `tests/test_gemini_client_quota.py` already have comprehensive test suites. Step 5 and Step 6 must explicitly extend existing classes, not overwrite them.
5. **[MEDIUM] Scope & drainage documentation**:
   - Clarify that `QuotaTracker` is specifically the Gemini Vertex AI rate limiter.
   - Explain the drainage window: 30s timeout drains up to 250k tokens in a 500k TPM window, allowing 80k-120k requests to admit reliably.

---

### 5. Path to Green

- [ ] **PtG-1**: Update Step 1 in plan: Reclassify to `[Complicated]`. Detail exact placement: check `estimated_tokens > self._burst_limit` *before* waiter tracking; wrap wait cycle in `try / finally` with `self._high_priority_waiters = max(0, self._high_priority_waiters - 1)`.
- [ ] **PtG-2**: Update Step 3 in plan: Clarify that `GeminiAdapter` forwards `priority` to `self._tracker.acquire()`, while `ClaudeAdapter` accepts `priority: int = 1` as an accept-and-ignore parameter (no tracker on ClaudeAdapter).
- [ ] **PtG-3**: Update Steps 5 & 6 in plan: Specify extending existing `tests/test_quota_tracker.py` and `tests/test_gemini_client_quota.py` test suites. Add ATDD tests for:
  - Oversize high-priority request raises `RequestExceedsBurstError` without leaking waiter counter.
  - Low-priority request gated while high-priority waiter is pending.
  - High-priority waiter counter decremented on `QuotaExhaustedError` and cancellation.
  - `ClaudeAdapter` accepts `priority` without error.
- [ ] **PtG-4**: Add Drainage & Scope Justification section in plan explaining why 30s `max_wait_seconds` is sufficient to clear burst headroom for 120k token payloads when background traffic is paused.

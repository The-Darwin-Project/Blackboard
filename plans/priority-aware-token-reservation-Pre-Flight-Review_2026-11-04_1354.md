# Pre-Flight Review: priority-aware-token-reservation (Round 2)

**Jira Tracking:** [VMER-2246](https://redhat.atlassian.net/browse/VMER-2246)
**Date:** 2026-11-04 13:54
**Status:** Ready
**Overall Confidence:** 90%

---

### 1. Confidence Dashboard

| Metric | Round 1 | Round 2 | Value |
| :--- | :--- | :--- | :--- |
| **Overall Confidence** | 62% Caution | **90% Ready** | **90% (Ready)** |
| **Status** | Caution | **Ready** | Ready (Soft gate ≥ 90% achieved) |
| **Auditor Agreement** | A: 70%, B: 75%, C: 62% | A: 92%, B: 92%, C: 90% | Pessimistic Min: **90%** |
| **Round 1 Blocker Status** | 4 open | **4/4 RESOLVED** | All execution blockers cleared and verified against live source. |

---

### 2. Task-by-Task Analysis

| Step | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1** | QuotaTracker priority waiter tracking, leak-safe try/finally lifecycle, and low-priority gating in `src/agents/llm/quota_tracker.py` | Complicated | 90% | Verified: Burst check precedes waiter increment; guaranteed decrement in `finally`; gate logic respects per-caller deadline. |
| **Step 2** | `LLMPort` interface priority parameter symmetry in `src/agents/llm/types.py` | Clear | 95% | Keyword argument dispatch in Brain prevents positional breakage. |
| **Step 3** | `GeminiAdapter` priority forwarding and `ClaudeAdapter` accept-and-ignore in `src/agents/llm/gemini_client.py` and `src/agents/llm/claude_client.py` | Clear | 90% | Verified: `ClaudeAdapter` lacks `_tracker`; accept-and-ignore prevents `AttributeError`. |
| **Step 4** | Brain priority classification and LLM stream dispatch in `src/agents/brain.py` | Clear | 95% | Verified: `EventDocument.approved_by` and `ConversationTurn(actor='user', action in ('approve', 'reject'))` match canonical models in `src/models.py`. |
| **Step 5** | Extend `tests/test_quota_tracker.py` with priority preemption, oversize leak-safety, and waiter cleanup unit tests | Complicated | 90% | Extends existing 135-line test suite with targeted ATDD scenarios. |
| **Step 6** | Extend `tests/test_gemini_client_quota.py` with adapter priority forwarding and Claude protocol conformance tests | Clear | 92% | Extends existing test suite. |

---

### 3. Integration Risk Matrix

| Boundary | Pattern | Risk | Severity | Status |
| :--- | :--- | :--- | :--- | :--- |
| `Brain` → `ClaudeAdapter` | Protocol dispatch | `AttributeError` on missing `_tracker` | HIGH | **RESOLVED** (`ClaudeAdapter` accepts and ignores `priority`). |
| `QuotaTracker.acquire` | Counter state machine | Counter leak on oversize request | HIGH | **RESOLVED** (Burst limit check runs *before* waiter counter increment). |
| Low-prio background events vs High-priority gate | Quota admission | Low-prio callers timeout under sustained bursts | MEDIUM | **DOCUMENTED** (Raises transient `QuotaExhaustedError`, safely retried by ReconcileScheduler resync). |
| 30s timeout vs 120k token drain | Token bucket physics | 30s wait budget expiration | LOW | **DOCUMENTED** (500k rolling 60s window drains up to 250k in 30s, clearing 80k–120k payloads). |

---

### 4. Gap Analysis

All Round 1 gaps (Claude contract, counter leak placement, test extension semantics, drainage analysis) are resolved.
Residual non-blocking polish items:
1. Low-priority bounded deferral trade-off documented in plan §3.3.
2. File path citations updated to `src/models.py`.
3. Observability logs explicitly preserved in Step 1.

---

### 5. Path to Green

- [x] PtG-1: Leak-safe burst-check-before-increment and `try/finally` decrement in Step 1.
- [x] PtG-2: `ClaudeAdapter` accept-and-ignore contract specified in Step 3.
- [x] PtG-3: Test suite extension semantics and leak test cases defined in Steps 5 & 6.
- [x] PtG-4: Rolling window drainage timing analysis added to §1.
- [x] PtG-C1: Low-priority bounded deferral trade-off documented in §3.3.
- [x] PtG-C2: Citation corrected to `src/models.py`.
- [x] PtG-C3: Observability logging preserved in Step 1.

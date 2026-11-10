# Pre-Flight Review: Nightwatcher Backlog & Quota Deadlock Remediation (Round 2)

**Timestamp:** 2026-11-03 20:55 UTC  
**Plan:** `BlackBoard/plans/nightwatcher-backlog-and-quota-deadlock.plan.md`  
**Plan Revision:** 1.1 (incorporating AL-1 to AL-5)  
**Jira Issue:** [VMER-2236](https://redhat.atlassian.net/browse/VMER-2236) (under parent [VMER-62](https://redhat.atlassian.net/browse/VMER-62))  
**Auditor Panel:** 3 parallel auditors (Architecture, Gap Analysis, Contracts & Platform)

---

## 1. Executive Summary & Auditor Matrix

| Auditor | Lens | Round 1 Score | Round 2 Score | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Auditor A** (`4a1e3bc0`) | Architecture & Closed-Loop Control | 95% | **95%** | Ready |
| **Auditor B** (`a19ddef7`) | Gap Analysis & Edge Cases | 85% | **96%** | Ready |
| **Auditor C** (`d64d7d45`) | Contracts & Platform Hazards | 85% | **98%** | Ready |
| **Consensus (Pessimistic)** | **Minimum Across All Auditors** | **85%** | **95%** | **Ready** |

**Consensus Gate Result:** **PASSED** (95% ≥ 90% soft gate threshold, 0 Stop / 0 Caution).

---

## 2. Verified Amendments (AL-1 to AL-5)

1. **AL-1 (`restage_orphans` FIFO preservation & atomic cleanup):**
   - Signature preserved: `async def restage_orphans(self, json_members: list[str]) -> int`.
   - ZSET score restored from `_json.loads(jm).get("staged_at", 0.0)` rather than clock time, guaranteeing deterministic FIFO replay.
   - Pipelined atomicity: `pipe.zadd` + `pipe.srem(NIGHTWATCHER_INFLIGHT)` executed in single `pipeline(transaction=True)`.
   - Corrupt JSON quarantined safely via try/except scan.
2. **AL-2 (`QuotaExhaustedError` shift recovery):**
   - Explicit `except QuotaExhaustedError as qe:` added before generic catch in `_sweep()`.
   - Restages in-flight leases via `await self.blackboard.restage_orphans(json_members)` to prevent stuck items.
   - Records `ShiftReport(status="quota_exhausted")` to inform control loop and prevent crash loop.
3. **AL-3 (Null-safe prompt truncation):**
   - Fixed format expression `(e.summary or "")[:140]` in Step 4 and ATDD scenario T-4.
4. **AL-4 (Downstream Phase 2 taxonomy compatibility):**
   - Self-healing fallback cluster in `validate_cluster_plan` populates all contract keys: `title`, `platform`, `events`, `reasoning`.
   - Bounded platform resolution against `VALID_PLATFORMS` ensures Phase 2 incident hydration / Jira cart dispatch will not fail validation.
5. **AL-5 (Standardized config bootstrap):**
   - Standalone drain utility bootstraps Redis via canonical `REDIS_URL`, `REDIS_PASSWORD`, and explicit `socket_timeout=30` (adhering to redis-py 8.0 safety rule).

---

## 3. Path to Green Ledger

All items from Pre-Flight Round 1 have been fully resolved:
- `PTG-1`: Restage orphans FIFO and atomicity -> **Resolved (AL-1)**
- `PTG-2`: Sweep error catch for quota exhaustion -> **Resolved (AL-2)**
- `PTG-3`: Null-safe escalation summary slicing -> **Resolved (AL-3)**
- `PTG-4`: Fallback cluster contract alignment -> **Resolved (AL-4)**
- `PTG-5`: Redis client timeout configuration -> **Resolved (AL-5)**

---

## 4. Final Verdict

The plan is mathematically sound, preserves state invariants, eliminates quota deadlock loops, and provides comprehensive automated ATDD coverage. **Ready for execution.**

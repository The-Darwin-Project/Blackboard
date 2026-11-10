# Pre-Flight Review (Round 1): nightwatcher-backlog-and-quota-deadlock

**Date:** 2026-11-03 20:52:00 IST
**Plan:** `nightwatcher-backlog-and-quota-deadlock.plan.md`
**Jira:** [VMER-2236](https://redhat.atlassian.net/browse/VMER-2236)

---

## 1. Unified Confidence Dashboard

| Metric | Auditor A (Architecture) | Auditor B (Gap Analysis) | Auditor C (Contracts & Platform) | Pessimistic Consensus |
| :--- | :--- | :--- | :--- | :--- |
| **Confidence** | 95% | 85% | 85% | **85%** |
| **Status** | Ready | Caution | Caution | **Caution (Needs Amendment)** |

---

## 2. Auditor Feedback & Critical Findings

### Auditor A (Architecture & Control Loops): 95%
- Bounded ingestion, lean payload, and railway cluster validation cleanly resolve the mathematical deadlock and retry spiral.
- Redis transaction hygiene is respected.
- Gaps identified: Drain script config inheritance, Phase 2 synthetic cluster ID downstream compatibility.

### Auditor B (Gap Analysis & Path Portability): 85%
- Zero leaked paths or `file:///` URLs (100% repo-relative).
- Gaps identified:
  1. `QuotaExhaustedError` propagation in `nightwatcher.py` needs explicit try/except block to restage items and record shift report cleanly.
  2. Step 3 snippet omitted `now` instantiation.
  3. `drain_nightwatcher_backlog.py` requires standard Redis connection bootstrapping.

### Auditor C (Contracts & Platform Abstractions): 85%
- Contract break in Step 3: Changing `restage_orphans` return type `-> int` to `-> None`.
- Queue ordering break in Step 3: Overwriting `staged_at` with `now` destroys FIFO priority in ZSET. Must parse `staged_at` from JSON.
- Corrupt JSON isolation in Step 3: Must retain `try/except json.loads` loop so corrupt entries don't fail the pipeline.
- Null-safety in Step 4: `(e.summary or "")[:140]` to prevent `TypeError`.

---

## 3. Path to Green (Consolidated Actions)

1. **Step 3 Amendment:** Retain signature `restage_orphans(self, json_members: list[str]) -> int`. In pipeline, extract `staged_at` via `try/except json.loads` to preserve ZSET score ordering. Execute atomic `pipe.zadd` + `pipe.srem` per member. Return count of restaged items.
2. **Step 1 & 4 Amendment:** Add explicit `try/except QuotaExhaustedError:` in `nightwatcher.py` sweep/analysis loop to cleanly invoke `restage_orphans`, record `"quota_exhausted"` in `ShiftReport`, and alert without unhandled pod crash.
3. **Step 4 Amendment:** Make summary truncation null-safe: `(e.summary or "")[:140]`.
4. **Step 5 Amendment:** Explicitly verify `c-unassigned-fallback` cluster schema compatibility with Phase 2 cart hydration and Jira Incident generation.
5. **Step 6 Amendment:** Specify `scripts/drain_nightwatcher_backlog.py` Redis client initialization reusing `REDIS_URL` and `REDIS_PASSWORD` with `socket_timeout=30`.

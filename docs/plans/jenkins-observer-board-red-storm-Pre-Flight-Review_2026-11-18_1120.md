# Pre-Flight Verification Review: Jenkins Observer Board Red Storm (Round 2)

**Timestamp:** 2026-11-18 11:20:00 UTC  
**Target Plan:** `~/.cursor/plans/jenkins-observer-board-red-storm.plan.md`  
**Git Root:** `BlackBoard/`  
**Review Type:** Round 2 Pre-Flight Review (3-Auditor Panel)  
**Overall Confidence:** **88%** (Pessimistic Minimum across Auditor A: 92%, Auditor B: 92%, Auditor C: 88%)  
**Status:** **Caution** (Convergence Soft Gate < 90% due to 4 tactical contract gaps identified for immediate resolution)

---

## 1. Consolidated Confidence Dashboard

| Auditor Role | Model Tier | Overall Confidence | Status | Critical Blockers |
| :--- | :--- | :--- | :--- | :--- |
| **Auditor A** (Architecture & Cynefin) | Thinking | **92%** | Ready | 0 |
| **Auditor B** (Gaps & Path Hygiene) | Thinking | **92%** | Caution | 0 |
| **Auditor C** (Contracts & Edge Cases) | Thinking | **88%** | Caution | 2 (Contract precision in Step 2) |
| **Pessimistic Merge** | Composite | **88%** | **Caution** | **2 Tactical Contract Blockers** |

- **Path & Link Hygiene**: **100% Clean**. Zero `file:///` URLs. Zero leaked `/home/...` developer paths.
- **Hexagonal Boundaries**: 100% Preserved. `BlackboardProtocol` phantom removed; `blackboard.py` implements direct Redis primitives with byte decoding.

---

## 2. Auditor Findings Summary

### Auditor A (Architecture & Cynefin - 92%)
- Verified Schmitt trigger hysteresis model aligns with control theory setpoint and eliminates alert loop.
- Noted `_is_triggering_result(j.result)` should be used in `_eval_view_health` rather than hardcoding `("FAILURE", "UNSTABLE")` to respect configurable `_trigger_states`.
- Verified dry-run guard in Step 4 protects state eviction during non-mutating observer passes.

### Auditor B (Gaps & Path Hygiene - 92%)
- Verified path hygiene is 100% clean.
- Caught attribute typo in Step 5: `self.adapter` must be private `self._adapter`.
- Caught iteration bug in Step 5: `recheck_cache[view]` is now `ViewScanResult`, so looping over `recheck_cache[view]` directly raises `TypeError`. Must iterate `(scan.jobs or [])`.
- Caught missing `ViewScanResult` import under `if TYPE_CHECKING:` in Step 1.
- Caught redundant Redis fetch in Step 6: add `if eid in status_map: continue`.

### Auditor C (Contracts & Edge Cases - 88%)
- **Critical Blocker 1 (Deadband Re-staging)**: In Step 2, if `last_fp != fingerprint` is checked inside `if in_outage:`, any failure decrease during deadband ($0.50 \le ratio < 0.70$) re-stages a `BOARD_RED` candidate because the fingerprint changed. This directly violates test scenario T-5 (`assert stage_jenkins_signal.call_count == 0`).  
  *Fix*: Gate staging strictly on `if is_outage and last_fp != fingerprint:`, while executing `continue` unconditionally for all `in_outage`.
- **Critical Blocker 2 (Metadata Schema Contract)**: Step 2 metadata dictionary omitted baseline fields (`job_name`, `version`, `build_number`, `url`, `staged_at`, `active_count`).  
  *Fix*: Retain full baseline metadata envelope while adding `fingerprint` and `failure_ratio`.
- **Resilience**: Step 4 should wrap Redis calls in `try...except` to prevent transient blips from aborting subsequent views.
- **In-Progress Builds**: Step 5 recheck health evaluation must filter in-progress builds (`not (j.result is None and j.build_number is not None)`).

---

## 3. Path to Green (Round 2 Amendments A-8 through A-13)

- **A-8 (Step 1)**: Import `ViewScanResult` alongside `JobResult` under `if TYPE_CHECKING:`. In `_eval_view_health`, use `self._is_triggering_result(j.result)` and filter out in-progress builds (`not (j.result is None and j.build_number is not None)`).
- **A-9 (Step 2)**: Gate staging on `if is_outage and last_fp != fingerprint:` within `if in_outage:`, ensuring deadband suppresses staging while maintaining fallthrough suppression (`continue`). Retain complete baseline metadata envelope.
- **A-10 (Step 4)**: Wrap `commit_jenkins_signal` and `clear_jenkins_last_outage_fingerprint` in `try...except Exception as e:` logging warning.
- **A-11 (Step 5)**: Enforce `self._adapter`, update loop to `for j in (scan.jobs or []):`, and filter in-progress jobs before `_eval_view_health`.
- **A-12 (Step 6)**: Add `if eid in status_map: continue` prior to fetching event doc in waiting-approval loop.
- **A-13 (Step 7)**: Set `bb.get_jenkins_last_outage_fingerprint = AsyncMock(return_value=None)` in mock fixture.

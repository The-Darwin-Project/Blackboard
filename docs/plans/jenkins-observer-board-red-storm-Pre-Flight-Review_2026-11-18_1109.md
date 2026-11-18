# Pre-Flight Review: jenkins-observer-board-red-storm (Round 1)

**Date:** 2026-11-18 11:09  
**Plan:** `jenkins-observer-board-red-storm.plan.md`  
**Jira Issue:** [VMER-2395](https://redhat.atlassian.net/browse/VMER-2395) | **GitHub Issue:** [#345](https://github.com/The-Darwin-Project/Blackboard/issues/345)  
**Target Repository:** `BlackBoard`  

---

### 1. Confidence Dashboard

| Metric | Value |
| :--- | :--- |
| **Overall Confidence** | **78%** (Pessimistic Min across Auditors A, B, C) |
| **Status** | **Caution** |
| **Auditor A (Architecture & Cynefin)** | 82% (Caution) |
| **Auditor B (Gaps & Path Hygiene)** | 82% (Caution) |
| **Auditor C (Contracts & Edge Cases)** | 78% (Caution) |
| **Path & Link Hygiene** | **PASSED** (0 `file:///` URLs, 0 `/home/...` paths) |
| **Critical Blockers** | 1. **Schmitt Trigger Fallthrough**: In `_poll_and_stage()`, suppressing `BOARD_RED` without `continue` or falling through in the deadband ($0.50 \le \text{ratio} \le 0.70$) stages individual failing jobs, producing an alert storm.<br/>2. **Metadata KeyError & Redis Decode**: Missing `"fingerprint"` key in staged metadata dictionary crashes `_process_candidates()`; raw Redis `get()` bytes return must be decoded.<br/>3. **Phantom Protocol**: `BlackboardProtocol` does not exist in `BlackBoard/src/state/ports.py`.<br/>4. **Dry-Run Safety**: Missing `if not self._dry_run:` guard around recovery evictions and fingerprint deletion in `_clear_recovered_group_flags`. |

---

### 2. Task-by-Task Analysis (Pessimistic Agreement Matrix)

| Step | Task Summary | Domain | Auditor A | Auditor B | Auditor C | Min Conf | Agreement Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Step 1** | Symmetric recency pruning & view health helper in `jenkins_observer.py` | Clear | 92% | 90% | 92% | **90%** | Full Agreement (Clarify tuple unpacking & `JobResult` type import) |
| **Step 2** | Schmitt trigger hysteresis & outage fingerprint staging in `jenkins_observer.py` | Complicated | 78% | 75% | 70% | **70%** | Full Agreement (Blockers: missing `continue` fallthrough, deadband logic, missing `"fingerprint"` in metadata, Redis write error handling) |
| **Step 3** | Durable outage fingerprint in `blackboard.py` & `ports.py` | Clear | 75% | 80% | 80% | **75%** | Full Agreement (Blocker: remove phantom `BlackboardProtocol` from `ports.py`, decode Redis bytes) |
| **Step 4** | Evict pending view-outage ZSET candidates on recovery in `_clear_recovered_group_flags` | Clear | 85% | 80% | 88% | **80%** | Full Agreement (Blocker: wrap recovery cleanup in `if not self._dry_run:`) |
| **Step 5** | Remove BOARD_RED bypass & fail-closed HTTP 200 in `_recheck_and_filter` | Complicated | 84% | 85% | 72% | **72%** | Full Agreement (Blocker: `recheck_cache` must store `ViewScanResult`, prune jobs before health eval) |
| **Step 6** | Expand dedup check to union `get_waiting_approval_events` | Clear | 95% | 95% | 95% | **95%** | Full Agreement (Ready) |
| **Step 7** | Update test fixtures & add ATDD test classes in `test_jenkins_observer.py` | Clear | 90% | 90% | 90% | **90%** | Full Agreement (Add dry-run recovery and FakeRedis test scenarios) |

---

### 3. Integration Risk Matrix

| Boundary | Pattern | Risk | Recommendation |
| :--- | :--- | :--- | :--- |
| **Observer $\rightarrow$ Blackboard (Signal Staging)** | Signal Staging / Dwell Queue | Suppressing `BOARD_RED` without `continue` falls through to lines 734–754, staging all individual failing jobs and causing an alert storm. Missing `"fingerprint"` in metadata raises `KeyError`. | Add `continue` on outage branch. Insert `"fingerprint": fingerprint` into staged metadata dict. Handle deadband ($0.50 \le \text{ratio} \le 0.70$) when outage is active. |
| **BlackboardState $\rightarrow$ Redis** | Document Storage (Key-Value) | Raw Redis `get()` returns `bytes` when `decode_responses=False`; `b"..." == "..."` evaluates `False`, silently breaking outage dedup. | Wrap return value in `val.decode("utf-8") if isinstance(val, bytes) else val`. |
| **JenkinsObserver $\rightarrow$ Redis (Recovery)** | State Deletion | `commit_jenkins_signal` and `clear_jenkins_last_outage_fingerprint` run without checking `_dry_run`, violating `@ai-rules` rule #7 and mutating Redis during dry runs. | Guard all recovery mutations with `if not self._dry_run:`. |
| **Jenkins REST Adapter $\rightarrow$ Recheck** | Port / Adapter Call | `recheck_cache` currently stores `scan.jobs: list`, dropping `status_code` for subsequent candidates sharing a view on 5xx/timeout. | Type `recheck_cache` as `dict[str, ViewScanResult]`. Cache full scan result. |
| **State Port Boundary (`ports.py`)** | Hexagonal Architecture | `BlackboardProtocol` does not exist in `ports.py`. Segregated domain protocols exist instead. | Drop `ports.py` modification, keeping parity with existing Jenkins alert methods in `blackboard.py`. |

---

### 4. Gap Analysis

- **Step 1 (Helper Signature & Import):**
  - Clarify return tuple: `tuple[bool, list[JobResult], float]` as `(is_outage, failing_jobs, ratio)`.
  - Add `from ..adapters.jenkins import JobResult` under `TYPE_CHECKING`.
- **Step 2 (Hysteresis Fallthrough & Metadata):**
  - **Blocker:** In `_poll_and_stage()`, if view is outage-active (or `last_fp is not None`), and ratio is within hysteresis deadband ($0.50 \le \text{ratio} \le 0.70$), maintain outage state and do NOT stage individual jobs.
  - **Blocker:** Add `"fingerprint": fingerprint` to `metadata` dict when staging `view-outage:{view}`.
  - **Blocker:** When `last_fp == fingerprint`, log debug and `continue` immediately to avoid falling through to individual job staging.
  - In `_process_candidates()`, wrap `set_jenkins_last_outage_fingerprint` in `try...except Exception:` to prevent candidate restage if event was already created.
- **Step 3 (Protocol & Byte Decoding):**
  - Drop reference to non-existent `BlackboardProtocol` in `ports.py`.
  - Add `val.decode("utf-8") if isinstance(val, bytes) else val` in `get_jenkins_last_outage_fingerprint()`.
- **Step 4 (Dry-run Guard):**
  - Wrap `commit_jenkins_signal` and `clear_jenkins_last_outage_fingerprint` inside `if not self._dry_run:`.
- **Step 5 (Recheck Caching & Threshold Alignment):**
  - Change `recheck_cache` to `dict[str, ViewScanResult]`.
  - Pass `scan.jobs` through recency/active filtering before calculating ratio in recheck.
  - Harmonize threshold: recovery is `ratio < 0.50` (recheck commits signal if `ratio < 0.50` or active $< 3$).
- **Step 7 (Test Coverage):**
  - Add test asserting that `dry_run=True` does NOT invoke `commit_jenkins_signal` or `clear_jenkins_last_outage_fingerprint` during recovery.
  - Add test for FakeRedis byte decoding.

---

### 5. Path to Green

1. [ ] **Step 1:** Specify `(is_outage, failing_jobs, ratio)` return signature and import `JobResult` under `TYPE_CHECKING`.
2. [ ] **Step 2:** Fix `_poll_and_stage()` outage flow:
   - Calculate `is_outage, failing_jobs, ratio = self._eval_view_health(active)`.
   - If `is_outage` OR (`last_fp is not None` and `ratio >= 0.50` and `len(active) >= 3` and `len(failing_jobs) >= 3`):
     - View is in outage: compute `fingerprint`.
     - If `last_fp != fingerprint`: stage `view-outage:{view}` with `metadata={"result": "BOARD_RED", "fingerprint": fingerprint, "view": view, ...}`.
     - Unconditionally `continue` (never fall through to individual job staging).
3. [ ] **Step 2:** Wrap `set_jenkins_last_outage_fingerprint` in `_process_candidates()` in `try...except Exception as e:` to guard against post-creation restage loops.
4. [ ] **Step 3:** Implement byte decoding in `get_jenkins_last_outage_fingerprint()`; drop `ports.py` change.
5. [ ] **Step 4:** Guard `commit_jenkins_signal` and `clear_jenkins_last_outage_fingerprint` with `if not self._dry_run:` in `_clear_recovered_group_flags`.
6. [ ] **Step 5:** Type `recheck_cache` as `dict[str, ViewScanResult]`. Apply recency filtering to `scan.jobs` before health evaluation, and commit recovered signal if `ratio < 0.50`.
7. [ ] **Step 7:** Add unit test classes for dry-run recovery safety, deadband suppression, and FakeRedis byte decoding.

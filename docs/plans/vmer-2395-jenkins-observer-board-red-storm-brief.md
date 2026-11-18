# Architect Brief: Jenkins Observer False BOARD_RED Sentinel Storms & Close-to-Re-Emit Loops
**Jira / Issue:** [VMER-2395](https://redhat.atlassian.net/browse/VMER-2395) | [The-Darwin-Project/Blackboard#345](https://github.com/The-Darwin-Project/Blackboard/issues/345)
**Incident:** `evt-d5f7584f` (related: `VMER-2191`, `evt-2aae6f01`)
**Canvas:** [architect-brief.canvas.tsx](file:///home/thason/.cursor/projects/home-thason-Git-GitHub-The-Darwin-Project/canvases/architect-brief.canvas.tsx)
**Agent Compatibility Score:** 79/100 (Deterministic: 78, Dynamic: 82.3)

---

## 1. Executive Summary & Control Theory Formulation

- **Setpoint ($SP$):** Only trigger `ci-gating-outage` (`BOARD_RED`) when active builds on a view genuinely exceed the 70% failure/unstable threshold, emit exactly once per outage occurrence, suppress re-emissions while the underlying incident/outage is unresolved or awaiting human approval, and immediately cancel/evict queued outage escalations when the view recovers.
- **Process Variable ($PV$):** During `evt-d5f7584f`, ~60 duplicate `ci-gating-outage|Gating Wrappers` events fired every 5–10 minutes, saturating Redis queues, consuming LLM context, and triggering churn across Slack/monitoring channels.
- **Controller:** `jenkins_observer.py` (polling loop, recency window calculation, candidate generation, queue staging) and `blackboard.py` (dedup query, pending eviction, durable outage state).
- **Feedback Loop / Error Signal ($e = SP - PV$):** High alert storm frequency caused by five distinct compounding defects (P0-1 through P0-5) in recency pruning, state persistence, recovery eviction, network fail-open handling, and status dedup boundaries.

---

## 2. Situational Awareness

| Dimension | Findings / System Reality |
| :--- | :--- |
| **Stack** | Python 3.15, FastAPI/Uvicorn, Redis 7.2 (ZSET, HASH, PUB/SUB), `fakeredis`, `pytest-asyncio`, `uv`. |
| **Architecture** | Hexagonal (Ports & Adapters). Domain logic in `src/agents/jenkins_observer.py`, State Adapter in `src/state/blackboard.py`, external port `aiohttp.ClientSession` to Jenkins REST API. |
| **Boundaries** | Service Git root is `BlackBoard/`. `@ai-rules` boundaries restrict direct Redis writes from pure logic. |
| **Agent Compat** | **79/100** (Build: 100, Test: 94, Run: 85, Docs: 69, Bootstrap: 50, Lint: 70). Scoped tests run in 1.09s (`uv run pytest tests/test_jenkins_observer.py -k TestTV7d`). |
| **Platform Econ** | **Double Pyramid:** Pass (zero added complexity). **Cimarron:** Pass (bounded failure mode). **Abstraction:** Fail (status code ignored, raw strings over typed domain). **Railways:** Fail (lacks Schmitt trigger self-centering). |

---

## 3. Root Cause Analysis (RCA) Matrix

### P0-1: Asymmetric Recency Window on Quiet Views
- **File:** `BlackBoard/src/agents/jenkins_observer.py:703-718`
- **Mechanism:** Builds with `result == "SUCCESS"` older than `RECENCY_WINDOW_HOURS` (72h) are pruned from `active_builds`, but `FAILURE` and `UNSTABLE` builds are retained indefinitely without an age cap.
- **Incident Topology:** On quiet views like `Gating Wrappers` (low commit velocity over weekends), total active builds shrank from 46 to 8 as successes expired. With 6 historical failures retained, the failure ratio spiked to $6 / 8 = 75\% > 70\%$, firing a false `BOARD_RED` even though no new failures occurred.
- **Remedy:** Apply symmetric age pruning: prune any build older than `RECENCY_WINDOW_HOURS` regardless of result status. Also introduce minimum failure count floor (`min_failures=3` or `min_active_builds=5`) and Schmitt trigger hysteresis (activate $>70\%$, recover $<50\%$).

### P0-2: Missing Durable Outage Fingerprint & Close-to-Re-Emit Loop
- **File:** `BlackBoard/src/state/blackboard.py:3146-3171` & `BlackBoard/src/agents/jenkins_observer.py:898-904`
- **Mechanism:** Redis `last_alerted_build` is only updated when `build_number is not None`. Because `BOARD_RED` events have `build_number: None`, no durable alerted state is written to Redis.
- **Incident Topology:** In PR #306, a lazy cleanup mechanism was introduced to prune active escalation flags upon event closure. When a human operator or automated triage closed the `BOARD_RED` event, the escalation flag was pruned. Because no `last_alerted_build` or outage fingerprint existed in Redis, the very next polling cycle (~60s) saw the view still $>70\%$ and immediately re-emitted a new event.
- **Remedy:** Record a durable outage fingerprint in Redis (e.g. `last_alerted_outage_ts` or synthetic build hash `f"outage:{view_name}:{first_failure_ts}"` in `darwin:jenkins:last_alerted`) to prevent immediate re-emission after event closure while the underlying condition is unchanged.

### P0-3: Pending ZSET Orphaned on View Recovery & Skipped Recheck
- **File:** `BlackBoard/src/agents/jenkins_observer.py:848-851, 915-925`
- **Mechanism:** When a view recovers, `_clear_recovered_group_flags` clears the service flag, but fails to evict pending candidates with key `view-outage:<view>` from `JENKINS_PENDING_ZSET`. The pending drain loop subsequently evaluates the candidate and emits it anyway. Additionally, `_recheck_and_filter` explicitly skips the 2-stage verification for `BOARD_RED` (`if candidate.get("event_type") == "BOARD_RED": return True`).
- **Remedy:** On recovery, actively evict all pending keys matching `f"view-outage:{view_name}"` from `JENKINS_PENDING_ZSET`. Remove the `BOARD_RED` bypass in `_recheck_and_filter` so outages undergo verification before emission.

### P0-4: Fail-Open Candidate Recheck on HTTP 5xx / Timeout
- **File:** `BlackBoard/src/agents/jenkins_observer.py:853-875`
- **Mechanism:** `_recheck_and_filter` ignores `scan.status_code` or network exceptions from `_fetch_view_jobs`. When Jenkins returns HTTP 500/502/503/504 or times out, `jobs` evaluates to empty `[]`. The function interprets this as "candidate still unresolved" and allows the candidate to drain and fire.
- **Remedy:** Fail-closed on network errors: if `scan.status_code != 200` or an exception occurs, retain the candidate in pending with backoff or drop it; never treat an infrastructure outage or scrape failure as confirmation of job failure.

### P0-5: Dedup Blindspot for Parked Waiting-Approval Events
- **File:** `BlackBoard/src/agents/jenkins_observer.py:347-362` & `BlackBoard/src/state/blackboard.py:309-322`
- **Mechanism:** `_is_duplicate_or_escalated` only checks `get_active_events_with_status()`, which returns events in `EVENT_ACTIVE`. Events transitioned to `EVENT_WAITING_APPROVAL` (parked pending human sign-off) are completely invisible to this dedup check, triggering duplicate events for the same failure.
- **CRITICAL WIP Invariant:** Do NOT modify `get_active_events_with_status()` in `blackboard.py` (doing so would break global system WIP limits and scheduler headroom).
- **Remedy:** In `jenkins_observer.py`, query both `get_active_events_with_status()` AND `get_waiting_approval_events()`, taking their set union for dedup checks.

---

## 4. Regression Verification Test Matrix

1. **Test 1 (Symmetric Recency):** Old successes and old failures (>72h) are pruned equally. Quiet view ratio stays 0% on quiet days.
2. **Test 2 (Ratio Threshold & Minimum Floor):** View with 2/2 failures (100%) but $< min\_failures$ does NOT trigger `BOARD_RED`.
3. **Test 3 (Schmitt Trigger Hysteresis):** Outage triggers at $>70\%$; recovery requires falling strictly below $50\%$.
4. **Test 4 (Durable Outage Fingerprint):** Closing an event does NOT re-emit `BOARD_RED` on the next poll if the failure set timestamp has not progressed.
5. **Test 5 (Recovery Eviction):** Recovered view immediately removes `view-outage:<view>` from `JENKINS_PENDING_ZSET`.
6. **Test 6 (Outage Recheck & Network Fail-Closed):** Jenkins HTTP 502/504 does not cause false positive event emissions.
7. **Test 7 (Waiting Approval Dedup):** Candidate matching an event in `EVENT_WAITING_APPROVAL` is correctly suppressed as duplicate.
8. **Test 8 (Global WIP Non-Regression):** `get_active_events_with_status()` return signature and behavior unchanged.

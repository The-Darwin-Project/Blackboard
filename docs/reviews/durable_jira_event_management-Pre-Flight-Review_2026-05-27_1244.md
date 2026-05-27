# Pre-Flight Review: Durable Jira Event Management

**Date:** 2026-05-27 12:44  
**Plan:** `durable_jira_event_management_906b2f1b.plan.md`

---

## 1. Developer And Technical Summary

* **Overall Confidence Score:** 88%
* **Status:** :rocket: Ready
* **Critical Blockers:** None. All tasks are Complicated domain (known patterns to mirror). Two tasks need attention on Redis access injection into the stateless `routes/jira.py`.

---

## 2. Task-by-Task Analysis

| Step # | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
|:---|:---|:---|:---|:---|
| 1 | Replace `_analyzed_issues` with Redis GET/SET | Complicated | 92% | Clear pattern from GitLab Headhunter. `blackboard.redis` is directly accessible. Minor: need to decide JSON serialization format and handle `None` returns gracefully. |
| 2 | Extract `_get_active_jira_keys()` from flow gate | Simple | 98% | Logic already exists in `check_flow_gate()` (lines 576-586). Extract, return `set[str]` of issue keys instead of count. |
| 3 | Cold-start recovery (detect existing bot comments) | Complicated | 82% | Requires an extra Jira API call per Planning issue on first poll. Risk: rate limiting if many issues exist. Need to batch or limit to first-poll-only flag. |
| 4 | Add `POST /jira/missions/{key}/retry` endpoint | Complicated | 85% | `routes/jira.py` is currently stateless (no Redis). Need to inject `Depends(get_blackboard)` -- pattern exists in other routes (`queue.py`). The endpoint also optionally transitions Jira status -- need to clarify: always transition or only if not already in "To Do"? |
| 5 | Update `reanalyze` to clear Redis state directly | Simple | 95% | Same Redis injection as step 4, then `redis.delete(key)`. Trivial once step 4's dependency injection is in place. |
| 6 | UI: Add Retry action to sidebar + API client | Simple | 97% | Existing pattern: `postJiraAction` already handles `'approve' | 'reanalyze' | 'dismiss'`. Add `'retry'` to the union. Menu item follows the same structure as existing items. |

---

## 3. Gap Analysis

### Step 1 (Redis state -- 92%)

* **Ambiguity:** Plan says "via `self.blackboard` or direct Redis client" -- should be `self.blackboard.redis` (direct async Redis client) since there's no blackboard method for arbitrary key GET/SET. This is how the GitLab Headhunter's feedback keys work.
* **Safety:** Need to handle the case where Redis returns `None` (key expired or never set) gracefully -- treat as "not analyzed" and proceed. The `_analyzed_issues.get(key, {}).get("phase")` pattern needs a Redis equivalent.

### Step 3 (Cold-start -- 82%)

* **Ambiguity:** "On first poll after restart" -- how do we detect "first poll"? Options: (a) check if Redis key exists for the issue and skip cold-start if it does, (b) use a `self._cold_started = False` flag that flips after first cycle. Option (a) is simpler -- if Redis key is missing AND bot comment exists, reconstruct. No special flag needed.
* **Safety:** If the Jira API is slow or rate-limited during cold start (many Planning issues), the first poll cycle could take 10+ seconds. Mitigation: only check comments for issues NOT in Redis (natural throttle -- after first poll, all are in Redis).

### Step 4 (Retry endpoint -- 85%)

* **Context:** `routes/jira.py` currently imports no state dependencies. Need to add `from ..dependencies import get_blackboard` and `Depends(get_blackboard)` parameter to the route handler. Pattern is well-established in `queue.py`, `events.py`, etc.
* **Ambiguity:** "If there's a closed/failed event for this key, optionally transition Jira back to To Do" -- the word "optionally" is vague. Recommendation: always transition to "To Do" if current status is not already "To Do" or "Planning". This makes the retry button a one-click reset.

---

## 4. Path to Green (Remediation)

- [x] **Architecture:** Mermaid diagram included in plan -- adequate
- [ ] **Clarify Step 1:** Use `self.blackboard.redis.get/set/delete` with `darwin:headhunter:jira:{key}` prefix. JSON encode/decode with `json.dumps/loads`. TTL via `ex=604800` (7 days in seconds).
- [ ] **Clarify Step 3:** No cold-start flag needed. Logic: if Redis key missing for a Planning issue, check comments for bot `accountId`. If found, SET Redis state. This naturally runs only once per issue (subsequent polls hit Redis).
- [ ] **Clarify Step 4:** Retry endpoint should: (1) delete Redis key, (2) transition Jira to "To Do" if not already there, (3) return `{"status": "retried", "key": key}`. Add `blackboard: BlackboardState = Depends(get_blackboard)` to the route.
- [ ] **Add to Plan:** Rate limit guard for cold-start -- cap at 10 Jira API comment-checks per poll cycle to avoid hitting the 350 req/s burst limit on first startup with many issues.
- [ ] **Safety:** Add a unit test for `_get_active_jira_keys()` to confirm it returns issue keys from `jira_context`, not event IDs.
- [ ] **Safety:** Add a unit test verifying Redis state survives simulated pod restart (write state -> clear in-memory -> read from Redis).

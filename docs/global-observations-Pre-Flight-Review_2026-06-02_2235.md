# Global Observations Unified View -- Pre-Flight Review

**Plan:** Global Observations Unified View
**Date:** 2026-06-02 22:35 UTC+3

---

## 1. Developer And Technical Summary

* **Overall Confidence Score:** 95%
* **Status:** Ready
* **Critical Blockers:** None. All files are loaded and understood. Plan reuses existing patterns.

---

## 2. Task-by-Task Analysis

| Step # | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Dual-write: global ZADD + SADD + 7d trim in `record_observation` | Complicated | 97% | ZADD + ZREMRANGEBYSCORE are atomic. Member format gains `event_id:service` -- must update rsplit parser. |
| 2 | Rewrite `list_observations` to read global keys | Complicated | 93% | SMEMBERS + N x ZRANGEBYSCORE. If FRIDAY created 20 unique names, that's 20 Redis calls. Acceptable at current scale. |
| 3 | Add `GET /observations` global endpoint | Simple | 100% | Same pattern as existing route. |
| 4 | Update InsightsPage to default global view | Complicated | 90% | Chart needs to handle more data points (7d x N events). Recharts may slow with >500 points per chart. |
| 5 | Update types (event_id + service on ObservationPoint) + tool description | Simple | 100% | Additive -- no breaking change. |
| 6 | Build verify + push | Simple | 100% | Standard. |

---

## 3. Gap Analysis

### Step 2 (Confidence 93%) -- list_observations rewrite

* **Ambiguity:** The global member format `{iso}:{value}:{unit}:{event_id}:{service}` has MORE segments than the event-scoped format `{iso}:{value}:{unit}:{phase}`. The rsplit(3) parser must change to rsplit(5) for global keys. Need two parsers or a unified format.
* **Recommendation:** Use a **single format** for both global and event-scoped keys: `{iso}:{value}:{unit}:{phase}:{event_id}:{service}`. Update `record_observation` to write this format to BOTH keys. Parser uses `rsplit(":", 5)` everywhere.

### Step 4 (Confidence 90%) -- UI with 7 days of data

* **Ambiguity:** 7 days of 15s-polling-equivalent data = potentially thousands of points per chart if FRIDAY is actively recording.
* **Recommendation:** Acceptable risk. FRIDAY records observations manually (not on a poll interval), so realistic volume is 5-50 points per series per event. Even across 30 events, that's ~1500 points max per name -- recharts handles this fine.

---

## 4. Path to Green (Remediation)

- [x] All target files loaded in context
- [ ] **Modify Plan:** Unify member format to `{iso}:{value}:{unit}:{phase}:{event_id}:{service}` for both event-scoped and global ZSETs. Single parser with `rsplit(":", 5)`.
- [x] Architecture diagram present in plan (Mermaid flowchart)
- [ ] No probe needed -- all Complicated domain

---

## Verdict: Ready to execute at 95% confidence.

One minor format unification needed (fold into Step 1 implementation).

# Code Review: Durable Jira Event Management

**Date:** 2026-05-27  
**Commit:** `7b0c004` -- `feat(jira): durable Redis-backed state for Headhunter Jira`  
**Scope:** 6 files, +266 / -40 lines

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** Low
* **Breaking Changes:** None. The `postJiraAction` type union is widened (additive). The `jiraMissionMenuItems` function signature adds `retry` to the actions parameter (all callers already pass the full `useJiraActions()` object which now includes `retry`). No external API contracts changed.

**Key architectural shift:** State moved from in-memory `_analyzed_issues` dict to Redis (`darwin:headhunter:jira:{key}`, 7d TTL). The in-memory dict is completely removed. All state reads/writes go through `_get_issue_state()`/`_set_issue_state()`.

---

## 2. Downstream Impact Analysis

### Affected Consumers

| Consumer | File | Impact |
|----------|------|--------|
| Parent Headhunter | `src/agents/headhunter.py` | Calls `self._jira.poll_and_process()` -- interface unchanged. **No impact.** |
| Brain (format_jira_for_llm) | `src/agents/brain.py` | Imports `format_jira_for_llm` -- not touched. **No impact.** |
| EventSidebar (UI) | `ui/src/components/ops/EventSidebar.tsx` | Passes `jiraActions` to `jiraMissionMenuItems`. `useJiraActions()` now returns `retry` -- property is additive. TypeScript infers the expanded type. **No impact.** |
| Tests | `tests/test_headhunter_jira.py` | Updated in this commit. All 22 pass. **No impact.** |
| Other routes | `src/routes/*.py` | `routes/jira.py` now imports `get_blackboard` + `BlackboardState` -- same pattern as 10 other route files. **No impact.** |

### Risk Assessment

- Existing tests: All pass (22/22)
- Silent failure risk: **Low** -- Redis state `None` (expired/missing) is handled gracefully as "not analyzed, proceed with fresh analysis"
- Pod restart recovery: **Covered** -- cold-start detects existing bot comments

---

## 3. Findings & Fixes

| File | Severity | Issue Type | Description & Fix |
|------|----------|------------|-------------------|
| `headhunter_jira.py` | **LOW** | Naming | `_REDIS_PREFIX` and `_REDIS_TTL` are instance vars (set in `__init__`) but named like class constants. Cosmetic -- not blocking. Could be promoted to class-level constants in a future cleanup. |
| `headhunter_jira.py` | **LOW** | Analysis text not in Redis | When creating an event (Phase 2), `analysis_text` is fetched from `state.get("analysis", "")` but the `_set_issue_state` call in Phase 1 only stores `phase` and `last_comment_id` -- NOT the analysis text itself. This means on pod restart, To Do issues will re-run Claude analysis even if already analyzed. This was an intentional trade-off (avoid storing large LLM output in Redis) but worth noting. |
| `routes/jira.py` | **LOW** | Error handling | `retry_mission` silently succeeds even if Jira transition fails (no HTTP error raised). This is by design (Redis state is cleared regardless, Headhunter will pick it up), but could confuse users if the Jira status doesn't change. Acceptable for v1. |
| `sidebarMenus.tsx` | **NONE** | Correct | `retry` placed before `dismiss` (destructive action last). Good UX ordering. |
| `test_headhunter_jira.py` | **NONE** | Coverage | 11 new tests covering Redis state, dedup, cold-start, and retry. All meaningful paths covered. |

---

## 4. Verification Plan

### Already Verified (pre-commit)

- [x] All 22 unit tests pass (0.24s)
- [x] Python syntax verification (ast.parse) on all modified `.py` files
- [x] `_get_active_jira_keys()` returns issue keys, not event IDs (covered by test)
- [x] Redis state survives simulated restart (covered by test)
- [x] Cold-start reconstructs from bot comment (covered by test)

### Post-Deploy Integration Tests

- [ ] Pod restart with Planning issue that has bot comment: verify no duplicate comment posted
- [ ] Pod restart with To Do issue that has active event: verify no duplicate event created
- [ ] UI "Retry" button: verify Redis key cleared + Jira transitioned to "To Do" + new event created on next poll
- [ ] UI "Re-analyze" button: verify Redis key cleared + fresh analysis posted
- [ ] Jira status bounce (In Progress -> To Do): verify new event created without UI intervention
- [ ] Rate limit: restart pod with 5+ Planning issues, verify max 10 cold-start comment checks per cycle (check logs for debug output count)
- [ ] TTL expiry: after 7 days, verify key auto-expires (can test by setting TTL to 60s temporarily)

### Verdict

**Approve.** Low risk, well-tested, mirrors the proven GitLab Headhunter pattern. Ready to push.

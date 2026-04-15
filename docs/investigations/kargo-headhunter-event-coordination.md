# Investigation: Kargo-Headhunter Event Coordination Gap

**Date:** 2026-04-15
**Status:** Open -- design needed
**Priority:** Medium (operational waste, not a bug)

---

## Problem

When a Kargo promotion fails and the KargoObserver creates an event, the promotion's retry often creates a new MR in GitLab. The Headhunter then picks up the MR as a `review_requested` todo and creates a **second event** for the same underlying work. Both events run independently -- double the agent dispatches, double the ephemeral cost, no coordination.

## Evidence from Production (20-hour window, 2026-04-14/15)

### Example 1: kubevirt-v4.16

- **evt-9f113407** (source=aligner, subject_type=kargo_stage): `kubevirt-v4.16@kargo-kubevirt-v4-16` -- KargoObserver detected failed promotion, sysadmin retested pipeline, deferred 1200s waiting for Konflux pipeline
- **evt-76b30183** (source=headhunter): `kubevirt` -- Headhunter picked up the same MR !49 as a GitLab todo, dispatched developer to check pipeline status

Both events tracked the same MR !49, same pipeline, same outcome. Independent agents, independent deferrals.

### Example 2: ocp-virt-validation-checkup

- **evt-49dcef5e** (source=headhunter): `ocp-virt-validation-checkup` -- Headhunter MR !215
- Kargo stage `kubevirt-v4.22` in project `kargo-ocp-virt-validation-checkup-v4-22` was the promotion source

## Root Cause

### Dedup misses cross-source events

The existing dedup in `brain.py._process_event_inner` (line ~431) checks:

```python
if existing.service == event.service and existing.status.value in ("new", "active", "deferred"):
```

But Kargo and Headhunter events use different service names for the same work:
- Kargo: `kubevirt-v4.16@kargo-kubevirt-v4-16` (stage@project)
- Headhunter: `kubevirt` (resolved from GitLab project path)

### Cross-event awareness is observational only

The Brain's `context/cross-event.md` skill shows "Related Active Events" in the prompt header. But the relatedness check in `_compute_context_flags` matches on `event.service`, which again misses the cross-source match.

### The MR URL is the shared key

Both events reference the same MR URL:
- Kargo `kargo_context.mr_url`: `https://gitlab.cee.redhat.com/.../merge_requests/49`
- Headhunter `gitlab_context.target_url`: `https://gitlab.cee.redhat.com/.../merge_requests/49`

This is the natural join key, but it's never compared.

## Proposed Solutions (Trade-offs)

### Option A: Brain skill guidance (KISS, no code changes)

Update `context/kargo-environment.md` and `source/headhunter.md` with:

> "If a Related Active Event exists with source=aligner and service containing `@kargo-`, and this event's MR was created by a Kargo promotion (Bot Instructions mention 'Kargo tracks its state'), close this event as duplicate and defer to the Kargo event."

**Pro:** Zero code changes. LLM reasoning handles the coordination.
**Con:** Depends on the LLM noticing the relationship. The related events may not show if service names don't match.

### Option B: MR URL cross-match in dedup (Complicated)

In `brain.py._process_event_inner` dedup logic, also check:

```python
# Current: service name match
if existing.service == event.service ...

# Added: MR URL cross-match for kargo <-> headhunter
new_mr = new_ctx.get("target_url") or (new_evidence.kargo_context or {}).get("mr_url")
existing_mr = ex_ctx.get("target_url") or (getattr(existing.event.evidence, "kargo_context", None) or {}).get("mr_url")
if new_mr and existing_mr and new_mr == existing_mr:
    # Same MR -- close as duplicate
```

**Pro:** Deterministic, catches the exact case.
**Con:** Requires code changes in the dedup path.

### Option C: Headhunter filter for Kargo-managed MRs (Upstream prevention)

In the Headhunter's `_classify_todo` or `_build_plan`, detect MR descriptions containing "Kargo tracks its state" and skip event creation entirely. The MR is managed by the Kargo promotion lifecycle, not the Headhunter.

**Pro:** Prevents the duplicate event at the source.
**Con:** Tight coupling between Headhunter and Kargo MR description format.

## Recommended Approach

Start with **Option A** (skill guidance) as a quick win. If the LLM doesn't reliably catch the relationship, implement **Option B** (MR URL cross-match) as the deterministic fix.

## Related Files

### Core files to modify

| File | Purpose |
|---|---|
| `brain_skills/context/cross-event.md` | Cross-event awareness rules. Add Kargo-Headhunter coordination guidance. |
| `brain_skills/context/kargo-environment.md` | Kargo close protocol. Add: "If a Headhunter event exists for this promotion's MR, the Headhunter event should be closed as duplicate." |
| `brain_skills/source/headhunter.md` | Headhunter source rules. Add: "If Bot Instructions say 'Kargo tracks its state', and a Kargo event exists for the same MR, close as duplicate." |

### For Option B (code changes)

| File | Purpose |
|---|---|
| `agents/brain.py` lines 431-465 | Dedup logic in `_process_event_inner`. Add MR URL cross-match. |
| `agents/brain.py` lines 1040-1070 | `_compute_context_flags`. Enrich "related events" to include MR URL matches, not just service name matches. |

### For Option C (upstream prevention)

| File | Purpose |
|---|---|
| `agents/headhunter.py` | `_classify_todo` or `_build_plan`. Detect Kargo-managed MRs and skip. |

## Context for the session

- The KargoObserver creates events with `source=aligner`, `subject_type=kargo_stage`, `service={stage}@{project}`
- The Headhunter creates events with `source=headhunter`, `subject_type=service`, `service={resolved_name}`
- Both carry the MR URL: `kargo_context.mr_url` and `gitlab_context.target_url`
- The Kargo MR description always contains `"Do NOT close this MR -- Kargo tracks its state."`
- The Brain already has cross-event awareness via `context/cross-event.md` and related events in the prompt header
- The ops journal (`darwin:journal:{service}`) is per-service, so entries from Kargo events and Headhunter events are in different journals (different service keys)

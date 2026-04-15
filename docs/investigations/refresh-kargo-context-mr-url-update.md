# Investigation: refresh_kargo_context Should Update mr_url

**Date:** 2026-04-15
**Status:** Open -- ready to implement
**Priority:** Low (operational efficiency, not a bug)
**Parent:** kargo-headhunter-event-coordination.md

---

## Problem

When a Kargo promotion fails and the sysadmin remediates by closing the old MR and re-promoting, the new promotion creates a new MR. The event's `kargo_context.mr_url` still points to the old MR (set at event creation). When `refresh_kargo_context` fires on defer-wake, it reads the fresh stage status (which includes the new MR URL via `get_stage_status`) but only puts `promotion`, `phase`, `failed_step`, and `message` into the conversation turn -- it **drops `mr_url`** and never updates the event evidence.

This means the cross-source event merge (shipped in commit 28d5db8) can't match across re-promotions.

## Evidence from Production (2026-04-15)

- `evt-540d16cd` (Kargo): `kubevirt-migration-operator-v4.20@kargo-kubevirt-migration-controller-v4-20`
  - Created with `kargo_context.mr_url` = MR !45
  - Sysadmin closed !45, re-promoted -> new MR !46 created
  - Event deferred 1500s waiting for !46 pipeline
- `evt-5d1c7fcb` (Headhunter): `kubevirt-migration-controller`, MR !46
  - Created during the Kargo event's defer window
  - Cross-source merge did NOT fire (Kargo event had !45, Headhunter had !46)
  - Headhunter event resolved independently (MR already merged, CLEAR, no agent dispatch)

## Impact

Low. The Headhunter event for the new MR resolves cheaply when the MR is already merged (one LLM cycle, no agent dispatch). The expensive double-dispatch scenario from the original investigation (both events deferring and dispatching agents for the same pipeline) doesn't apply here because the new MR is typically in a better state than the failed one.

## Proposed Fix

In `brain.py` `refresh_kargo_context` handler (line ~2590), after reading the fresh stage status, update `kargo_context.mr_url` on the event evidence if it changed:

```python
# After getting state from get_stage_status (line 2584)
new_mr_url = state.get("mr_url", "")
if new_mr_url and new_mr_url != kc.get("mr_url", ""):
    kc["mr_url"] = new_mr_url
    await self.blackboard.update_event_evidence_field(
        event_id, "kargo_context", kc
    )
    logger.info(f"Updated kargo_context.mr_url for {event_id}: {new_mr_url}")
```

Also include `mr_url` in the result text so the Brain sees the new MR in the conversation:

```python
result_text = (
    f"Kargo Stage: {stage}@{project}\n"
    f"Promotion: {state.get('promotion', '?')}\n"
    f"Phase: {state.get('phase', '?')}\n"
    f"Failed Step: {state.get('failed_step', 'N/A')}\n"
    f"Message: {state.get('message', '')}"
    f"\nMR URL: {state.get('mr_url', 'N/A')}"
)
```

## Dependencies

- Need to verify `blackboard.update_event_evidence_field` exists or add it (partial evidence update without replacing the whole object).
- Alternative: read the full evidence, mutate `kargo_context.mr_url`, write it back via existing `blackboard` methods.

## Timing

The fix applies on defer-wake. If the Headhunter arrives during the defer (before wake), the URL is still stale and the merge won't fire. This is acceptable -- the Headhunter event resolves cheaply in that case. The fix covers the scenario where the Headhunter arrives *after* the defer-wake but before the Kargo event closes.

## Related Files

| File | Change |
|---|---|
| `agents/brain.py` lines 2590-2606 | `refresh_kargo_context` handler: update `kargo_context.mr_url` + include in result text |
| `state/blackboard.py` | May need `update_event_evidence_field` or use existing partial update method |

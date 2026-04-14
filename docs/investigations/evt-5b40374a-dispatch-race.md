# Investigation: evt-5b40374a Dispatch Race Condition

**Event:** evt-5b40374a
**Date:** 2026-04-14
**Service:** quata-app-stage@quata-app (Kargo stage)
**Source:** aligner (subject_type=kargo_stage)
**Trigger:** User right-click "Create Event" from Kargo Stages tree in dashboard
**Outcome:** Event resolved successfully (11 turns, root cause identified, maintainer notified, incident created)
**Bug:** Local sysadmin sidecar competed with ephemeral agent during dispatch

---

## Symptom

User observed in the dashboard UI:
1. Internal sysadmin agent started processing
2. Internal agent disconnected
3. OnCall (ephemeral) agent started
4. OnCall agent stopped mid-execution
5. Internal agent resumed
6. Internal agent stopped
7. OnCall agent resumed and completed

This flickering UX is confusing and makes the system appear broken.

## Timeline (from Brain pod logs)

| Time | Actor | Action |
|---|---|---|
| 18:34:43 | Local sysadmin sidecar | Booted, WS errors, reconnecting |
| 18:34:50 | Local sysadmin sidecar | Connected to Brain WS |
| 18:37:02 | Brain | Event created, classify_event -> COMPLICATED |
| 18:37:07 | Brain | consult_deep_memory |
| 18:37:24 | Brain | select_agent(sysadmin, investigate) |
| 18:37:26 | Brain | **Wrote event MD to /data/gitops-sysadmin/** (local sidecar volume) |
| 18:37:27 | Brain | Agent task started, **Triggered TaskRun** (ephemeral) |
| 18:37:27 - 18:38:57 | Local sidecar + Ephemeral | **RACE**: local sidecar reads event MD from shared volume, ephemeral pod spinning up |
| 18:38:57 | Ephemeral provisioner | **Ephemeral dispatch failed (1/2)** -- cleanup + retry |
| 18:39:02 | Ephemeral provisioner | Triggered replacement TaskRun |
| 18:39:08 | Ephemeral agent (mlgpg) | Registered, marked busy |
| 18:39:30 | Ephemeral agent (mlgpg) | Finished (22 seconds), unregistered |
| 18:39:31 | Brain | Agent task completed, processes result |
| 18:39:35 | Brain | select_agent(sysadmin) AGAIN (second dispatch) |
| 18:39:36 | Brain | **Wrote event MD to /data/gitops-sysadmin/** again |
| 18:39:36 | Ephemeral provisioner | Triggered new TaskRun |
| 18:39:41 | Ephemeral agent (pjkxd) | Registered, marked busy |
| 18:40:07 | Ephemeral agent | sysadmin.message (progress) |
| 18:45:42 | Ephemeral agent | sysadmin.plan (investigation complete) |
| 18:45:55 | Brain | notify_user_slack (root cause found) |
| 18:46:01 | Brain | create_incident |
| 18:46:11 | Brain | close_event |
| 18:46:39 | Archivist | Archived to Qdrant |

## Root Cause

The dispatch path in `brain.py._run_agent_task` has a race condition:

1. **Event MD volume write is unconditional** -- when `select_agent(sysadmin)` fires, `_run_agent_task` writes the event markdown to `/data/gitops-sysadmin/events/event-{id}.md` (the local sidecar's shared volume). This happens BEFORE the ephemeral dispatch decision.

2. **Local sidecar file watcher picks up the file** -- the local sysadmin sidecar has a file watcher on its events directory. When a new `.md` file appears, it starts processing via its HTTP `/execute` endpoint.

3. **Ephemeral TaskRun starts concurrently** -- the Tier 1 ephemeral check correctly identifies `subject_type=kargo_stage` and triggers a TaskRun. But the TaskRun takes 5-10 seconds to schedule a pod.

4. **Both agents compete** -- the local sidecar starts immediately (file already on disk), while the ephemeral pod is still scheduling. The registry sees both trying to register for the same event. The result is the flickering UI behavior.

## Scope

This is a **pre-existing bug** in the dispatch path, not specific to KargoObserver. It affects all Tier 1 ephemeral sources (headhunter, timekeeper, kargo_stage). It was less visible for headhunter events because:
- Headhunter events typically arrive when the local sysadmin sidecar is already busy with another task
- KargoObserver events often arrive when the local sidecar is idle (metrics events don't use sysadmin)

## Proposed Fix

In `brain.py._run_agent_task`, gate the event MD volume write:

```python
# Current: unconditional write
self._write_event_to_volume(event_id, agent_name, event_md)

# Fix: skip volume write when ephemeral dispatch is active
if not use_ephemeral:
    self._write_event_to_volume(event_id, agent_name, event_md)
```

Ephemeral agents receive the event document via the `/events/{id}/document` REST endpoint (already implemented at `routes/events.py:43`), not from the shared volume. The volume write is only needed for local sidecars.

## Log Evidence

### Sidecar WS connection (from user-provided sidecar log)
```
[2026-04-14T18:34:43.905Z] WS error:
[2026-04-14T18:34:43.905Z] Reconnecting in 1000ms
[2026-04-14T18:34:43.905Z] Disconnected from Brain
[2026-04-14T18:34:44.909Z] WS error:
[2026-04-14T18:34:44.909Z] Reconnecting in 2000ms
[2026-04-14T18:34:46.917Z] WS error:
[2026-04-14T18:34:46.917Z] Reconnecting in 4000ms
[2026-04-14T18:34:50.950Z] Connected to Brain: ws://localhost:8000/agent/ws
```

### Ephemeral dispatch (from Brain pod)
```
18:37:27 - Agent task started: sysadmin (mode=investigate) for evt-5b40374a
18:37:27 - Triggered TaskRun for evt-5b40374a (status=202)
18:38:57 - Ephemeral dispatch failed for evt-5b40374a (1/2): . Cleaning up and retrying.
18:39:08 - Registered agent oncall-darwin-oncall-mlgpg-pod (ephemeral=True, event=evt-5b40374a)
18:39:08 - Ephemeral retry succeeded for evt-5b40374a after cleanup
```

### Event resolution
```
18:45:55 - Brain LLM decision: notify_user_slack
18:45:56 - Slack DM: "Investigation revealed that cnv-fbc-quota was decommissioned... but Kargo project quata-app was left behind"
18:46:01 - Brain LLM decision: create_incident
18:46:11 - Brain LLM decision: close_event
18:46:11 - Closed event: evt-5b40374a
```

## Event Outcome (despite the bug)

The KargoObserver feature worked end-to-end:
- User created event via dashboard Kargo Stages tree
- Brain classified as COMPLICATED, dispatched sysadmin
- Agent investigated, found root cause: `cnv-fbc-quota` app deleted on 2026-03-03 (commit c1279729) but Kargo project `quata-app` was left behind
- Brain notified maintainer via Slack DM
- Brain created incident
- Brain closed event with documented root cause
- Archivist archived to Qdrant for deep memory

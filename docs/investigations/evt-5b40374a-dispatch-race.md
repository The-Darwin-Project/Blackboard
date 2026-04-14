# Investigation: evt-5b40374a Dispatch Race Condition

**Event:** evt-5b40374a
**Date:** 2026-04-14
**Service:** quata-app-stage@quata-app (Kargo stage)
**Source:** aligner (subject_type=kargo_stage)
**Trigger:** User right-click "Create Event" from Kargo Stages tree in dashboard
**Outcome:** Event resolved successfully (11 turns, root cause identified, maintainer notified, incident created)
**Bug:** Two bugs -- missing ALIGNER_MAX_ACTIVE config + unconditional volume write before ephemeral decision
**Status:** Fixed (2026-04-14)

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
| 18:37:27 - 18:38:57 | Local sidecar + Ephemeral | **RACE**: "sysadmin starting..." broadcast fires before ephemeral decision, UI shows activity during 90s provisioning wait |
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

## Root Cause: Two Bugs, Not One

### Bug 1: Missing ALIGNER_MAX_ACTIVE capacity config

When `kargo_stage` was added to the Tier 1 ephemeral condition, the capacity env var was not wired. The lookup chain:

```
ensure_agent(source=event_doc.source)          # brain.py -- source="aligner" for kargo events
  -> get_source_limit("aligner")               # ephemeral_provisioner.py
    -> os.environ.get("ALIGNER_MAX_ACTIVE", "1") # env var NOT SET -> default=1
```

With limit=1, only one kargo ephemeral event can run at a time. evt-329de81a hit this limit (evt-5b40374a had the slot) and was deferred 3x for 120s each.

Headhunter events work because `HEADHUNTER_MAX_ACTIVE=2` is properly wired through Helm values -> deployment template -> ArgoCD overlay.

**Fix:** Wired `ALIGNER_MAX_ACTIVE` through Helm: `aligner.maxActive: "2"` in values.yaml, `ALIGNER_MAX_ACTIVE` env var in deployment.yaml, production override in darwin-blackboard.yaml.

### Bug 2: Unconditional volume write before ephemeral decision

The `select_agent` handler called `write_event_to_volume` unconditionally at line 1704, BEFORE launching `_run_agent_task` where the ephemeral decision is made. When ephemeral capacity was hit and the event deferred, the file stayed on disk for 120+ seconds. Same issue in the `message_agent` handler at line 1819.

Note: the local sidecar does NOT have a file watcher -- it only processes tasks via WS dispatch. The stale file is unnecessary I/O, not a direct race cause. The UI flickering comes from the "agent starting..." broadcast firing before the ephemeral decision.

**Fix:** Moved the volume write into `_run_agent_task`, gated by `agent_id_override is None` (local sidecar dispatch only). This gate correctly handles:
- Non-ephemeral sources -> local sidecar -> writes file
- Ephemeral provision success -> ephemeral agent (REST) -> skips file
- Circuit breaker fallback -> local sidecar -> writes file
- Capacity defer -> returns early -> no dispatch, no file

## Second Case: evt-329de81a (Aligner-created, same root cause)

**Event:** evt-329de81a (must-gather-v4.13@kargo-cnv-must-gather-v4-13)
**Trigger:** KargoObserver watch callback (automatic detection, not dashboard)

```
18:40:10 - Wrote event MD to /data/gitops-sysadmin/events/event-evt-329de81a.md
18:40:11 - Ephemeral limit for 'aligner' reached (1/1). Event evt-329de81a stays queued.
18:40:11 - Deferring evt-329de81a for 120s: Waiting for ephemeral agent slot
18:42:34 - Deferring again for 120s
18:45:33 - Deferring again for 120s
```

Deferred 3 times because `ALIGNER_MAX_ACTIVE` defaulted to 1.

## Comparison: evt-1f624e95 (headhunter, clean dispatch)

```
18:58:33 - select_agent -> developer
18:58:33 - Wrote event MD to /data/gitops-developer/
18:58:34 - Agent task started: developer (mode=execute)
18:58:34 - Triggered TaskRun (status=202)
18:58:46 - Registered oncall-gzjl8-pod (ephemeral=True)   <- 12 seconds, clean
```

`HEADHUNTER_MAX_ACTIVE=2` -> capacity available -> no deferral -> no flickering.

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

## Event Outcomes (despite the bug)

### evt-5b40374a (quata-app-stage)
- User created event via dashboard Kargo Stages tree
- Agent investigated, found root cause: `cnv-fbc-quota` app deleted on 2026-03-03 (commit c1279729) but Kargo project `quata-app` was left behind
- Brain notified maintainer via Slack DM, created incident, closed
- Archivist archived to Qdrant for deep memory

### evt-329de81a (must-gather-v4.13)
- KargoObserver auto-detected from watch stream
- Brain used `refresh_kargo_context` tool (working correctly)
- Agent investigating MR merge timeout (still active)

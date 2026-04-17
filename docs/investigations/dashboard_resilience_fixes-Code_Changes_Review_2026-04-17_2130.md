# Code Changes Review: Dashboard Resilience Three-Issue Fix

**Plan:** `dashboard_resilience_fixes_3d6572c3.plan.md`
**Reviewer:** Systems Architect (diff-based, final pass)
**Date:** 2026-04-17T21:30
**Diff scope:** 9 modified files + 2 new files, 155 insertions, 12 deletions

---

## 1. Developer + Technical Impact Summary

| Metric | Value |
| :--- | :--- |
| **Risk Level** | **Low** |
| **Breaking Changes** | None -- all additive (new REST endpoint, new WS message type, new event handlers, new callbacks) |
| **TypeScript Build** | R1 scoping blocker from prior review is resolved (handlers hoisted to `let` at `useEffect` scope) |
| **Python Imports** | Clean -- no circular dependencies introduced |
| **New API Surface** | `GET /api/kargo/stages` (typed `KargoStageSnapshot` response model) |
| **New WS Message** | `event_status_changed` with `{event_id, status}` payload |
| **New Module Exports** | `client.ts`: `setOnUnauthorized`, `setWSAuthFailureCallback`, `getWSAuthFailureCallback`, `getKargoStages` |

---

## 2. Downstream Impact Analysis

### Import Graph (verified no circular dependencies)

```
client.ts <-- AuthContext.tsx (setTokenGetter, setOnUnauthorized, setWSAuthFailureCallback)
client.ts <-- WebSocketContext.tsx (getWSAuthFailureCallback)
client.ts <-- useKargo.ts (getKargoStages)
AuthContext.tsx <-- WebSocketContext.tsx (useAuth)
WebSocketContext.tsx <-- OpsStateContext.tsx (useWSMessage, useWSReconnect)
useKargo.ts <-- OpsStateContext.tsx (useKargoStages, useKargoStagesInvalidation)
useKargo.ts <-- hooks/index.ts (re-export)
```

All arrows are unidirectional. `client.ts` is the leaf node -- imports from no context or hook.

### Consumer Impact

| Consumer | What Changed | Risk | Verified |
| :--- | :--- | :--- | :--- |
| `EventSidebar.tsx` | Consumes `kargoStages` from `useOpsState()` | Type unchanged (`KargoStageStatus[]`). Data now from React Query instead of useState. `initialData: []` prevents undefined. | No change needed |
| `sidebarMenus.tsx` | Imports `KargoStageStatus` type only | No runtime impact | No change needed |
| `ConversationFeed.tsx` | Subscribes to `useWSMessage` | New `event_status_changed` type tolerated (falls through to no-op) | No change needed |
| `App.tsx` | Provider tree | `QueryClientProvider > AuthProvider > WebSocketProvider > OpsStateProvider` order unchanged | Correct |
| All REST consumers | `fetchApi` now calls `_onUnauthorized` on 401 | Callback is null until AuthProvider wires it. No impact when auth disabled. | Safe |

### Silent Failure Risk

| Scenario | Risk | Mitigation |
| :--- | :--- | :--- |
| Query key mismatch between `useKargoStages` and WS cache set | WS optimistic update silently does nothing | `KARGO_STAGES_KEY` constant used in both `useKargoStages()` and `useKargoStagesInvalidation()`. Single source of truth. |
| `event_status_changed` broadcast but no UI handler | Status change invisible | Handler added in `OpsStateContext.tsx` -- `invalidateActive()` + `invalidateEvent()` |
| 4001 close but `_wsAuthFailureCallback` not yet wired | No logout on auth rejection | `_wsAuthFailureCallback` is set in AuthProvider `useEffect` before WebSocketProvider mounts (provider order). Startup race: callback is `null` only during AuthProvider's async config fetch, before any WS connection exists. |

---

## 3. Findings & Fixes

| File | Severity | Issue Type | Description |
| :--- | :--- | :--- | :--- |
| All files | PASS | Build | No linter errors on any modified file. |
| `brain.py` | PASS | Placement | All 3 broadcast sites verified: (1) ~608 inside `if transition_event_status()` guard, (2) ~2081 after both Redis writes inside `if event:` guard, (3) ~3919 inside `if transitioned:` before `_waiting_for_user` check. |
| `brain.py` | PASS | Boundary | Broadcasts at call sites, NOT inside `transition_event_status()`. Hexagonal boundary preserved. |
| `AuthContext.tsx` | PASS | Scoping | R1 resolved: handlers declared as `let` at `useEffect` scope, assigned inside IIFE, guarded with `if (handler)` in cleanup. |
| `AuthContext.tsx` | PASS | Cleanup | All 4 OIDC listeners properly removed on unmount via `remove*` methods. |
| `AuthContext.tsx` | PASS | Documentation | Three-layer defense-in-depth documented in `@ai-rules` #4-#6 with rationale for each design choice. |
| `client.ts` | PASS | Callback pattern | `setOnUnauthorized`, `setWSAuthFailureCallback`, `getWSAuthFailureCallback` follow `setTokenGetter` pattern exactly. |
| `client.ts` | PASS | 401 placement | `_onUnauthorized()` called after error body parse, before `throw ApiError`. Correct. |
| `WebSocketContext.tsx` | PASS | 4001 handling | `onclose(event)` signature, early return on `event.code === 4001`, no reconnect backoff. |
| `OpsStateContext.tsx` | PASS | Migration | `useState` replaced with `useKargoStages()` hook. WS handler uses `setKargoStages` (query cache setter). `invalidateKargoStages()` added to reconnect handler. |
| `routes/kargo.py` | PASS | Contract | `KargoStageSnapshot` Pydantic model enforces typed API response. |
| `dependencies.py` | PASS | Convention | `get_kargo_observer` is `async def`, matching all other DI getters. `@ai-rules` header present. |
| `brain.py` `@ai-rules` | PASS | Documentation | Rule #27 documents `event_status_changed` broadcast pattern. Rule #28 documents pre-existing defer write debt with remediation path. |

**No findings requiring fixes.** All prior review items (R1-R5, B1-B3, S1-S5, F1-F3) verified resolved in the diff.

---

## 4. Verification Plan

### Build Verification

| Check | Command | Expected |
| :--- | :--- | :--- |
| TypeScript | `cd ui && npx tsc -b --noEmit` | Exit 0, zero errors |
| Python imports | `python -c "from src.routes.kargo import router"` | No ImportError |

### Issue 1 -- Kargo REST Fallback

| Flow | Test |
| :--- | :--- |
| Endpoint returns data | `curl -s localhost:8000/api/kargo/stages \| jq` -- returns `KargoStageSnapshot[]` |
| Observer disabled | `KARGO_OBSERVER_ENABLED=false` -- endpoint returns `[]` |
| Polling fallback | Block WS in browser DevTools, wait 30s, verify sidebar Kargo tree refreshes |
| Initial load | Fresh page load (no prior WS) -- Kargo count populates from REST before first WS message |
| WS optimistic update | With WS open, trigger Kargo failure -- sidebar updates in < 1s (WS push), not 30s (poll) |

### Issue 2 -- Event Status Broadcast

| Flow | Test |
| :--- | :--- |
| NEW -> ACTIVE | Create chat event, watch DevTools WS frames for `event_status_changed` with `status: "active"` |
| ACTIVE -> DEFERRED | Trigger CLEAR event that defers in one cycle -- sidebar moves event to deferred section immediately |
| DEFERRED -> ACTIVE | Wait for defer TTL to expire -- sidebar moves event back to active section |
| Failed transition | Concurrent status race (edge case) -- `transition_event_status` returns false, no broadcast fires |

### Issue 3 -- Dex Token Expiry

| Flow | Test |
| :--- | :--- |
| Token expiry (Layer 1) | Set short Dex token TTL, wait -- `[Auth] Token expired` in console, LoginPage renders |
| Silent renew failure | Kill Dex server during renewal -- `[Auth] Silent renew failed` in console, LoginPage renders if token expired |
| 401 interceptor (Layer 2) | Manually expire token in sessionStorage, make API call -- `onUnauthorized` triggers logout |
| 401 race guard | Trigger 401 while `user.expired` is false (renew in progress) -- no logout, user stays logged in |
| WS 4001 (Layer 3) | Force server close with 4001 -- single logout, NO reconnect loop in console |
| WS normal close | Kill backend -- normal reconnect backoff (1s, 2s, 4s...) continues working |

---

## 5. Verdict

**Approved.** Risk level **Low**. All prior blockers resolved. No new findings. Zero deferred debt -- all design decisions documented in-code with rationale.

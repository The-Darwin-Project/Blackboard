# Darwin Brain API Contract for Release Console BFF

**Status:** Implemented in commit `7ca8efe` on `main`
**Date:** 2026-04-30
**Spec:** [Darwin-Spec-Change-Release-Console-Integration.md](Darwin-Spec-Change-Release-Console-Integration.md)

---

## 1. Connection

**Darwin Brain endpoint (in-cluster):**

```
ws://darwin-blackboard-brain.darwin.svc.cluster.local:8000/ws
http://darwin-blackboard-brain.darwin.svc.cluster.local:8000
```

---

## 2. WebSocket Authentication

The BFF authenticates via trusted-proxy headers on the WebSocket upgrade request.

**Required headers:**

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Forwarded-Email` | User's email (e.g., `thason@redhat.com`) | Stable user identity |
| `X-BFF-Token` | Shared secret matching `TRUSTED_PROXY_SECRET` env var | BFF identity verification |

**Behavior:**

- Valid headers: connection accepted, `UserContext(source="release-console", email=forwarded_email)`
- Invalid/missing token: connection closed with code `4001`
- Missing email: connection closed with code `4001`

**Env vars on Darwin side:**

| Var | Default | Purpose |
|-----|---------|---------|
| `TRUSTED_PROXY_ENABLED` | `"false"` | Must be `"true"` to enable |
| `TRUSTED_PROXY_SECRET` | `""` | Shared secret (inject via K8s Secret) |

**Env vars on Console-Server BFF side:**

| Var | Purpose |
|-----|---------|
| `DARWIN_BRAIN_WS_URL` | `ws://darwin-blackboard-brain.darwin.svc.cluster.local:8000` |
| `DARWIN_BRAIN_REST_URL` | `http://darwin-blackboard-brain.darwin.svc.cluster.local:8000` |
| `TRUSTED_PROXY_SECRET` | Same value as Darwin side |

---

## 3. WebSocket Messages: Client -> Darwin

### `chat` -- Create new event

```json
{
  "type": "chat",
  "message": "Scale inventory-api to 3 replicas",
  "service": "general"
}
```

- `service` is optional, defaults to `"general"`
- `image` field (base64 data URI, max 1MB) is optional
- Creates an event with `created_by_email` set to the authenticated user's email

### `user_message` -- Add message to existing event

```json
{
  "type": "user_message",
  "event_id": "evt-abc12345",
  "message": "Actually, scale to 5 instead"
}
```

- `image` field (base64 data URI, max 1MB) is optional

### `approve` -- Approve a pending plan

```json
{
  "type": "approve",
  "event_id": "evt-abc12345"
}
```

Note: does NOT call `transition_event_status`. Brain picks up the approval via conversation polling.

### `emergency_stop` -- Kill all active agents

```json
{
  "type": "emergency_stop"
}
```

---

## 4. WebSocket Messages: Darwin -> Client (Broadcast)

Darwin broadcasts to ALL connected WebSocket clients. The BFF must filter by `event_id` to show only the current user's events.

| Type | Key Fields | Notes |
|------|-----------|-------|
| `event_created` | `event_id, service, reason` | Sent only to the creating socket (response to `chat`) |
| `brain_thinking` | `event_id, accumulated, is_thought` | Live streaming. `is_thought=true` = internal reasoning |
| `brain_thinking_done` | `event_id` | Finalize streaming block |
| `turn` | `event_id, turn: ConversationTurn` | Persisted conversation turn (any actor) |
| `event_status_changed` | `event_id, status` | Status transition (e.g., `active` -> `waiting_approval`) |
| `event_closed` | `event_id, ...` | Terminal state reached |
| `progress` | `agent_id, event_id, message` | Live agent CLI output lines |
| `message_status` | `event_id, turn, status` | Delivery receipt (`sent` -> `delivered` -> `evaluated`) |

### BFF Filtering Strategy

The BFF maintains a local set of `event_id`s belonging to the current user:
1. On `event_created` response: add `event_id` to set
2. On reconnect: call `GET /queue/active`, filter by `created_by_email == user.email`
3. For all broadcast messages: relay to browser only if `event_id` is in the user's set
4. Drop all broadcasts for unknown `event_id`s (aligner, headhunter, other users)

---

## 5. REST Endpoints

All REST endpoints are unauthenticated (internal cluster access).

### `GET /queue/active` -- List active events

**Response:** Array of event metadata objects

```json
[
  {
    "id": "evt-abc12345",
    "source": "chat",
    "service": "general",
    "subject_type": "service",
    "status": "active",
    "reason": "Scale inventory-api to 3 replicas",
    "evidence": { "display_text": "...", "source_type": "chat", ... },
    "turns": 5,
    "created": "2026-04-30T12:00:00+00:00",
    "created_by_email": "thason@redhat.com"
  }
]
```

**BFF filters:** `source === "chat" && created_by_email === user.email`

Notes:
- `created_by_email` is `null` for automated events (aligner, headhunter, timekeeper)
- `created_by_email` is `null` for legacy events created before this feature

### `GET /queue/{event_id}` -- Full event document

**Response:** Full `EventDocument` (Pydantic model, includes `conversation` array and all metadata including `created_by_email`)

### `POST /queue/{event_id}/approve` -- Approve plan

**Response:** `{ "status": "approved", "event_id": "..." }`

Transitions event from `waiting_approval` to `active`. Clears Brain wait state.

Note: the WS `approve` message does the same thing but does NOT call `transition_event_status`. The REST endpoint does. For Release Console, prefer the REST endpoint for approve/reject since it provides atomic status transition.

### `POST /queue/{event_id}/reject` -- Reject plan

**Request body:**

```json
{
  "reason": "The plan scales too aggressively",
  "image": null
}
```

`image` is optional base64 data URI (max 1MB).

**Response:** `{ "status": "rejected", "event_id": "..." }`

### `GET /queue/closed/list` -- List closed events

**Response:** Same shape as `/queue/active` but for recently closed events (last 24h). Includes `created_by_email`.

---

## 6. Event Lifecycle States

```
new -> active -> waiting_approval -> active -> resolved -> closed
                      |                          |
                      +--- (reject) --> active ---+
```

| Status | Meaning |
|--------|---------|
| `new` | Queued, awaiting Brain triage |
| `active` | Brain is processing (agents may be dispatched) |
| `waiting_approval` | Plan generated, awaiting user approve/reject |
| `deferred` | Brain deferred processing (will retry) |
| `resolved` | Work complete, Brain closing |
| `closed` | Terminal state |

---

## 7. ConversationTurn Schema

Each turn in `event.conversation` has this shape:

```json
{
  "turn": 1,
  "actor": "brain",
  "action": "triage",
  "thoughts": "Analyzing the request...",
  "result": null,
  "plan": null,
  "selectedAgents": ["architect"],
  "image": null,
  "status": "evaluated",
  "source": "dashboard",
  "user_name": "Tal H.",
  "timestamp": 1714470000.0
}
```

Key `actor` values: `brain`, `architect`, `sysadmin`, `developer`, `qe`, `aligner`, `headhunter`, `user`

Key `action` values: `triage`, `investigate`, `plan`, `execute`, `approve`, `reject`, `close`, `route`, `message`, `error`

---

## 8. Rollout Notes

1. `TRUSTED_PROXY_ENABLED` and `TRUSTED_PROXY_SECRET` must be set in Darwin's Helm values before the BFF can connect. The secret MUST be injected via K8s Secret (`secretKeyRef`), not ConfigMap.

2. Pre-existing active `source="chat"` events will have `created_by_email=null`. The BFF filter will hide these. In practice, chat events are short-lived and the active queue will cycle before the BFF goes live.

3. The Darwin Dashboard (ops UI) is unaffected. It shows all events from all sources and does not use `created_by_email` filtering.

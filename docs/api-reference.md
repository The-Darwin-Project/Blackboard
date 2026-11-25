<!-- @ai-rules:
1. [Constraint]: Every route in src/routes/*.py must be listed here. Check routes/__init__.py for the full set.
2. [Pattern]: Group endpoints by router file. Include request/response examples for POST endpoints.
3. [Gotcha]: /reports/ serves the SPA (not JSON). /reports/list and /reports/search return JSON.
4. [Constraint]: No internal hostnames or credentials. Open-source hygiene.
-->
# API Reference

All endpoints are served by the FastAPI Brain server on port 8000.

## Health and Info

```text
GET /health              # {"status": "brain_online"}
GET /info                # API information and available endpoints
GET /api/agents          # Connected agents (AgentRegistry visibility)
```

## WebSocket

```text
WS /ws                   # Dashboard/BFF bidirectional WebSocket
                         # Receives: turn, progress, event_created, event_closed,
                         #           attachment, phase_updated
                         # Sends: chat, approve, reject, user_message

WS /agent/ws             # Agent WebSocket (reverse mode): sidecars connect here
                         # See architecture.md for the full message protocol
```

## Chat

```json
POST /chat/
{"message": "Scale darwin-store to 3 replicas", "service": "darwin-store"}

// Response:
{"event_id": "evt-abc123", "status": "created"}
// Brain processes asynchronously -- track via WebSocket or GET /queue/{event_id}
```

## Conversation Queue

```text
GET  /queue/active                    # List active events with metadata
GET  /queue/waiting_approval           # Events parked for human approval (all sources)
GET  /queue/{event_id}                # Full event document with conversation
GET  /queue/{event_id}/turns          # Paginated conversation turns (optional ?role=, ?since=)
GET  /queue/{event_id}/report         # Generated markdown report for an event
POST /queue/{event_id}/approve        # Approve a pending plan (optional {"expected_sha": "..."}; 409 on SHA drift)
POST /queue/{event_id}/reject         # Reject a pending plan with reason
POST /queue/{event_id}/close          # User-initiated force close
POST /queue/{event_id}/plan-step      # Agent plan step status update
GET  /queue/closed/list               # Recently closed events
GET  /queue/headhunter/pending        # Pure-Redis pending/active/waiting_approval Headhunter items (list[dict])
GET  /queue/headhunter/status         # Per-platform enabled, counts, last_poll_at, redacted errors, circuit breakers
POST /queue/headhunter/poll           # Operator-gated global 10s-debounced poll wake-up (5s lock -> 409 if busy)
POST /queue/headhunter/breaker/{platform}/reset  # Operator-gated per-platform breaker reset (gitlab|github; 5s lock -> 409)
POST /queue/headhunter/items/{action} # Operator-gated item action (promote -> 202, dismiss/requeue -> 200; 5s lock -> 409)
```

### Headhunter Queue & Operator Controls

* `GET /queue/headhunter/pending` reads exclusively from Redis (`darwin:headhunter:snapshot:{platform}` plus active/`waiting_approval` Blackboard Headhunter events) with zero live VCS HTTP calls per UI poll, preserving `list[dict]` rows with additive `check_status`, `pipeline_status`, `queue_position`, and `status` fields.
* `GET /queue/headhunter/status` returns `{platforms: {gitlab: {...}, github: {...}}}` with per-platform `enabled`, `pending_count`, `queued_count`, `last_poll_at`, PII-redacted `partial_error` (`<= 200` chars), and `breaker: {state, consecutive_failures, next_retry_at, last_error}`.
* Operator endpoints (`POST /queue/headhunter/poll`, `POST /queue/headhunter/breaker/{platform}/reset`, `POST /queue/headhunter/items/{promote,dismiss,requeue}`) require RBAC authorization (`OBS_ADMIN_GROUPS` ∪ `APPROVER_GROUPS`, fail-closed `401`/`403`) and acquire `hh._poll_lock` with a 5s timeout (all three return `409 Conflict` with `Retry-After: 5` if busy; `/items/{action}` also returns `409` on concurrent Redis `WatchError`).
* **Debounce & Error Semantics:** `/poll` uses a **global** 10s debounce; `/breaker/{platform}/reset` uses a **per-platform** 10s cooldown; `/items/{action}` uses a **per-`(action, platform, item_number)`** 10s cooldown. Common errors: `404` (item missing from active snapshot on `/items/{action}`), `409` (`_poll_lock` busy with `Retry-After: 5` on `/poll`, `/breaker/{platform}/reset`, and `/items/{action}`, or concurrent queue mutation on `/items/{action}`), `422` (invalid `platform`/`action` or request payload), `502` (upstream VCS/gateway error), `503` (Brain/Headhunter/Blackboard unavailable).

```json
POST /queue/headhunter/poll
// Response (202 Accepted; 409 Conflict Retry-After: 5 if poll lock busy):
{"triggered": true, "debounced": false}
// Debounced within 10s global window (202 Accepted):
{"triggered": false, "debounced": true}

POST /queue/headhunter/breaker/gitlab/reset
// Response (200 OK; 409 Conflict Retry-After: 5 if poll lock busy):
{"reset": true, "debounced": false, "platform": "gitlab", "state": "closed"}
// Debounced within 10s per-platform cooldown (202 Accepted):
{"reset": false, "debounced": true, "platform": "gitlab"}
```

* `POST /queue/headhunter/items/{action}` validates the target item against the active Headhunter queue/pending snapshot before acting (`extra="forbid"`):

```json
// GitLab payload:
POST /queue/headhunter/items/promote
{"platform": "gitlab", "project_id": 42, "item_number": 17, "is_issue": false}

// GitHub payload:
POST /queue/headhunter/items/requeue
{"platform": "github", "owner": "org", "repo": "repo", "item_number": 77, "is_issue": false}

// Response (202 Accepted for promote; 200 OK for dismiss -> "dismissed" / requeue -> "requeued"; 409 Conflict Retry-After: 5 if poll lock busy):
{"status": "accepted", "action": "promote", "platform": "gitlab", "item_number": 17}

// Debounced within 10s per-(action, platform, item_number) cooldown (202 for promote; 200 for dismiss/requeue):
{"ok": false, "debounced": true, "action": "promote", "platform": "gitlab"}
```

### Admin Endpoints

Memory/lesson/knowledge list endpoints use cursor-based scroll pagination (see [Knowledge Admin](#knowledge-admin) for the shared envelope shape).

```text
POST /queue/admin/rebuild-deep-memory # Re-index deep memory from closed events
GET  /queue/admin/memories            # Scroll archived event memories
     ?limit=50&cursor=&service=&q=    # cursor from prior page's next_cursor; q is post-fetch substring match on symptom/service (current page only)
POST /queue/admin/correct-memory      # Correct a memory entry
GET  /queue/admin/lessons             # Scroll lessons learned
     ?limit=50&cursor=&channel=&q=    # channel/q are post-fetch filters (current page only, no Qdrant index)
POST /queue/admin/lessons             # Create a lesson
GET  /queue/admin/lessons/{id}        # Get a single lesson by ID
PATCH /queue/admin/lessons/{id}/demote  # Demote a lesson (reduce priority)
PATCH /queue/admin/lessons/{id}/verify  # Mark a lesson as verified
DELETE /queue/admin/lessons/{id}      # Delete a lesson
POST /queue/admin/lessons/extract     # LLM-powered lesson extraction
POST /queue/admin/lessons/apply       # Apply a lesson to an event
GET  /queue/admin/memories/{event_id} # Single memory entry by event ID
```

## Event History (Reports)

Persisted event reports with 90-day TTL. The Reports UI is a React SPA served at `/reports`.

```text
GET  /reports/list                    # All persisted report metadata (paginated)
     ?limit=50&offset=0
     ?service=darwin-store

GET  /reports/search                  # Compound cursor pagination with facet filters
     ?cursor={score}:{event_id}       # Keyset pagination cursor
     ?limit=50
     ?start_time=1714000000           # Unix epoch (ZSET indexed_at)
     ?end_time=1714100000
     ?service=darwin-store
     ?source=aligner
     ?domain=complicated
     ?severity=warning
     ?q=OOMKilled                     # Substring search on event_id, service, reason

GET  /reports/{event_id}              # Full markdown report content
```

## TimeKeeper (Scheduled Tasks)

All mutating endpoints require Dex authentication.

```text
POST   /api/timekeeper                # Create schedule (auth required)
GET    /api/timekeeper                # List all schedules
GET    /api/timekeeper/{id}           # Get one schedule
PUT    /api/timekeeper/{id}           # Update schedule (owner only)
DELETE /api/timekeeper/{id}           # Delete schedule (owner only)
PATCH  /api/timekeeper/{id}/toggle    # Enable/disable (owner only)
POST   /api/timekeeper/refine         # LLM instruction refinement (auth required)
```

## Shifts (Nightwatcher)

```text
GET /shifts/list                      # All shift reports (paginated)
GET /shifts/{date}/{window}           # Single shift report (date=YYYY-MM-DD, window=morning|evening)
GET /shifts/current                   # Current or most recent shift report
```

## Feedback

```json
POST /feedback
{"event_id": "evt-abc123", "turn_number": 5, "rating": "positive", "comment": "Accurate fix"}
```

Ratings stored in Qdrant for quality tracking.

## Incidents

```text
GET /incidents/list                   # Jira incidents (via JiraIncidentAdapter)
```

## Topology and Metrics

```text
GET /topology/                        # JSON topology
GET /topology/services                # Service list with metadata
GET /topology/service/{service_name}  # Single service detail
GET /topology/graph                   # Cytoscape.js graph data
GET /topology/mermaid                 # Mermaid diagram
GET /metrics/{service}                # Current metrics
GET /metrics/{service}/history        # Historical metrics for a service
GET /metrics/chart                    # Time-series chart data
```

## Jira Missions (Headhunter Jira)

Exposes Jira issues tracked by the Headhunter Jira daemon for the Operations Center UI. Returns `[]` when Jira is not configured.

```text
GET  /jira/missions                   # List tracked issues (Planning/To Do/In Progress, darwin label)
POST /jira/missions/{key}/approve     # Approve a mission (transition Planning → To Do)
POST /jira/missions/{key}/reanalyze   # Clear Redis state and trigger re-analysis
POST /jira/missions/{key}/dismiss     # Dismiss a mission from tracking
POST /jira/missions/{key}/retry       # Retry event creation for an approved mission
```

## Cortex / Cognitive Graph

Read-only endpoints for the Cortex UI and JARVIS memory views. Return HTTP 503 when PulseTracker or Archivist is unavailable.

```text
GET /api/cognitive-graph              # Qdrant neurons (lessons + memories) with Redis heat counters
GET /api/pulses                       # Pulse log history (?event_id=, ?since=, ?limit=)
GET /api/cortex/status                # Live adapter status (UI hydration on mount)
GET /api/cortex/activity              # Recent Cortex activity stream
GET /api/cortex/shadow                # Shadow-mode intervention log (when SYSTEM2_SHADOW=true)
GET /api/cortex/shadow/{event_id}     # Shadow interventions for a single event
GET /api/cortex/handoff-reports       # Session handoff reports from Redis
GET /api/cortex/proposals             # Cortex proposals awaiting Brain action
POST /api/cortex/proposals/dismiss    # Dismiss proposals by timestamps {timestamps: [...]}
```

## Flow Observability

```text
GET /flow                             # Queue depth, active events, automated WIP (excludes chat, slack, jarvis), agent utilization, token totals, per-pool TPM metrics (vertex_gemini, vertex_claude, enmaas, peak_pool_utilization_pct)
GET /flow/history                     # FlowSnapshot time-series (60s intervals, Redis sorted set; includes automated WIP and per-pool TPM metrics)
GET /flow/{event_id}                  # Value stream breakdown (queue_wait, routing, execution, total_lead_time)
```

## Configuration

```text
GET /config                           # Public UI config (auth settings, nightwatcher status, contact info)
```

## Events

```text
GET /events/                          # Architecture event timeline
GET /events/{id}/document             # Full event document (used by ephemeral agents)
```

## Journal

```text
GET /api/journal                      # Read-only ops journal (all services)
GET /api/journal/{service_name}       # Ops journal filtered by service
```

## Kargo

```text
GET /api/kargo/stages                 # Kargo stage status (from KargoObserver)
```

## Field Notes Notebook

CRUD for FRIDAY's qualitative knowledge capture. Mutations require Dex auth.

```text
GET    /api/notebook                  # All field notes sorted by timestamp
PATCH  /api/notebook/{note_id}        # Update note content/category (auth required)
DELETE /api/notebook/{note_id}        # Delete a field note (auth required)
```

## Observations

FRIDAY's numeric observation series (trajectory data for deferral decisions).

```text
GET /api/observations                 # Global observation series (?name=, ?service=)
GET /api/queue/{event_id}/observations  # Observation series for a specific event
```

## Knowledge Admin

Static infrastructure facts (conventions, ownership, relationships). Admin CRUD only -- no auto-extract.

```text
POST   /queue/admin/knowledge         # Create a knowledge fact
GET    /queue/admin/knowledge         # Scroll knowledge facts
       ?limit=50&cursor=&scope=&service=&q=  # scope/service are indexed Qdrant filters; q is a post-fetch substring match (current page only)
GET    /queue/admin/knowledge/{id}    # Get a single knowledge fact
PATCH  /queue/admin/knowledge/{id}    # Update a knowledge fact (topic/scope immutable)
DELETE /queue/admin/knowledge/{id}    # Delete a knowledge fact
```

**Scroll envelope** (shared shape for `/admin/{memories,lessons,knowledge}`):

```json
{"items": [...], "next_cursor": "opaque-string-or-null", "has_more": true}
```

`limit` defaults to 50, `le=200`. `cursor` is opaque -- pass the prior page's `next_cursor` verbatim; omit for the first page. `has_more: false` means the underlying Qdrant scroll is exhausted; post-fetch filters (`q`, `channel`) can return a sparse or empty page while `has_more` is still `true` if matches exist on a later page -- there is no `total` count.

## Knowledge Graph

Read-only endpoints backing the Memory page's Graph tab. Dex-gated; return empty results (`[]` / `null`) when the graph store or Dex is unavailable, rather than erroring.

```text
GET /api/knowledge-graph/services         # All entities with relationship counts
GET /api/knowledge-graph/services/{id}    # Single entity + its relationships
GET /api/knowledge-graph/stats            # Entity/relationship counts by type, last_updated
```

## Diagnostics

```text
GET /skills/version                   # Skill reconciler sync metadata (version SHA, file count, last sync)
```

## Telemetry

```text
GET /telemetry/llm                    # Multi-pool LLM quota stats (vertex_gemini, vertex_claude, enmaas, enmaas_active, peak_pool_utilization_pct) + bounded callers/teams attribution (256-entry LRU with "_other" overflow)
```

The legacy `POST /telemetry/` push endpoint returns HTTP 410 (deprecated). Use `darwin.io` annotations for passive discovery instead.

## Dex Proxy

```text
GET /dex/*                            # Proxies to internal Dex OIDC provider
```

Only active when `DEX_ENABLED=true`.

## Multi-Option Approvals (VMER-2501)
- `POST /queue/{event_id}/decision`: Submit a decision (`DecisionRequest`: `approval_id`, `option_id`, `message`, `write_in_text`, `image`, `reject_reason`, `expected_sha`).
- WebSocket `approval_decision` accepts the same `DecisionRequest` fields (`event_id`, `approval_id`, `option_id`, `message`, `write_in_text`, `image`, `reject_reason`, `expected_sha`) and broadcasts `turn_updated` for swept `pendingApproval` turns.
- Legacy `/approve` and `/reject` shims (HTTP and WebSocket) route through `execute_approval_decision` when `pending_approval` is present.
- Event status transitions and approvals are atomic via Redis WATCH/MULTI/EXEC.

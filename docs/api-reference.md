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
POST /queue/{event_id}/approve        # Approve a pending plan
POST /queue/{event_id}/reject         # Reject a pending plan with reason
POST /queue/{event_id}/close          # User-initiated force close
POST /queue/{event_id}/plan-step      # Agent plan step status update
GET  /queue/closed/list               # Recently closed events
GET  /queue/headhunter/pending        # Pending Headhunter events
```

### Admin Endpoints

```text
POST /queue/admin/rebuild-deep-memory # Re-index deep memory from closed events
GET  /queue/admin/memories            # Browse vector store entries
POST /queue/admin/correct-memory      # Correct a memory entry
GET  /queue/admin/lessons             # List extracted lessons
POST /queue/admin/lessons             # Create a lesson
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
GET /incidents/list                   # Smartsheet incidents (via adapter)
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
```

## Flow Observability

```text
GET /flow                             # Queue depth, active events, agent utilization by role
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

## Telemetry

```text
GET /telemetry/llm                    # LLM quota stats (TPM usage)
```

The legacy `POST /telemetry/` push endpoint returns HTTP 410 (deprecated). Use `darwin.io` annotations for passive discovery instead.

## Dex Proxy

```text
GET /dex/*                            # Proxies to internal Dex OIDC provider
```

Only active when `DEX_ENABLED=true`.

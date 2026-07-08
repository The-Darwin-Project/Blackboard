<!-- @ai-rules:
  1. [Scope]: This README documents the Darwin Dashboard UI only.
  2. [Constraint]: Keep under 100 lines. No emojis. Professional tone.
  3. [Pattern]: Update this file when pages or key components are added/removed.
-->

# Darwin Dashboard

React + TypeScript + Vite application serving as the primary web UI for the Darwin Brain. Provides real-time monitoring, event management, and agent interaction via WebSocket.

## Pages

| Page | Description |
|------|-------------|
| **Dashboard (Ops Center)** | CCTV-style adaptive grid with agent streaming cards, conversation feed, event chat panel. `cols = ceil(sqrt(N))` layout. |
| **Event History** | TanStack Table with card grid toggle, server pagination, compound cursor pagination. Facet filters: service, source, domain, severity, time range, text search. |
| **Memory** | Five sub-tabs: Memories, Lessons, Facts (knowledge admin), Field Notes (notebook), Extract wizard. |
| **Cortex** | Cognitive graph visualization (Sigma.js v3 + ForceAtlas2) — four rings (executive, skills, knowledge, events) with live pulse feed. |
| **JARVIS Memory** | Session handoff reports, shadow-mode interventions, and Cortex proposals with dismiss. |
| **Shifts** | Nightwatcher shift reports (morning/evening). Conditional nav tab, visible only when Nightwatcher is enabled. |
| **TimeKeeper** | Schedule management UI (create, edit, toggle, delete). Requires Dex auth. |
| **Topology** | Service dependency graph rendered with Cytoscape.js. |
| **Flow History** | Flow metrics time-series (WIP, queue depth, agent utilization) with SparkCard charts. |
| **Token Utilization** | LLM token tracking: per-model and per-caller breakdowns from FlowSnapshot data. |
| **User Guide** | AI transparency page. |
| **Incidents** | Jira incident tracker view (via JiraIncidentAdapter). |

## Key Components

- **ConversationFeed** — Append-only event conversation renderer.
- **EventChatPanel** — Layout-level event chat panel (extracted from EventSidebar).
- **AgentStreamCard** — Real-time CLI stdout in dedicated cards with floating windows.
- **GridTile** — Per-agent streaming tile in the CCTV adaptive grid.
- **ServiceTile** — Per-service health and metrics tile.
- **PlanViewer** — Floating viewer for plan and approval turns.
- **PhaseIndicator** — Brain phase badge with transition markers.
- **TokenUtilizationPage** — Per-model, per-caller LLM token breakdown.
- **NotebookPanel** — Field notes inline edit/dismiss UI.

## Tech Stack

- React 19, TypeScript (strict mode)
- Vite (dev server port 5174, production build served by FastAPI)
- TanStack Query for server state management
- WebSocket context provider for real-time updates
- Cytoscape.js for topology visualization

## Directory Structure

```
ui/
  src/
    components/     # 35+ React components (ops/, cortex/, memory/, notebook/, timekeeper/)
    contexts/       # ActiveStreamsContext (40Hz WS), OpsStateContext (user-freq), WebSocketContext, AuthContext
    hooks/          # TanStack Query hooks + useResizablePanel
    api/            # API client + TypeScript types
    utils/          # Stream reducers, token formatters, safeOpen
    __tests__/      # Unit tests (activeStreams, streamReducers)
  public/           # Static assets including lessons-learned template
```

## Development

```bash
cd ui
npm ci
npm run dev    # Vite dev server on port 5174
npm run build  # Production build to ui/dist/
npm run lint   # ESLint
```

Production build is served by the FastAPI Brain server (static mount at `/`). In development, run the Vite dev server with the Brain on port 8000.

## WebSocket Protocol

Connects to `WS /ws` on the Brain.

**Inbound (server to client):**

| Message | Purpose |
|---------|---------|
| `turn` | New conversation turn |
| `progress` | Agent execution progress |
| `event_created` / `event_closed` | Event lifecycle transitions |
| `attachment` | File or image attachments |
| `phase_updated` | Brain phase transitions |

**Outbound (client to server):**

| Message | Purpose |
|---------|---------|
| `chat` | User messages |
| `approve` / `reject` | Plan approval or rejection |
| `user_message` | Follow-up messages in active events |

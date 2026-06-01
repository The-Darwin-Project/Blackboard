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
| **Dashboard (Ops Center)** | XProtect-inspired adaptive layout with service tiles, conversation feed, agent streaming cards. Side-by-side layout activates with 4+ tiles. |
| **Event History** | TanStack Table with card grid toggle, server pagination, compound cursor pagination. Facet filters: service, source, domain, severity, time range, text search. |
| **Memory** | Two views: Memories (vector store entries) and Lessons (extracted lessons learned). Includes LLM-powered Extract wizard with multi-select event picker. |
| **Cortex** | Cognitive graph visualization — Qdrant neurons with heat counters, live pulse feed, Cortex status. |
| **JARVIS Memory** | Session handoff reports, shadow-mode interventions, and Cortex proposals. |
| **Shifts** | Nightwatcher shift reports (morning/evening). Conditional nav tab, visible only when Nightwatcher is enabled. |
| **TimeKeeper** | Schedule management UI (create, edit, toggle, delete). Requires Dex auth. |
| **Topology** | Service dependency graph rendered with Cytoscape.js. |
| **User Guide** | AI transparency page. |
| **Incidents** | Smartsheet incident tracker view. |

## Key Components

- **ConversationFeed** — Append-only event conversation renderer.
- **AgentStreamCard** — Real-time Gemini CLI stdout in dedicated cards with floating windows.
- **ServiceTile** — Per-service health and metrics tile.
- **PlanViewer** — Floating viewer for plan and approval turns.
- **PhaseIndicator** — Brain phase badge with transition markers.

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
    components/     # 25+ React components
    contexts/       # WebSocketContext provider
    hooks/          # TanStack Query hooks (useQueue, useChat, useWebSocket, etc.)
    api/            # API client + TypeScript types
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

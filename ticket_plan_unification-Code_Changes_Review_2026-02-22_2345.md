# Ticket-Plan Unification -- Code Changes Review

**Date:** 2026-02-22 23:45
**Reviewer:** Systems Architect (AI)
**Plan:** `ticket_plan_unification_b925a03e.plan.md`
**Scope:** 7 files, 475 deletions, 56 insertions (subtractive refactor)

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** LOW -- This is a clean subtractive refactor. All removals are mechanically sound and verified by import checks + grep sweep.
* **Breaking Changes:**
  - `GraphResponse.plans` field removed from the `/topology/graph` API response. Frontend and backend **must deploy together** (single image push). Any external consumer polling this field will get `undefined` instead of a list.
  - `EventType` enum no longer includes `plan_created`, `plan_approved`, `plan_rejected`, `plan_executed`, `plan_failed`. Any Redis event documents with these types will be ignored by `getAgentFromEventType()` (falls to `default: 'architect'` -- safe degradation).
  - `Snapshot.pending_plans` removed. The Architect sidecar context no longer includes pending plans. Since plans are now Markdown conversation turns (not model objects), this is intentional.

---

## 2. Downstream Impact Analysis

### Affected Consumers

| Consumer | Import/Dependency | Impact | Risk |
|---|---|---|---|
| `routes/topology.py` | Calls `blackboard.get_graph_data()`, uses `GraphResponse` as response model | **Safe** -- `GraphResponse` still valid, `plans` field simply absent from response | LOW |
| `routes/topology.py` L73 | Docstring references "ghost nodes" | **Stale docstring** -- not staged, not a runtime issue | LOW |
| `brain.py` | Imported `PlanAction`, `PlanCreate`, `PlanStatus` -- all removed | **Safe** -- imports cleaned, method definitions deleted, all call sites removed | NONE |
| `blackboard.py` | Imported `GhostNode`, `Plan`, `PlanCreate`, `PlanStatus` -- all removed | **Safe** -- imports cleaned, 7 plan methods deleted, ghost node assembly deleted | NONE |
| `kubernetes.py` L341, L375 | Uses "ghost" terminology for stale K8s services | **Not related** -- different "ghost" concept (services vanishing from cluster, not Plan ghost nodes) | NONE |
| `formatter.py` L69-70 | References `turn.plan` (Markdown plan text) | **Intentionally kept** -- this is the Architect's Markdown plan, not the Plan model | NONE |
| `dispatch.py` L38-40 | References `plans/plan-` file paths | **Intentionally kept** -- filesystem plan volumes for agent sidecars, not the Plan model | NONE |
| `llm/types.py` L130-135 | `plan_summary` in function schema | **Intentionally kept** -- LLM function parameter for Architect approval flow | NONE |
| `security.py` L44-51 | `plan_context` parameter | **Intentionally kept** -- security validation of plan text, not the Plan model | NONE |
| `models.py` L351 | `ConversationTurn.plan_id` field | **Intentionally kept** -- event conversation protocol field | NONE |

### Existing Tests

No unit tests for Plan model or ghost node rendering exist in the codebase. Build verification (`python import` + `npm run build`) was the primary gate, supplemented by grep sweep.

---

## 3. Findings & Fixes

| # | File | Severity | Issue Type | Description & Fix |
|---|------|----------|------------|-------------------|
| 1 | `src/state/blackboard.py` L419, L422 | **MEDIUM** | Stale Docstring | `get_graph_data()` docstring still says "Pending plans as ghost nodes" (L419) and "GraphResponse with nodes, edges, and ghost nodes" (L422). These lines are inside the staged diff but were not updated. **Fix:** Update docstring to remove ghost node references. |
| 2 | `ui/src/components/CytoscapeGraph.tsx` L172-177, L211 | **MEDIUM** | React Performance | `TICKET_COLORS` is declared **inside** the component body (not as a module-level constant). It creates a new object reference on every render, which causes `buildTicketLabel` (via `useCallback` dep array at L211) to be recreated every render, which in turn triggers the graph update `useEffect` (L686) unnecessarily. **Fix:** Move `TICKET_COLORS` outside the component to module scope. |
| 3 | `ui/src/components/CytoscapeGraph.tsx` L360-368 | **LOW** | Design Gap | `edge.ticket-edge` CSS style uses hardcoded amber `#f59e0b`. The plan spec says "dashed line, matching ticket source color" but the Cytoscape style system can't vary by data attribute without explicit `data()` mappers. Currently non-blocking since `resolved_service` is always `None` (probe step). **Fix (deferred):** When Step 7c implements `resolved_service`, add `data.color` to edge elements and use Cytoscape's `data()` style function, or use per-source edge classes. |
| 4 | `ui/src/components/NodeInspector.tsx` L3-4 | **LOW** | Stale JSDoc | File-level JSDoc still says "Slide-over drawer for service details and **plan actions**" and "**plan approval buttons**". No plan actions remain in this component post-refactor. **Fix:** Update JSDoc to match current functionality. |
| 5 | `src/routes/topology.py` L73 | **LOW** | Stale Docstring (not staged) | Route docstring says "and pending plans as ghost nodes per GRAPH_SPEC.md". This file is NOT in the staged changeset but contains a stale reference. **Fix:** Add `topology.py` to the commit and update the docstring. |
| 6 | `ui/src/components/CytoscapeGraph.tsx` | **LOW** | Missing AI Shebang | No `@ai-rules` shebang. This is a 769-line file with complex Cytoscape lifecycle management, extension registration, and HTML label overlay patterns. Should have a shebang per project rules. |
| 7 | `ui/src/api/types.ts` | **LOW** | Missing AI Shebang | No `@ai-rules` shebang. This is the contract file between Python and TypeScript -- critical for type alignment. |

---

## 4. Verification Plan

### Automated Checks (already passed per transcript)

- [x] `python -c "from src.agents.brain import Brain"` -- import compiles clean
- [x] `cd ui && npm run build` -- zero errors, 8.23s
- [x] `rg '_event_plans|_create_plan_for_event|PlanAction|PlanCreate|PlanStatus|GhostNode|ghost_nodes|ghost-edge|buildGhostLabel|onPlanClick|handlePlanClick' BlackBoard/src/ BlackBoard/ui/src/` -- zero hits

### Manual Integration Tests (recommended before merge)

1. **Graph API contract**: `GET /topology/graph` -- verify response has `nodes`, `edges`, `tickets` keys but NO `plans` key.
2. **Ticket color differentiation**: Create events from `chat` and `slack` sources. Verify ticket nodes render with amber vs violet borders respectively.
3. **Event lifecycle**: Create an event, route through Brain, close it. Verify no "plan" creation or "ghost node" warnings in logs.
4. **Snapshot sanity**: Trigger an Architect analysis. Verify `Snapshot` context excludes `pending_plans` and the Architect still receives topology + services.

### Residual Grep (extended pattern recommended)

```bash
rg 'ghost_nodes|ghost-edge|buildGhostLabel|onPlanClick|handlePlanClick|plans.*ghost|ghost.*plan' BlackBoard/src/ BlackBoard/ui/src/
```

---

## 5. Refactored Code Snippets (for MEDIUM issues)

### Fix #1: Stale `get_graph_data()` docstring

```python
# blackboard.py -- get_graph_data() docstring
async def get_graph_data(self) -> GraphResponse:
    """
    Get topology as rich graph data for Cytoscape.js visualization.
    
    Combines:
    - Services with health status and metadata
    - Edges with protocol information
    - Ticket nodes from active events
    
    Returns:
        GraphResponse with nodes, edges, and ticket nodes
    """
```

### Fix #2: Move `TICKET_COLORS` to module scope

```tsx
// CytoscapeGraph.tsx -- move OUTSIDE the component, after imports
const TICKET_COLORS: Record<string, string> = {
  aligner: '#ef4444',
  chat: '#f59e0b',
  slack: '#8b5cf6',
  headhunter: '#06b6d4',
};

// Then inside the component, buildTicketLabel's dep array becomes:
// }, []);  -- TICKET_COLORS is now a stable module-level reference
```

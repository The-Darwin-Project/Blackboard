# Cortex Graph Redesign -- Pre-Flight Review

## 1. Developer And Technical Summary

* **Overall Confidence Score:** 78%
* **Status:** Caution
* **Critical Blockers:**
  1. Sigma.js v3 does NOT support dotted/dashed edges (v4 feature). Structural edges need visual differentiation via color/opacity/size instead, or upgrade sigma to v4.
  2. Group drag (BFS on structural edges) requires custom `dragNode` + batch `setNodeAttribute` which may cause layout jank at 200+ nodes -- needs validation.

## 2. Task-by-Task Analysis

| Step # | Task Summary | Cynefin Domain | Confidence | Risk / Missing Context |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Structural edges: phase chain, phase->tools, agent->tools, tool groups | Complicated | 75% | Sigma v3 lacks dotted edge type. Need alternative visual (thin, low-opacity white vs event-colored solid). `_phase_tool_priority` mapping needs extraction from brain.py (~line 963). |
| 2 | Executive sizing: tools=8, phases=10, agents=12 | Clear | 95% | Straightforward constant changes in `getNeuronSize()` and `labelRenderedSizeThreshold`. ForceAtlas2 position restoration bug (line 103 `attrs.x % 80`) must also be fixed. |
| 3 | Event hub nodes: center position, hashed color, fade on close | Complicated | 80% | Sigma v3 doesn't support diamond/hexagon node shapes natively (uses `type: 'circle'`). Custom node programs exist but add complexity. Alternative: use circles with larger size + border effect via nodeReducer. `activeEvents` hook already exists. |
| 4 | Activity edges: event-colored, solid, fade over 10s | Complex | 65% | Edge fade animation requires continuous `edgeReducer` re-evaluation + `sigma.refresh()` on `requestAnimationFrame`. At 200+ edges this may cause WebGL frame drops. Need a probe to validate performance. Also: tracking which tool triggered a knowledge search requires correlating sequential pulse batches (tool pulse followed by knowledge pulse), which isn't guaranteed to be in order. |
| 5 | Group drag: BFS on structural edges | Complex | 55% | Sigma.js `dragNode` event gives single node. Moving N connected nodes requires `setNodeAttribute(x,y)` for each in the BFS set, then `sigma.refresh()`. At 20+ nodes in a domain cluster, this may stutter. No prior art found in sigma.js examples for group drag. Needs a probe. |

## 3. Gap Analysis

### Task 1 (Structural Edges) -- 75%
* **Ambiguity:** Plan says "white dotted" but Sigma v3 only supports `line` edge type. Need to decide: upgrade sigma to v4, use thin white solid edges at low opacity, or add `@sigma/edge-curve` for visual variety.
* **Context:** `_phase_tool_priority` mapping from `brain.py` line 963 needed for phase->tool connections. Already read in this session.

### Task 3 (Event Hub Nodes) -- 80%
* **Ambiguity:** Plan says "diamond or hexagon shape" but Sigma v3 default node programs are `circle`, `point`, `square`, `triangle`. Diamond requires `@sigma/node-diamond` package or a custom WebGL node program.
* **Safety:** `useActiveEvents` hook must return event IDs that match pulse batch `event_id` values.

### Task 4 (Activity Edges) -- 65%
* **Ambiguity:** "fade over 10s" requires a continuous animation loop. Options: `setInterval` + `edgeReducer` recalculation + `sigma.refresh()`, or graphology attribute update + natural re-render. Neither is documented for this use case.
* **Safety:** No probe step for animation performance at scale.

### Task 5 (Group Drag) -- 55%
* **Context:** No sigma.js group drag examples found. The `@sigma/drag` plugin exists but handles single-node drag only.
* **Safety:** No probe step. This could fail entirely or cause layout thrashing.

## 4. Path to Green (Remediation)

- [ ] **Decision: Sigma v3 vs v4.** If v4 is stable, upgrade for native dashed edges + possibly better node shapes. If not, use thin white solid edges (opacity 0.15) for structural, full opacity colored for activity. Both visually distinct without dashing.
- [ ] **Decision: Node shapes.** Use `@sigma/node-square` for event nodes (available in v3) instead of diamond. Or use circles with 2x size and distinct color -- KISS.
- [ ] **Add probe: Activity edge animation.** Before task 4, add 50 edges with opacity decay via `setInterval` + `edgeReducer`, measure FPS. If <30fps at 50 edges, switch to static edges that appear/disappear instead of fade.
- [ ] **Defer group drag to v2.** Task 5 is Complex with 55% confidence and no prior art. Single-node drag works fine for now. Group drag can be added once the base graph is working. Remove from this plan.
- [ ] **Fix ForceAtlas2 position restoration.** Line 103 in CortexGraph.tsx: `attrs.x % 80` scrambles positions. Replace with saved pre-ForceAtlas2 coordinates for executive nodes.
- [ ] **Extract PHASE_TOOL_PRIORITY.** Already have the mapping from brain.py line 963: `triage: {refresh_gitlab_context, refresh_kargo_context}`, `investigate: {select_agent, create_plan, message_agent}`, etc.

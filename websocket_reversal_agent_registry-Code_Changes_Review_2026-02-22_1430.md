# WebSocket Reversal + Agent Registry -- Code Changes Review

**Date:** 2026-02-22 14:30  
**Reviewer:** Systems Architect (Principal Review)  
**Plan:** `websocket_reversal_agent_registry_7d7c0c69.plan.md`  
**Phases Implemented:** Phase A (Brain-side infra) + Phase B (Sidecar-as-client) + Partial Phase C (DevTeam class, test probe)  
**Files Changed:** 37 (3,631 additions, 1,379 deletions)  
**Prior Review:** [WS Reversal Implementation](374772a8-06c1-43c9-9c0f-f797a7495b55), [Server.js Modular Split](3d13410f-bef2-47f8-ac5b-f205cd93679a)

---

## 1. Developer + Technical Impact Summary

* **Risk Level:** MEDIUM -- Core dispatch path rearchitected but cleanly feature-flagged. All previously identified HIGH-severity issues have been resolved.
* **Breaking Changes:** None. `AGENT_WS_MODE=legacy` (default) preserves all existing behavior. Reverse mode is opt-in.
* **Overall Assessment:** Production-ready for Phase A/B merge. The infrastructure is clean, encapsulation is correct, race conditions are resolved, and the sidecar modular split is well-executed. Remaining items are LOW-severity polish and tracked Phase C work.

---

## 2. Downstream Impact Analysis

### Affected Consumers

| Modified Module | Consumers |
|---|---|
| `dispatch.py` (new) | `brain.py`, `dev_team.py`, `__init__.py`, `test_agent_bridge.py` |
| `agent_registry.py` (new) | `agent_ws_handler.py`, `dispatch.py`, `dev_team.py`, `main.py`, `dependencies.py`, tests |
| `task_bridge.py` (new) | `agent_ws_handler.py`, `dispatch.py`, `main.py`, `dependencies.py`, tests |
| `brain.py` (modified) | `main.py` (Brain init), all event processing paths |
| `dependencies.py` (modified) | `brain.py`, `dev_team.py` (lazy import) |
| `main.py` (modified) | Application root -- all routes, lifespan, WS endpoints |
| `server.js` (refactored → 8 modules) | Sidecar entrypoint -- affects all 4 agent pods |
| `llm/types.py` (modified) | `dev_team.py`, `brain.py` (via `llm/__init__.py`) |
| UI: `client.ts`, `types.ts`, `Dashboard.tsx` | New `AgentRegistryPanel` component, `/api/agents` endpoint |

### Risk Assessment

* **Existing tests:** `test_agent_bridge.py` covers the critical bridge path: register → dispatch → progress → result → idle, evict-on-reconnect, disconnect-unblocks-dispatch.
* **Silent failure risk:** LOW. The `get_by_id()` / `get_available()` public API methods enforce lock-guarded access. The TOCTOU race in `ws-client.js` is resolved by pre-setting task state before execution.
* **Legacy mode:** Fully preserved. The Brain's `_run_agent_task()` cleanly branches on `_ws_mode` with automatic fallback if registry is unavailable.

---

## 3. Findings & Fixes

### Resolved Since Prior Review (for traceability)

| # | File | Status | What Changed |
|---|------|--------|--------------|
| R-01 | `dispatch.py:60-61` | RESOLVED | Session-affinity lookup now uses `registry.get_by_id()` (was accessing `_lock`/`_agents` directly) |
| R-02 | `dev_team.py:196` | RESOLVED | `reply_to_agent` handler now uses `registry.get_by_id()` (was accessing privates) |
| R-03 | `dev_team.py:243-245` | RESOLVED | Renamed to `_qe_on_progress`, defined unconditionally (was variable shadowing) |
| R-04 | `dispatch.py:152-157` | RESOLVED | `send_cancel` uses polling loop with 100ms intervals + early exit (was blocking 5s sleep) |
| R-05 | `ws-client.js:182-184` + `cli-executor.js:303-309` | RESOLVED | Task state set BEFORE execution; `executeCLIStreaming` enriches existing task's `child` field (was TOCTOU race) |
| R-06 | `http-handler.js:114` | IMPROVED | Huddle timeout raised from 30s to 45s. Shell script uses 60s. 15s buffer is acceptable. |

### Remaining Findings

| # | File | Severity | Issue Type | Description |
|---|------|----------|------------|-------------|
| F-01 | `dev_team.py:192-208` | **MEDIUM** | Plan divergence | `reply_to_agent` is fully implemented, but the plan defers it to Phase E (Complex domain). The bidirectional flow works via held HTTP response, but it hasn't been probe-tested end-to-end. If the CLI agent's `huddleSendMessage` curl call completes (timeout or error) before the Manager replies, the reply is dropped. Track as Phase E probe. |
| F-02 | `dependencies.py:118-127` | **LOW** | Missing type hints | `set_registry_and_bridge(registry, bridge)` and `get_registry_and_bridge()` lack type annotations. Inconsistent with the typed pattern in the rest of the file. |
| F-03 | `config.js`, `state.js`, `stream-parser.js` | **LOW** | Missing AI shebang | Per project rules, all JS files should have `@ai-rules` headers. These three modules lack them. |
| F-04 | `ws-client.js` | **LOW** | Missing `followup` handler | Legacy `ws-server.js` handles `msg.type === 'followup'`. Reverse mode uses `type: "task"` with `session_id` (which maps to `--resume`), so the mechanism works -- but the behavioral difference should be documented. |
| F-05 | `Dockerfile:109` | **LOW** | Broad COPY | `COPY *.js .` copies all JS files. Consider `.dockerignore` or explicit list if test files appear in the directory. |
| F-06 | `brain.py` | **LOW** | DevTeam not wired | `DevTeam` is exported via `__init__.py` but `brain.py` dispatches `developer` role through `dispatch_to_agent`, not `DevTeam.process()`. Expected for Phase A/B. Phase C Step 10 wiring is pending. |
| F-07 | `types.ts:267-268, 305-307` | **LOW** | Duplicate header | `// Agent Mapping Helper` section header appears twice. |

### F-02 Fix (Type Hints)

```python
# dependencies.py -- add type annotations
from .agents.agent_registry import AgentRegistry
from .agents.task_bridge import TaskBridge

def set_registry_and_bridge(registry: AgentRegistry, bridge: TaskBridge) -> None:
    ...

def get_registry_and_bridge() -> tuple[AgentRegistry | None, TaskBridge | None]:
    ...
```

Note: Use `TYPE_CHECKING` guard if circular import is a concern (consistent with existing pattern in the file).

---

## 4. Verification Plan

### Must-Run Before Merge

1. **Bridge integration test** (`pytest tests/test_agent_bridge.py -v`): Validates register → dispatch → progress → result → idle, evict-on-reconnect, disconnect → error sentinel.

2. **Security enforcement**: Verify `dispatch_to_agent` blocks a prompt containing a forbidden pattern (e.g. `rm -rf /`) before any WS send. The `_check_security()` call is at line 57, before agent resolution. No dedicated test exists -- recommend adding one.

3. **Sidecar backward compatibility**: Start sidecar WITHOUT `BRAIN_WS_URL` set. Verify legacy WS server mode on `/ws` works unchanged. Start WITH `BRAIN_WS_URL=ws://localhost:8000/agent/ws` and verify reverse mode connects + registers.

4. **Brain legacy/reverse branch**: Verify `AGENT_WS_MODE=legacy` (default) routes through `agent.process()` with per-agent locks. Verify `AGENT_WS_MODE=reverse` routes through `dispatch_to_agent()` for architect/sysadmin/developer. Verify `_aligner` and `_archivist_memory` always use legacy path.

5. **UI proxy**: Verify `/api/agents` renders in the new Agents tab in the Dashboard right panel (Vite proxy config added for `/api`).

### Should-Run Pre-Deploy

6. **Cancel propagation**: Dispatch a task, cancel via Brain, verify sidecar kills CLI, sends error, persistent WS stays alive, dispatch unblocks.

7. **Reconnect resilience**: Kill sidecar pod mid-task. Verify reconnect with exponential backoff, re-register, Bridge error sentinel injection, dispatch returns error.

8. **Retryable error flow**: Sidecar sends `{"type": "error", "retryable": true}`. Verify Brain's `_run_agent_task()` hits the `RETRYABLE_SENTINEL` path and defers the event (does not fail it).

---

## 5. Observability (Production Feedback Loop)

### Logging Coverage (Already Implemented)

| Layer | What's Logged |
|---|---|
| AgentRegistry | register/unregister/evict (INFO), busy/idle transitions (DEBUG) |
| TaskBridge | queue create/put/delete (DEBUG), orphan sentinel warnings |
| Dispatch | security blocks, retryable errors, result resolution |
| WS Handler | registration timeout, disconnect, heartbeat pong (DEBUG) |
| Sidecar | connection lifecycle, task start/end, credential setup, timeout/cancel |

### Recommended Metrics (Future Work)

| Metric | Type | Why |
|---|---|---|
| `darwin_agent_registry_size` | Gauge | Zero agents = Brain cannot dispatch |
| `darwin_dispatch_duration_seconds` | Histogram | Track agent response time by role |
| `darwin_dispatch_retryable_total` | Counter | Detect systemic overload (429, timeouts) |
| `darwin_ws_reconnect_total` | Counter | Network instability indicator |

### Alerting (Future Work)

- `darwin_agent_registry_size == 0` for >2m: No agents connected
- `darwin_dispatch_retryable_total` rate >5/min: Agent overload

---

## 6. Architecture Assessment

### Strengths

1. **Feature flag isolation** -- `AGENT_WS_MODE` cleanly separates legacy and reverse paths with automatic fallback. Zero risk to existing behavior.

2. **Clean module boundaries** -- TaskBridge, AgentRegistry, and agent_ws_handler are pure infrastructure. No LLM logic leakage. Proper Hexagonal separation.

3. **Sidecar modular split** -- `server.js` (formerly ~1,400 lines) split into 8 focused CommonJS modules: `config.js` (37L), `state.js` (17L), `credentials.js` (379L), `cli-executor.js` (409L), `http-handler.js` (220L), `ws-server.js` (182L), `ws-client.js` (221L), `stream-parser.js` (67L). The `ws-client.js` reverse mode drops in cleanly because of the split.

4. **Encapsulation** -- All registry access goes through public methods (`get_by_id`, `get_available`, `get_by_event`, `mark_busy`, `mark_idle`). Lock-guarded. No private state access from outside the class.

5. **Race condition resolution** -- The `ws-client.js` TOCTOU race (task state vs. child spawn) is fixed by pre-setting state before execution and enriching the `child` field inside `executeCLIStreaming`. The `send_cancel` polling loop exits early when the queue is consumed.

6. **Test probe** -- `test_agent_bridge.py` validates the critical bridge path in three scenarios (happy path, evict, disconnect) without requiring Redis or sidecars.

7. **DevTeam function calling** -- `MANAGER_TOOL_SCHEMAS` enforce structured communication. Manager skills externalized to ConfigMap-updateable markdown. Max fix rounds (2) prevent infinite loops.

### Tracking (Phase C/D)

| Item | Phase | Status |
|---|---|---|
| Wire DevTeam into brain.py dispatch (Step 10) | C | Pending |
| Probe `reply_to_agent` bidirectional flow (Phase E) | E | Implemented but unprobed |
| Remove legacy code paths | D | Blocked by Phase C validation |
| Helm changes (BRAIN_WS_URL, remove sidecar URLs) | D | Not started |

---

## 7. Verdict

**Approve for merge** with LOW-severity items tracked as follow-ups. The five HIGH/MEDIUM issues from the prior review round have all been resolved. The feature flag provides a clean rollback path. The remaining findings (F-01 through F-07) are polish items and tracked future-phase work that do not block the Phase A/B merge.

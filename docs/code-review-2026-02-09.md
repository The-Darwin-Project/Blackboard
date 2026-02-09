# Blackboard Code Review — 2026-02-09

## Executive Summary

The Blackboard application is a well-architected autonomous cloud operations system implementing the **Blackboard Pattern** with multi-agent LLM orchestration. FastAPI backend, Redis-backed state, Gemini CLI sidecars over WebSocket, K8s metrics observer, and a React/TypeScript dashboard.

**Overall:** Production-capable with specific hardening gaps. Architecture is sound, separation of concerns is clean, LLM integration is well-designed. Main gaps are security hardening and operational robustness.

---

## Severity Summary

| Category | Count | Key Items |
|----------|-------|-----------|
| **HIGH** | 4 | No auth, XSS risk, no rate limiting, default Redis password |
| **MEDIUM** | 6 | Event loop tight spin, non-atomic close, deprecated dead code, 856-line component, broadcast backpressure, redundant sidecar logins |
| **LOW** | 6 | Dead code, missing AI shebangs, unpinned deps, no Dockerfile healthcheck, redundant K8s API calls, no-op handler |

---

## HIGH Severity

### H-1: No Authentication or Authorization on Any API Endpoint

- [ ] **Status:** Open

**Files:** All `src/routes/*.py`, `src/main.py` (WebSocket endpoint)

Every route (`/telemetry/`, `/chat/`, `/queue/`, `/metrics/`, `/topology/`, `/events/`, `/ws`) is completely open. Any pod in the namespace (or anyone with OpenShift route access) can:
- Inject telemetry to trigger autonomous remediation
- Approve/reject plans
- Create events that cause real GitOps changes (commits, pushes)

**Recommendation:** Add bearer token check via FastAPI middleware or dependency. For WebSocket, validate during `accept()` phase.

---

### H-2: `dangerouslySetInnerHTML` Without Sanitization (XSS)

- [ ] **Status:** Open

**File:** `ui/src/components/ConversationFeed.tsx`

Markdown content (from agent responses and user messages) is rendered via `dangerouslySetInnerHTML` without sanitization. A crafted payload in telemetry or chat could inject XSS. Especially risky since LLM-generated content is not sanitized.

**Recommendation:** Use DOMPurify before rendering, or switch to `react-markdown` which handles sanitization.

---

### H-3: No Rate Limiting on Telemetry or Chat Endpoints

- [ ] **Status:** Open

**Files:** `src/routes/telemetry.py`, `src/routes/chat.py`

A rogue or misconfigured client can flood `/telemetry/` and trigger unbounded LLM calls (Aligner Flash + Brain Pro). Each telemetry push can trigger `_analyze_metrics_signals` which calls Vertex AI. This is both a DoS vector and a cost amplifier.

**Recommendation:** Add rate limiting per service (telemetry) and per IP/session (chat). `slowapi` is a quick win for FastAPI.

---

### H-4: Redis Default Password in Helm Values

- [ ] **Status:** Open

**File:** `helm/values.yaml`

Ships with hardcoded default Redis password (`darwin-brain`). Combined with `existingSecret` being empty by default, a fresh deployment uses a well-known password.

**Recommendation:** Remove default password; require `existingSecret` or use a Helm-generated secret.

---

## MEDIUM Severity

### M-1: Missing `sleep` in Brain Event Loop (Tight Spin)

- [ ] **Status:** Open

**File:** `src/agents/brain.py` — `start_event_loop()`

The event loop only sleeps on exception. On the happy path, `dequeue_event` blocks for up to 5s (Redis `brpop` timeout), but the active events scan runs every iteration with no throttle. Under load with many active events, this is a tight loop issuing repeated Redis queries and potentially re-triggering `process_event` on already-active events.

**Recommendation:** Add `await asyncio.sleep(1)` at the end of each loop iteration (outside exception handler).

---

### M-2: `close_event` Is Not Atomic

- [ ] **Status:** Open

**File:** `src/state/blackboard.py` — `close_event()`

While `append_turn` correctly uses `WATCH/MULTI/EXEC` for optimistic locking, `close_event` does a plain `GET -> modify -> SET` without transaction guards. Under concurrent processing, a turn appended between GET and SET would be lost.

**Recommendation:** Use the same `WATCH/MULTI/EXEC` pattern as `append_turn`.

---

### M-3: Deprecated Task Queue Methods Still Present

- [ ] **Status:** Open

**File:** `src/state/blackboard.py`

Four deprecated methods remain: `enqueue_architect_task`, `dequeue_architect_task`, `enqueue_plan_for_execution`, `dequeue_plan_for_execution`. Marked deprecated but still importable — adds confusion and dead code surface area.

**Recommendation:** Remove them entirely. The event conversation system replaced them.

---

### M-4: ConversationFeed.tsx Is 856 Lines

- [ ] **Status:** Open

**File:** `ui/src/components/ConversationFeed.tsx`

Single component handles: event selection, conversation display, markdown viewer, image upload, WebSocket routing, event creation, approval/rejection, draggable floating window. Violates the project's own `<=100 lines` guideline.

**Recommendation:** Split into: `EventList`, `ConversationView`, `MarkdownViewer`, `ImageUploader`, `ApprovalControls`.

---

### M-5: No Backpressure on WebSocket Broadcast

- [ ] **Status:** Open

**File:** `src/main.py` — `broadcast_to_ui()`

Iterates all connected UI clients sequentially. If a client is slow, `await client.send_text()` blocks the entire broadcast loop. With many clients or high-frequency agent progress messages, this could stall the Brain event loop.

**Recommendation:** Use `asyncio.create_task` per send, or implement a bounded outbound queue per client with eviction.

---

### M-6: Sidecar ArgoCD/Kargo Login Runs on Every Task

- [ ] **Status:** Open

**File:** `gemini-sidecar/server.js` — `setupCLILoginsBackground()`

Spawns background `argocd login` and `kargo login` processes on *every* incoming WebSocket task, not just once at startup. Each agent task triggers redundant login attempts.

**Recommendation:** Run logins once at startup, track success state. Re-login only on auth failure.

---

## LOW Severity

### L-1: Dead Code — `useWebSocket.ts`

- [ ] **Status:** Open

**File:** `ui/src/hooks/useWebSocket.ts` (87 lines)

Standalone WebSocket hook appears unused — `WebSocketContext.tsx` is the active provider. Duplicate logic.

**Recommendation:** Remove if confirmed unused.

---

### L-2: Dead Code — `handlePlanClick` No-Op in Dashboard

- [ ] **Status:** Open

**File:** `ui/src/components/Dashboard.tsx`

`handlePlanClick` exists but does nothing. Dead code.

**Recommendation:** Remove or implement.

---

### L-3: Missing AI Shebang Headers

- [ ] **Status:** Open

**Files:** All `*.py`, `*.ts`, `*.js` files

Per the project's own `.cursor/rules`, all code files should have `@ai-rules:` headers. None of the reviewed files have them.

**Recommendation:** Add headers during next edit pass on each file.

---

### L-4: `requirements.txt` Has No Version Pins

- [ ] **Status:** Open

**File:** `requirements.txt`

All dependencies are unpinned. For a production system making autonomous infrastructure changes, a breaking change in `google-genai`, `redis`, or `fastapi` could silently break the system.

**Recommendation:** Pin major versions at minimum (`google-genai>=1.60.0,<2.0`, `fastapi>=0.115,<1.0`).

---

### L-5: No Health Check in Dockerfile

- [ ] **Status:** Open

**File:** `Dockerfile`

No `HEALTHCHECK` instruction. K8s probes handle this in-cluster, but it's a gap for standalone Docker runs and `docker-compose` setups.

**Recommendation:** Add `HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1`.

---

### L-6: K8s Observer Makes Redundant API Calls

- [ ] **Status:** Open

**File:** `src/observers/kubernetes.py` — `_get_service_name()`

Calls `read_namespaced_pod` for every pod on every polling cycle (5s interval). With 20 pods, that's ~240 API calls/min for label lookups alone.

**Recommendation:** Cache pod-to-service mappings with a TTL (labels rarely change). Invalidate on pod list changes.

---

## Architecture Strengths (Preserve These)

1. **Clean Blackboard Pattern** — Redis-backed central state with well-defined layers (Structure, Metadata, Plan, Event Queue). Agents never talk directly to each other.

2. **LLM-First Decision Engine** — Brain contains zero routing logic in Python. All decision-making delegated to Gemini Pro via function calling. System is genuinely adaptive.

3. **Dual-Source Metrics with Smart Merging** — Aligner's `_buffer_metric` merges self-reported and K8s observer data into 5s time buckets using `max()`. Elegantly handles impedance mismatch between app-level and container-level metrics.

4. **Circuit Breakers Everywhere** — Max turns (30), max duration (30 min), max LLM iterations (5), routing depth (15), event dedup, time-based cooldowns. System won't run away.

5. **Cynefin Integration** — Aligner classifies events into Cynefin domains; Brain system prompt uses classification to determine response pattern.

6. **WebSocket Architecture** — Bidirectional streaming with per-agent concurrency locks (Brain-side + client-side defense-in-depth). Progress streaming gives real-time visibility.

7. **GitOps-Only Mutations** — Air gap between read-only kubectl and GitOps-only writes enforced through GEMINI.md rules, security patterns, and Brain system prompt.

8. **Optimistic Locking on Event Turns** — `append_turn` uses Redis `WATCH/MULTI/EXEC` for safe concurrent writes.

---

## Suggested Fix Order

1. **H-1** (Auth) — Highest risk, blocks production deployment
2. **H-3** (Rate limiting) — Cost/DoS protection
3. **H-4** (Redis password) — Quick fix, high impact
4. **H-2** (XSS) — Add DOMPurify, straightforward
5. **M-2** (Atomic close) — Data integrity
6. **M-1** (Event loop sleep) — Operational stability
7. **M-5** (Broadcast backpressure) — Scalability
8. **M-6** (Sidecar login) — Unnecessary API calls
9. **M-3** (Remove deprecated) — Code hygiene
10. **M-4** (Split ConversationFeed) — Maintainability
11. **L-*** — Address during normal development flow

---
name: event-rename-and-lite-llm-naming
overview: Event title generation via lightweight LLM (gemini-3.5-flash-lite) for user-created events (chat/slack) with user manual rename override, Hexagonal broadcast port decoupling, and real-time UI/Slack sync
jira: VMER-2229
jira_url: https://redhat.atlassian.net/browse/VMER-2229
docs_hub_plan: null
docs_hub_mr: null
todos:
  - id: step-1
    content: "[Clear] Extend EventDocument schema in src/models.py and create_event signature in src/state/blackboard.py with title and title_source"
    status: completed
  - id: step-2
    content: "[Complicated] Implement atomic update_event_title_if_not_user in BlackboardState with WATCH/MULTI transaction and retry exhaustion safety"
    status: completed
  - id: step-3
    content: "[Complicated] Implement event_namer background module with create_adapter, prompt sanitization, output cleaning, GC task set, and brain.broadcast"
    status: completed
  - id: step-4
    content: "[Clear] Wire synchronous fallback title ('Untitled Event' guard) and async naming trigger in src/routes/chat.py, src/adapters/dashboard_ws.py, and src/channels/slack.py"
    status: completed
  - id: step-5
    content: "[Complicated] Implement PATCH /queue/{event_id}/title with Pydantic validator, can_rename_event authz predicate, idempotency check, closed guard, and brain.broadcast"
    status: completed
  - id: step-6
    content: "[Clear] Add title/title_source serialization to queue list projections and sanitize markdown titles with _esc() in event_markdown.py"
    status: completed
  - id: step-7
    content: "[Complicated] Wire event_title_updated handler into SlackChannel.broadcast_handler in src/channels/slack.py with DM gating and error isolation"
    status: completed
  - id: step-8
    content: "[Clear] Update frontend EventDocument and ActiveEvent in ui/src/api/types.ts and optimistic TanStack query cache patch in OpsStateContext"
    status: completed
  - id: step-9
    content: "[Complicated] Implement inline title editing with useOpsControl, Enter/Escape handling, and whitespace validation in WorkspaceHeader and WorkspaceInspector"
    status: completed
  - id: step-10
    content: "[Clear] Update WorkspaceTaskItem row 1 (line 80) layout to display title with fallback hierarchy (title || service || sliced id) and flex truncation"
    status: completed
isProject: false
---

# Darwin: Event Renaming & Background LLM Naming for User Events (Chat/Slack)

**Jira Issue:** [VMER-2229](https://redhat.atlassian.net/browse/VMER-2229) (Parent Epic: [VMER-62](https://redhat.atlassian.net/browse/VMER-62)) | **Plan Attached:** Yes

---

## Amendment Ledger (Pre-Flight Convergence Round 2)

| Item ID | Category | Change Description | Target Sections |
| :--- | :--- | :--- | :--- |
| **R-1** | Syntax & Prompt Sanitization | In `src/agents/event_namer.py`, call `sanitize_prompt_text(text, max_len=300)` with keyword-only argument `max_len` and explicitly strip XML boundary tags `</user_request>` from input. | Section 4 (Step 3) |
| **R-2** | Slack Bolt API Property | In `src/channels/slack.py`, invoke Slack Bolt client via `self._app.client.assistant_threads_setTitle(...)` (aligned with live `SlackChannel` property `_app.client`). | Section 4 (Step 7) |
| **R-3** | Auth Logic & Dex Groups | In `src/auth.py`, place strict source restriction `if source not in ("chat", "slack"): return False` before `if not auth_enabled: return True`. Match Dex groups using case-normalized set intersection (`APPROVER_GROUPS` and `OBS_ADMIN_GROUPS`). Support `auth_enabled: Optional[bool] = None`. | Section 3.2, Section 4 (Step 5) |
| **R-4** | REST Endpoint Hardening | In `src/routes/queue.py`, return HTTP 401 when `auth_enabled and not user.email`. Emit structured `logger.warning("[Audit] Denied title rename: ...")` on 403 denial. Guard closed events with `EventStatus.CLOSED` / `"closed"` check (HTTP 409). In `TitleUpdateRequest`, collapse consecutive whitespace/newlines using `re.sub(r"\s+", " ", v).strip()`. Assert HTTP 422 in validation tests. | Section 4 (Step 5), Section 5 (T-SEC-3) |
| **R-5** | Redis Pipeline Transaction | In `BlackboardState.update_event_title_if_not_user()`, use `async with self.redis.pipeline(transaction=True) as pipe:` matching `stamp_event:1715`, and check lowercase document status `str(doc.get("status", "")).lower() == "closed"`. | Section 4 (Step 2) |

---

## Amendment Ledger (Pre-Flight Convergence Round 1)

| Item ID | Category | Change Description | Target Sections |
| :--- | :--- | :--- | :--- |
| **B-1** | Hexagonal Architecture | Decoupled point-to-point calls to Slack/WS. All title updates now publish `{"type": "event_title_updated", ...}` through `brain.broadcast(...)`. Registered channel adapters (`DashboardWSAdapter.__call__` and `SlackChannel.broadcast_handler`) consume the broadcast. | Sections 1, 4, 5 (Steps 3, 5, 7) |
| **B-2** | Schema & State Signature | Added `title: Optional[str] = None` and `title_source: Optional[str] = None` parameters to `BlackboardState.create_event()` in `src/state/blackboard.py`. | Section 5 (Step 1, Step 4) |
| **B-3** | Contracts & Factory | Corrected LLM adapter import to `from src.agents.llm import create_adapter` and passed 4 required positional arguments: `create_adapter("gemini", project, location, "gemini-3.5-flash-lite")`. | Section 5 (Step 3) |
| **B-4** | Paths & Class Hygiene | Fixed 5 hallucinated file paths (`src/routes/chat.py`, `src/channels/slack.py`, `src/adapters/dashboard_ws.py`, `src/agents/llm/__init__.py`, `ui/src/api/types.ts`). Removed phantom `ActiveEvent` from Python models (it is purely TypeScript). Updated `WorkspaceTaskItem.tsx` line reference from L186 to L80. | Sections 2, 5 (Steps 1, 3, 4, 8, 10) |
| **B-5** | Security & Auth | Added pure predicate `can_rename_event(created_by_email, user_email, source, roles, auth_enabled)` in `src/auth.py`. Gated renames to `source in ('chat', 'slack')` and blocked unowned event IDOR (`created_by_email is None`). Added structured `[Audit]` logging. | Section 4, Section 5 (Step 5) |
| **B-6** | Security & XSS | Wrapped `event.title` in `_esc(event.title)` within `src/utils/event_markdown.py` to prevent stored markdown/HTML injection in rehype-raw renderers. | Section 5 (Step 6) |
| **B-7** | Input Validation | Added Pydantic `@field_validator("title")` on `TitleUpdateRequest` that strips whitespace, replaces newlines, enforces `1 <= len(stripped) <= 100`, and rejects empty/whitespace-only input. | Section 5 (Step 5) |
| **B-8** | Robustness & GC Defense | Added module-level `_background_tasks: set[asyncio.Task] = set()` in `event_namer.py` to prevent premature Python task garbage collection. Added defensive LLM output stripping (markdown symbols, quotes, newlines, 100-char cap). Added unwatch and retry exhaustion handling to Redis WATCH transaction. | Section 5 (Steps 2, 3) |
| **B-9** | UI & Cache Sync | Corrected hook in `WorkspaceHeader.tsx` to `useOpsControl()`. Ensured TanStack query cache invalidates `['eventDocument', eventId]`. Updated task list item to preserve fallback chain: `evt.title || evt.service || evt.id.slice(4, 12)`. | Section 5 (Steps 8, 9, 10) |
| **B-10** | ATDD Scenarios | Added security and edge-case scenarios T-SEC-1 through T-SEC-6 to Section 6. | Section 6 |

---

## 1. System Architecture & Lifecycle Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as User (Chat / Slack)
    participant Ingress as Ingress (src/routes/chat.py / src/channels/slack.py)
    participant Redis as Redis (BlackboardState)
    participant Namer as Event Namer (src/agents/event_namer.py)
    participant Brain as Brain Port (brain.broadcast)
    participant WS as WebSocket Hub (DashboardWSAdapter)
    participant UI as Workspace UI (React)
    participant SlackAPI as Slack Channel (SlackChannel.broadcast_handler)

    Note over User, Ingress: 1. Event Ingestion Phase (Synchronous, Zero-Latency Impact)
    User->>Ingress: Send initial prompt / message
    Ingress->>Ingress: Fallback title: text[:60].strip() or "Untitled Event"
    Ingress->>Redis: create_event(..., title=fallback, title_source="fallback")
    Redis-->>Ingress: EventDocument (evt-xxx created)
    Ingress-->>User: HTTP 201 Created / Slack ack
    Ingress-)Namer: _background_tasks.add(asyncio.create_task(generate_event_title(...)))

    Note over Namer, SlackAPI: 2. Background LLM Naming Phase (Async, Fail-Open)
    Namer->>Namer: create_adapter("gemini", project, location, "gemini-3.5-flash-lite")
    Namer->>Namer: asyncio.wait_for(adapter.generate(prompt), timeout=10.0)
    alt LLM Success (Returns clean 3-6 word title)
        Namer->>Redis: update_event_title_if_not_user(evt_id, clean_title, "llm")
        alt User has NOT renamed event (title_source != "user")
            Redis-->>Namer: True (Atomic write committed)
            Namer-)Brain: broadcast({"type": "event_title_updated", "event_id": evt_id, "title": clean_title, "title_source": "llm"})
            Brain-)WS: broadcast_handler(msg) -> Send WS frame to connected clients
            WS-)UI: OnMessage -> Optimistic TanStack Query cache patch
            Brain-)SlackAPI: broadcast_handler(msg)
            opt Slack DM event (channel_type == "im" and slack_thread_ts)
                SlackAPI-)SlackAPI: assistant_threads_setTitle(thread_ts, clean_title)
            end
        else User already renamed event (title_source == "user")
            Redis-->>Namer: False (Race-guard: discarded LLM title)
        end
    else LLM Timeout / Quota Exhaustion / Error
        Namer->>Namer: Log warning; preserve fallback title
    end

    Note over User, Brain: 3. User Manual Rename Phase (REST API & Real-Time Sync)
    User->>UI: Click title / pencil icon -> Enter new title
    UI->>Ingress: PATCH /queue/{event_id}/title {"title": "Fix OOM on Redis cluster"}
    Ingress->>Ingress: can_rename_event(doc.created_by_email, user.email, doc.source, user.roles)
    alt Authorized & Open Event
        opt Title Unchanged (Idempotency Short-Circuit)
            Ingress-->>UI: HTTP 200 (No-op, return current doc)
        end
        Ingress->>Redis: stamp_event(evt_id, title=req.title, title_source="user")
        Redis-->>Ingress: Updated EventDocument
        Ingress-)Brain: broadcast({"type": "event_title_updated", "event_id": evt_id, "title": req.title, "title_source": "user"})
        Brain-)WS: Fanout to UI
        Brain-)SlackAPI: Fanout to Slack (if DM)
        Ingress-->>UI: HTTP 200 OK {"id": evt_id, "title": req.title, "title_source": "user"}
    else Unauthorized or Closed Event
        Ingress-->>UI: HTTP 403 Forbidden / HTTP 409 Conflict
    end
```

---

## 2. Merged Evidence Summary

Explorers A (`claude-4.6-opus-max-thinking`), B (`gemini-3.1-pro`), and C (`claude-sonnet-5-thinking-xhigh`) conducted codebase scans across `BlackBoard/`. Evidence merged as follows:

1. **Schema & Models (`src/models.py`)**:
   - `EventDocument` (line 423) defines the durable event document schema.
   - `title: str | None = Field(default=None, description="Concise human-readable event title")` and `title_source: Literal["fallback", "llm", "user"] | None = Field(default=None)` can be safely added with default `None` for backward compatibility with existing Redis JSON hashes.
   - Note: `ActiveEvent` does NOT exist in backend Python models; it exists solely in the React frontend (`ui/src/api/types.ts:242`).
2. **State & Redis Storage (`src/state/blackboard.py`)**:
   - `create_event` (line 1142) must be extended to accept `title: Optional[str] = None` and `title_source: Optional[str] = None`, stamping them into `EventDocument`.
   - `stamp_event` (line 1703) performs unconditional key-value writes.
   - To prevent a delayed background LLM title from overwriting an immediate manual user rename, implement `update_event_title_if_not_user(event_id: str, title: str, title_source: str = "llm") -> bool` in `BlackboardState` using Redis `WATCH`/`MULTI` pipeline transaction. If `doc.get("title_source") == "user"` or document does not exist or event is closed, unwatch and return `False`.
3. **Queue API Endpoints (`src/routes/queue.py`)**:
   - `GET /queue/{event_id}` (line 357) uses `response_model=EventDocument` and auto-serializes new fields.
   - `list_active_events` (line 170), `list_waiting_approval_events` (line 206), and `list_closed_events` (line 661) construct explicit Python projection dictionaries. All three must include `"title": getattr(event, "title", None)` and `"title_source": getattr(event, "title_source", None)`.
   - New endpoint `PATCH /queue/{event_id}/title` requires payload `TitleUpdateRequest(title: str)` with Pydantic validator, identity resolution via `get_user_from_request(request)`, authorization via `can_rename_event`, and broadcast via `brain.broadcast(...)`.
4. **LLM Naming Adapter (`src/agents/event_namer.py`)**:
   - Import `from src.agents.llm import create_adapter`. Pass `create_adapter("gemini", os.getenv("GCP_PROJECT", ""), os.getenv("GCP_LOCATION", "us-central1"), "gemini-3.5-flash-lite")`.
   - Wrap generation in `asyncio.wait_for(..., timeout=10.0)` with a broad `try/except Exception` fail-open guard.
   - Maintain module-level `_background_tasks: set[asyncio.Task] = set()` to prevent task garbage collection mid-flight.
5. **Slack API Constraints (`src/channels/slack.py`)**:
   - `assistant_threads_setTitle` is strictly supported only on Slack Assistant threads / DMs (`channel_type == "im"`), and raises errors on public channel mentions.
   - Slack title sync is handled through `SlackChannel.broadcast_handler(message)` when message type is `event_title_updated`, keeping Slack logic decoupled.
6. **Frontend UI Components (`ui/src/`)**:
   - Types in `ui/src/api/types.ts`: Add `title?: string | null` and `title_source?: 'fallback' | 'llm' | 'user' | null` to `EventDocument` and `ActiveEvent`.
   - `WorkspaceHeader.tsx`: Inline editable title using `useOpsControl()`, pencil icon, `Enter` to commit, `Escape` to cancel, and optimistic updates via TanStack Query cache.
   - `WorkspaceTaskItem.tsx` (line 80): Display title with fallback chain `{evt.title || evt.service || evt.id.slice(4, 12)}` and CSS flex truncation.
   - `WorkspaceInspector.tsx`: Display title and title source badge (`user` / `llm` / `fallback`).

---

## 3. Implementation Strategy

### 3.1 Hexagonal Isolation & Ports/Adapters
- **Broadcast Port**: No direct point-to-point calls between `event_namer.py` and `dashboard_ws.py` or `slack.py`. All updates flow through `brain.broadcast(message)`.
- **Channel Adapters**:
  - `DashboardWSAdapter.__call__` forwards messages to WebSocket clients.
  - `SlackChannel.broadcast_handler` intercepts `event_title_updated` and updates Slack DM thread title if applicable.
- **Fail-Open Graceful Degradation**: If Vertex AI is unreachable or times out (>10s), the synchronous fallback title (`text[:60] or "Untitled Event"`) persists with `title_source="fallback"`. Ingress latency is zero.

### 3.2 Security & Authorization Architecture
- **Authorization Predicate**: In `src/auth.py`, implement pure function:
  ```python
  def can_rename_event(
      created_by_email: Optional[str],
      user_email: Optional[str],
      source: str,
      roles: list[str],
      auth_enabled: Optional[bool] = None,
  ) -> bool:
      # Strict source restriction: automated events cannot be renamed via user API
      if source not in ("chat", "slack"):
          return False
      if auth_enabled is None:
          auth_enabled = bool(DEX_ENABLED or TRUSTED_PROXY_ENABLED)
      if not auth_enabled:
          return True
      user_roles_lower = {r.lower().strip() for r in roles}
      approver_groups_lower = {g.lower().strip() for g in APPROVER_GROUPS}
      obs_admin_groups_lower = {g.lower().strip() for g in OBS_ADMIN_GROUPS}
      if user_roles_lower & (approver_groups_lower | obs_admin_groups_lower):
          return True
      if not user_email or not created_by_email:
          return False  # Block IDOR on unowned events
      return user_email.lower().strip() == created_by_email.lower().strip()
  ```
- **Stored XSS Prevention**: In `src/utils/event_markdown.py`, wrap `event.title` in `_esc(event.title)` before markdown interpolation.
- **Prompt Injection Defense**: Frame user message in `<user_request>` XML tags and sanitize with `sanitize_prompt_text`. System prompt strictly commands the LLM to output a 3-6 word title and never leak instructions.
- **Idempotency & Rate Limiting**: If `req.title == event.title`, return HTTP 200 immediately without database writes or broadcasts.

---

## 4. Atomic Execution Steps

### Step 1: Extend Event Schema Models and BlackboardState.create_event
- **Files**: `src/models.py`, `src/state/blackboard.py`
- **Cynefin**: Clear
- **Action**:
  1. In `src/models.py`, add `title: str | None = Field(default=None, description="Concise human-readable event title")` and `title_source: Literal["fallback", "llm", "user"] | None = Field(default=None, description="Origin of event title")` to `EventDocument`.
  2. In `src/state/blackboard.py` (`create_event` line 1142), add optional parameters `title: Optional[str] = None` and `title_source: Optional[str] = None`, stamping them into the initialized `EventDocument`.
- **Verification**: `python -m pytest tests/test_models.py` passes without schema validation regression.

### Step 2: Atomic Conditional Title Update in BlackboardState (WATCH/MULTI)
- **File**: `src/state/blackboard.py`
- **Cynefin**: Complicated
- **Action**: Implement `async def update_event_title_if_not_user(self, event_id: str, title: str, title_source: str = "llm") -> bool`:
  1. Execute in a 3-retry loop:
     - Start transactional pipeline: `async with self.redis.pipeline(transaction=True) as pipe:`
     - `await pipe.watch(key)`
     - Fetch document: `raw = await pipe.get(key)`. If `not raw`: `await pipe.unwatch()`; return `False`.
     - Deserialize doc. If `str(doc.get("status", "")).lower() == "closed"` or `doc.get("title_source") == "user"`: `await pipe.unwatch()`; return `False`.
     - Update fields: `doc["title"] = title`, `doc["title_source"] = title_source`.
     - `pipe.multi()`, `pipe.set(key, json.dumps(doc))`, `await pipe.execute()`.
     - Return `True`.
  2. Catch `WatchError`: If retries exhausted, ensure unwatch and return `False`.
- **Verification**: Dedicated concurrency test in `tests/test_blackboard_title_race.py` simulating concurrent user rename vs LLM completion passes.

### Step 3: Event Namer Background Module
- **File**: `src/agents/event_namer.py` (New file, <=100 lines)
- **Cynefin**: Complicated
- **Action**:
  1. Maintain module-level `_background_tasks: set[asyncio.Task] = set()`.
  2. Define `async def generate_event_title(blackboard, brain, event_id: str, text: str, source: str) -> None`:
  3. Clean text: `clean_input = sanitize_prompt_text(text, max_len=300).replace("</user_request>", "")`.
  4. System prompt: `"Generate a concise 3-6 word title summarizing the user request. Respond with ONLY the title string, no quotes, no markdown, no punctuation."`
  5. User prompt: `f"<user_request>\n{clean_input}\n</user_request>"`
  6. Call adapter:
     ```python
     from ..llm import create_adapter
     project = os.getenv("GCP_PROJECT", "")
     location = os.getenv("GCP_LOCATION", "us-central1")
     adapter = create_adapter("gemini", project, location, "gemini-3.5-flash-lite")
     ```
  7. Timeout wrapper: `response = await asyncio.wait_for(adapter.generate(system_prompt=system_prompt, contents=user_prompt), timeout=10.0)`
  8. Output sanitization: `clean_title = (response.text or "").strip().strip('"\'*`').splitlines()[0].strip()[:100]`. If empty, return.
  9. Update state: `updated = await blackboard.update_event_title_if_not_user(event_id, clean_title, "llm")`.
  10. If `updated`: `await brain.broadcast({"type": "event_title_updated", "event_id": event_id, "title": clean_title, "title_source": "llm"})`.
  11. Wrap in `try/except Exception: logger.warning("LLM title generation failed for %s", event_id)` fail-open guard.
  12. Helper `spawn_event_namer_task(blackboard, brain, event_id, text, source)` wraps in `create_task`, adds to `_background_tasks`, and adds `task.add_done_callback(_background_tasks.discard)`.
- **Verification**: Unit tests in `tests/test_event_namer.py` with mocked LLM adapter returning titles and timeout simulation.

### Step 4: Wire Ingestion Triggers in Chat, WS, and Slack
- **Files**: `src/routes/chat.py`, `src/adapters/dashboard_ws.py`, `src/channels/slack.py`
- **Cynefin**: Clear
- **Action**:
  1. In `src/routes/chat.py` (line 58): Compute `fallback = user_message[:60].strip() or "Untitled Event"`. Pass `title=fallback, title_source="fallback"` to `create_event`. Call `spawn_event_namer_task(blackboard, brain, event_id, user_message, "chat")`.
  2. In `src/adapters/dashboard_ws.py`: Compute `fallback = message_text[:60].strip() or "Untitled Event"`. Pass `title=fallback, title_source="fallback"` to `create_event`. Call `spawn_event_namer_task(blackboard, brain, event_id, message_text, "chat")`.
  3. In `src/channels/slack.py` (line 467): Compute `fallback = event_text[:60].strip() or "Untitled Event"`. Pass `title=fallback, title_source="fallback"` to `create_event`. Call `spawn_event_namer_task(blackboard, brain, event_id, event_text, "slack")`.
- **Verification**: `python -m pytest tests/test_routes_chat.py tests/test_slack_channel.py` validates `title` and `title_source` set upon creation.

### Step 5: PATCH /queue/{event_id}/title Endpoint
- **File**: `src/routes/queue.py`
- **Cynefin**: Complicated
- **Action**:
  1. Define Pydantic model:
     ```python
     class TitleUpdateRequest(BaseModel):
         title: str

         @field_validator("title")
         @classmethod
         def validate_title(cls, v: str) -> str:
             collapsed = re.sub(r"\s+", " ", v).strip()
             if not collapsed:
                 raise ValueError("Title cannot be empty or whitespace only")
             if len(collapsed) > 100:
                 raise ValueError("Title cannot exceed 100 characters")
             return collapsed
     ```
  2. Implement `@router.patch("/{event_id}/title") async def update_event_title(request: Request, event_id: str, req: TitleUpdateRequest)`:
  3. Load event document: `event = await blackboard.get_event(event_id)`. If not found, raise `HTTPException(404, detail="Event not found")`.
  4. Closed guard: If `str(event.status).lower() == "closed"` or `event.status == EventStatus.CLOSED`, raise `HTTPException(409, detail="Cannot rename closed event")`.
  5. Resolve user: `user = get_user_from_request(request)`.
  6. Authenticated guard: If `auth_enabled and not user.email`, raise `HTTPException(401, detail="Authentication required")`.
  7. Authorization check: `if not can_rename_event(event.created_by_email, user.email, event.source, user.roles): logger.warning("[Audit] Denied title rename: user=%s event=%s source=%s", user.email, event_id, event.source); raise HTTPException(403, detail="Forbidden")`.
  8. Idempotency check: If `req.title == getattr(event, "title", None)`, return `{"id": event_id, "title": req.title, "title_source": event.title_source}`.
  9. Commit rename: `await blackboard.stamp_event(event_id, title=req.title, title_source="user")`.
  10. Audit log: `logger.info("[Audit] Event %s renamed to '%s' by %s", event_id, req.title, user.email)`.
  11. Broadcast: `await brain.broadcast({"type": "event_title_updated", "event_id": event_id, "title": req.title, "title_source": "user"})`.
  12. Return `{"id": event_id, "title": req.title, "title_source": "user"}`.
- **Verification**: Integration tests in `tests/test_queue_title_patch.py` verifying rename, 422 on whitespace/length validation failure, 401 on unauthenticated, 403 on IDOR/unauthorized with audit log, 409 on closed, and idempotency.

### Step 6: Queue Projection Endpoints Serialization & Markdown Escaping
- **Files**: `src/routes/queue.py`, `src/utils/event_markdown.py`
- **Cynefin**: Clear
- **Action**:
  1. In `src/routes/queue.py`: In `list_active_events` (line 170), `list_waiting_approval_events` (line 206), and `list_closed_events` (line 661), add `"title": getattr(event, "title", None)` and `"title_source": getattr(event, "title_source", None)` to the projection dictionaries.
  2. In `src/utils/event_markdown.py`: Wrap `event.title` in `_esc(event.title)` before rendering title headers to prevent stored XSS.
- **Verification**: Test endpoint responses via `TestClient` in `tests/test_queue_projection_titles.py`.

### Step 7: Slack DM Thread Title Sync in SlackChannel Broadcast Handler
- **File**: `src/channels/slack.py`
- **Cynefin**: Complicated
- **Action**:
  1. In `SlackChannel.broadcast_handler(self, message: dict)`: Add handler for `msg_type == "event_title_updated"`.
  2. Extract `event_id = message.get("event_id")`, `title = message.get("title")`.
  3. Load event doc: `event = await self._blackboard.get_event(event_id)`.
  4. If `event` has `slack_channel_id` and `slack_thread_ts`:
     - Verify DM context: `if event.slack_channel_id.startswith("D")` or `channel_type == "im"`:
     - Execute `await self._app.client.assistant_threads_setTitle(channel_id=event.slack_channel_id, thread_ts=event.slack_thread_ts, title=title[:100])`.
     - Wrap in `try/except Exception as e: logger.debug("Slack title sync ignored: %s", e)`.
- **Verification**: Unit test with mocked Slack WebClient verifying title sync on broadcast message.

### Step 8: Frontend TypeScript Schema & OpsStateContext Query Invalidation
- **Files**: `ui/src/api/types.ts`, `ui/src/contexts/OpsStateContext.tsx`
- **Cynefin**: Clear
- **Action**:
  1. In `ui/src/api/types.ts`: Add `title?: string | null` and `title_source?: 'fallback' | 'llm' | 'user' | null` to `EventDocument` and `ActiveEvent`.
  2. In `ui/src/contexts/OpsStateContext.tsx`: Handle `event_title_updated` in WS dispatcher:
     - Update event in `activeEvents` and `waitingApprovalEvents` via `optimisticPatchEvent(event_id, { title, title_source })`.
     - Invalidate or set query data for `['eventDocument', event_id]`.
- **Verification**: `npx tsc -b` / `npm run build` compiles cleanly without type errors.

### Step 9: Inline Title Editing in WorkspaceHeader & Inspector
- **Files**: `ui/src/components/workspace/WorkspaceHeader.tsx`, `ui/src/components/workspace/WorkspaceInspector.tsx`
- **Cynefin**: Complicated
- **Action**:
  1. In `WorkspaceHeader.tsx`: Use `useOpsControl()`. Manage editing state (`isEditing`, `draftTitle`).
  2. Display pencil icon next to title.
  3. On click: enter edit mode with focused input (`aria-label="Event Title"`).
  4. On Enter: Validate `draftTitle.trim()`. If non-empty and changed, call `PATCH /queue/{event_id}/title` and update optimistically. If empty/whitespace, cancel edit and revert to existing title.
  5. On Escape or Blur without changes: Exit edit mode.
  6. In `WorkspaceInspector.tsx`: Display Title row with badge indicating source (`User`, `AI`, `Fallback`).
- **Verification**: Vitest tests in `ui/src/components/workspace/__tests__/workspace-header.test.tsx`.

### Step 10: Event Title in Task List Items with Truncation
- **File**: `ui/src/components/workspace/WorkspaceTaskItem.tsx`
- **Cynefin**: Clear
- **Action**: In Row 1 (line 80), replace raw `evt.id` with fallback chain `{evt.title || evt.service || evt.id.slice(4, 12)}`. Maintain `evt.id` in tooltip or subtitle. Ensure container `truncate min-w-0 flex-1` smoothly truncates long titles.
- **Verification**: Vitest test in `ui/src/components/workspace/__tests__/workspace-task-item.test.tsx`.

---

## 5. Verification & Test Specification (Dave Farley 4-Layer ATDD Model)

### 5.1 Executable Scenarios & Test Specification Table

| ID | Scenario (Given/When/Then) | DSL Operation / Driver | SUT Target | Expected Output / Assertion | Category |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T-1** | **Given** a user posts a message via Chat<br>**When** the event is created<br>**Then** it immediately has `title_source="fallback"` and `title == text[:60]` | `create_chat_event()` | `src/routes/chat.py` | Event document has valid title string without awaiting LLM | Acceptance |
| **T-2** | **Given** an event with fallback title<br>**When** background LLM generates a 4-word title<br>**Then** Redis is updated to `title_source="llm"` and WS broadcasts `event_title_updated` | `run_background_namer()` | `src/agents/event_namer.py` | State updated; WS message sent with title and source="llm" | Integration |
| **T-3** | **Given** background LLM generation takes > 10.0 seconds<br>**When** timeout triggers<br>**Then** the fallback title remains intact and no exception is raised | `mock_slow_adapter(delay=15s)` | `src/agents/event_namer.py` | Function returns safely; event title remains fallback | Unit |
| **T-4** | **Given** an event where user renames before LLM completes (`title_source="user"`)<br>**When** LLM task completes and attempts write<br>**Then** `update_event_title_if_not_user` returns `False` and user title is preserved | `concurrent_rename_race()` | `src/state/blackboard.py` | Return value is `False`; `event.title` is user's title | Unit / Concurrency |
| **T-5** | **Given** an active event<br>**When** user sends `PATCH /queue/{event_id}/title` with valid title<br>**Then** returns 200 OK, sets `title_source="user"`, and broadcasts WS update | `http_patch_title()` | `src/routes/queue.py` | HTTP 200; `title_source == "user"`; WS broadcast triggered | Acceptance |
| **T-6** | **Given** `WorkspaceHeader` rendered with an event title<br>**When** user clicks title, enters new name, and presses Enter<br>**Then** PATCH is called, header updates optimistically, and input closes | `user_rename_header_ui()` | `WorkspaceHeader.tsx` | Fetch called with PATCH; header displays new title | UI Acceptance |
| **T-SEC-1** | **Given** an automated or unowned event (`source="aligner"`, `created_by_email=None`)<br>**When** regular user calls `PATCH /queue/{event_id}/title`<br>**Then** API returns 403 Forbidden | `http_patch_unowned_title()` | `src/routes/queue.py` | HTTP 403 Forbidden; audit log recorded | Security / Auth |
| **T-SEC-2** | **Given** an active event owned by user A<br>**When** user B calls `PATCH /queue/{event_id}/title`<br>**Then** API returns 403 Forbidden | `http_patch_other_user_title()` | `src/routes/queue.py` | HTTP 403 Forbidden | Security / Auth |
| **T-SEC-3** | **Given** an active event<br>**When** user calls `PATCH /queue/{event_id}/title` with `"   "` (whitespace only)<br>**Then** API returns 422 Unprocessable Entity | `http_patch_whitespace_title()` | `src/routes/queue.py` | HTTP 422 with validation error message | Security / Validation |
| **T-SEC-4** | **Given** an event title containing `<script>alert(1)</script>`<br>**When** rendered via `src/utils/event_markdown.py`<br>**Then** the title is HTML-escaped and does not execute | `render_event_markdown()` | `src/utils/event_markdown.py` | Markdown output contains `&lt;script&gt;` | Security / Stored XSS |
| **T-SEC-5** | **Given** a user prompt containing prompt injection commands<br>**When** background LLM event namer executes<br>**Then** prompt is sanitized with `<user_request>` tags and produces a concise title without leaking system instructions | `test_prompt_injection_naming()` | `src/agents/event_namer.py` | Generated title is clean and $\le 100$ characters | Security / AI Safety |
| **T-SEC-6** | **Given** a closed event<br>**When** user calls `PATCH /queue/{event_id}/title`<br>**Then** API returns 409 Conflict | `http_patch_closed_title()` | `src/routes/queue.py` | HTTP 409 Conflict | State Machine |

---

## 6. Evidence Coverage Gate

- [x] Every file identified during exploration maps to $\ge 1$ atomic step with verified repo-relative paths.
- [x] Zero `file:///` URLs or developer home paths in plan document.
- [x] Concurrency race condition (TOCTOU) addressed with formal atomic transaction, key-miss guard, and unwatch safety.
- [x] Hexagonal broadcast port decoupling: All title updates route through `brain.broadcast(...)`.
- [x] Fail-open LLM isolation with strong task references guarantees zero degradation on event ingestion latency.
- [x] Security threat model addressed: unowned event IDOR guard, stored XSS escaping, whitespace validation, and idempotency short-circuit.
- [x] Real-time synchronization modeled across REST, WebSocket, UI, and Slack threads with error isolation.

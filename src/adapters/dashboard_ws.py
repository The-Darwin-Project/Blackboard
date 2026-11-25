# BlackBoard/src/adapters/dashboard_ws.py
# @ai-rules:
# 1. [Pattern]: Implements BroadcastPort via __call__ -- Brain calls await adapter(message).
# 2. [Constraint]: JWT auth uses auth.get_user_from_websocket (pure crypto, no network).
# 3. [Pattern]: connected_clients set managed here. broadcast fans out, removes disconnected.
# 4. [Constraint]: Brain and Blackboard injected via constructor. No app.state access.
# 5. [Pattern]: KargoObserver injected post-init via set_kargo_observer(). Null-guarded for KARGO_OBSERVER_ENABLED=false.
# 6. [Pattern]: Initial kargo_stages_update sent on every new WS connection. create_kargo_event delegates to Brain.
# 7. [Pattern]: _handle_chat passes user.email as created_by_email for multi-tenant event ownership, and seeds the first user turn via create_event(initial_turns=...) -- never a follow-up append_turn (evt-996e33ec).
# 8. [Pattern]: ArgoCDObserver injected post-init via set_argocd_observer(), same shape as Kargo. No UI
#    consumer sends argocd_health_update yet (v1 dead wire) -- no _send_initial_argocd_state needed.
# 9. [Pattern]: websocket_handler accepts() FIRST, then validates auth and closes with 4001 if rejected.
#    ASGI close() before accept() is treated as a rejected handshake -> browser gets HTTP 403 / code 1006, never 4001.
# 10. [Pattern]: _handle_user_message uses auth.can_append_message for ownership checks. Structured [Audit]
#     logs emitted at call site, not inside auth.py.
# 11. [Pattern]: WS error envelope schema: {"type": "error", "kind": "auth_rejected"|"rate_limited"|"invalid_payload"|"invalid_option"|"invalid_image"|"image_too_large"|"stale_approval"|"not_waiting"|"sha_drift"|"sha_unresolvable"|"closed"|"error", "event_id": str, "message": str}.
"""Dashboard WebSocket adapter -- manages UI client connections and broadcast."""
from __future__ import annotations

import inspect
import json
import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect

from ..auth import (
    can_append_message, can_approve_event, get_user_from_websocket, prompt_display_name,
    resolve_approval_identity,
)
from ..agents.event_namer import spawn_event_namer_task
from ..models import ConversationTurn, EventEvidence
from ..utils.prompt_sanitize import fallback_title
from ..utils.vcs_approval import check_approval_sha_drift, resolve_live_head_sha

if TYPE_CHECKING:
    from ..agents.brain import Brain
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)


class DashboardWSAdapter:
    """Dashboard WebSocket adapter.

    Manages UI client connections, handles incoming messages (chat, user_message,
    approve, emergency_stop), and implements BroadcastPort for outgoing messages.
    """

    def __init__(self, brain: Brain, blackboard: BlackboardState, auth_enabled: bool) -> None:
        self._brain = brain
        self._blackboard = blackboard
        self._auth_enabled = auth_enabled
        self._clients: set[WebSocket] = set()
        self._kargo_observer = None
        self._argocd_observer = None

    def set_kargo_observer(self, observer) -> None:
        """Inject KargoObserver after initialization (observer starts after adapter)."""
        self._kargo_observer = observer

    def set_argocd_observer(self, observer) -> None:
        """Inject ArgoCDObserver after initialization (observer starts after adapter)."""
        self._argocd_observer = observer

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def __call__(self, message: dict) -> None:
        """BroadcastPort implementation -- fan out to all connected UI clients."""
        if not self._clients:
            return
        data = json.dumps(message)
        disconnected: set[WebSocket] = set()
        for client in self._clients:
            try:
                await client.send_text(data)
            except Exception:
                disconnected.add(client)
        self._clients.difference_update(disconnected)

    async def websocket_handler(self, websocket: WebSocket) -> None:
        """Handle a single Dashboard WebSocket lifecycle.

        Accept the connection FIRST so that close(4001) transmits a real
        WS Close Frame -- ASGI close() before accept() is treated as a
        rejected handshake (browser gets HTTP 403 / code 1006, never 4001).
        """
        await websocket.accept()

        try:
            user = get_user_from_websocket(websocket)
        except Exception as e:
            logger.error("WebSocket user extraction failed: %s", e)
            await websocket.close(code=1011)
            return

        if self._auth_enabled and user.user_id == "anonymous":
            logger.warning("[Audit] WS auth rejected: anonymous user")
            try:
                await websocket.close(code=4001)
            except (WebSocketDisconnect, RuntimeError):
                pass
            return

        self._clients.add(websocket)
        logger.info("UI WebSocket connected (%d clients) user=%s", len(self._clients), user.label)

        await self._send_initial_kargo_state(websocket)

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "chat":
                    await self._handle_chat(websocket, data, user)
                elif msg_type == "user_message":
                    await self._handle_user_message(websocket, data, user)
                elif msg_type == "approve":
                    await self._handle_approve(websocket, data, user)
                elif msg_type == "approval_decision":
                    await self._handle_approval_decision(websocket, data, user)
                elif msg_type == "emergency_stop":
                    await self._handle_emergency_stop(websocket)
                elif msg_type == "create_kargo_event":
                    await self._handle_create_kargo_event(websocket, data)

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error("WebSocket error: %s", e)
        finally:
            self._clients.discard(websocket)
            logger.info("UI WebSocket disconnected (%d clients)", len(self._clients))

    async def _handle_chat(self, ws: WebSocket, data: dict, user) -> None:
        raw_msg = data.get("message")
        message = raw_msg if isinstance(raw_msg, str) else str(raw_msg or "")
        service = data.get("service", "general")
        display_label = (
            user.label.split("@")[0]
            if getattr(user, "label", None) and user.label != "anonymous"
            else user.source
        )
        image = data.get("image")
        image_rejected = bool(image and len(image) > 1_400_000)
        if image_rejected:
            image = None
        # Seed the first user turn WITH the event (create_event persists it before LPUSH)
        # so the Brain can never pop a blank chat event (evt-996e33ec).
        user_turn = ConversationTurn(
            turn=1,
            actor="user",
            action="message",
            thoughts=message,
            image=image,
            user_name=prompt_display_name(user),
        )
        fallback = fallback_title(message)
        event_id = await self._blackboard.create_event(
            source="chat",
            service=service,
            reason=message,
            evidence=EventEvidence(
                display_text=message,
                source_type="chat",
                triggered_by=prompt_display_name(user) or display_label,
                domain="disorder",
                severity="info",
            ),
            created_by_email=user.email,
            initial_turns=[user_turn],
            title=fallback,
            title_source="fallback",
        )
        try:
            spawn_event_namer_task(self._blackboard, self._brain, event_id, message, "chat")
        except Exception as e:
            logger.warning("Failed to spawn event namer task for %s: %s", event_id, e)
        if image_rejected:
            await ws.send_json({
                "type": "error", "kind": "invalid_payload",
                "event_id": event_id, "message": "Image too large (max 1MB). Image was not attached.",
            })
        await ws.send_json({
            "type": "event_created",
            "event_id": event_id,
            "service": service,
            "reason": message,
        })
        logger.info("WS chat event created: %s", event_id)

    async def _handle_user_message(self, ws: WebSocket, data: dict, user) -> None:
        event_id = data.get("event_id", "")
        message = data.get("message", "")
        image = data.get("image")
        if image and len(image) > 1_400_000:
            await ws.send_json({
                "type": "error", "kind": "invalid_payload",
                "event_id": event_id, "message": "Image too large (max 1MB). Image was not attached.",
            })
            image = None
        if not event_id or not message:
            return
        event = await self._blackboard.get_event(event_id)
        if not event:
            await ws.send_json({
                "type": "error", "kind": "not_found",
                "event_id": event_id, "message": f"Event {event_id} not found",
            })
            return
        if not can_append_message(event.created_by_email, user.email, auth_enabled=self._auth_enabled):
            logger.warning(
                "[Audit] Denied WS append: event_id=%s caller_email=%s owner_email=%s",
                event_id, user.email, event.created_by_email,
            )
            await ws.send_json({
                "type": "error", "kind": "auth_rejected",
                "event_id": event_id, "message": "Not authorized to post to this event",
            })
            return
        logger.info(
            "[Audit] Allowed WS append: event_id=%s caller_email=%s owner_email=%s",
            event_id, user.email, event.created_by_email,
        )
        turn = ConversationTurn(
            turn=len(event.conversation) + 1,
            actor="user",
            action="message",
            thoughts=message,
            image=image,
            user_name=prompt_display_name(user),
        )
        await self._blackboard.append_turn(event_id, turn)
        self._brain.clear_waiting(event_id)
        await self._brain.resume_if_parked(event_id)
        self._brain.enqueue_for_processing(event_id)
        await ws.send_json({
            "type": "turn",
            "event_id": event_id,
            "turn": turn.model_dump(),
        })
        logger.info("WS user message added to event: %s", event_id)

    async def _handle_approve(self, ws: WebSocket, data: dict, user) -> None:
        event_id = data.get("event_id", "")
        if not event_id:
            return
        event = await self._blackboard.get_event(event_id)
        if not event:
            return

        raw_expected = data.get("expected_sha")
        expected_sha = raw_expected if isinstance(raw_expected, str) else None
        if getattr(event, "pending_approval", None) is not None:
            from ..routes.approval_decision import execute_approval_decision
            from ..routes.approval_decision_helpers import DecisionRequest

            outcome = await execute_approval_decision(
                blackboard=self._blackboard,
                brain=self._brain,
                event_id=event_id,
                user=user,
                auth_enabled=self._auth_enabled,
                req=DecisionRequest(expected_sha=expected_sha),
                legacy_mode="approve",
                source="dashboard",
                head_sha_resolver=resolve_live_head_sha,
            )
            if outcome.kind != "ok":
                kind = "auth_rejected" if outcome.kind in ("unauthenticated", "forbidden") else outcome.kind
                payload: dict = {
                    "type": "error",
                    "kind": kind,
                    "event_id": event_id,
                    "message": outcome.message,
                }
                if outcome.expected_sha is not None:
                    payload["approval_requested_sha"] = outcome.expected_sha
                if outcome.actual_sha is not None:
                    payload["live_sha"] = outcome.actual_sha
                await ws.send_json(payload)
                return
            if ws not in self._clients and outcome.turn is not None:
                await ws.send_json({
                    "type": "turn",
                    "event_id": event_id,
                    "turn": outcome.turn.model_dump(),
                })
            return

        if not can_approve_event(user, event, auth_enabled=self._auth_enabled):
            logger.warning(
                "WS approval rejected for event %s by user %s (roles=%s)",
                event_id, getattr(user, "email", user.label), getattr(user, "roles", []),
            )
            await ws.send_json({
                "type": "error",
                "kind": "auth_rejected",
                "event_id": event_id,
                "message": "Forbidden: User not authorized to approve this event",
            })
            return

        try:
            mr_id, mr_sha = await resolve_live_head_sha(event)
        except Exception as exc:
            logger.warning("WS _handle_approve: resolve_live_head_sha failed for %s (%s)", event_id, type(exc).__name__)
            mr_id, mr_sha = None, None
        fresh_event = await self._blackboard.get_event(event_id)
        if not fresh_event:
            return
        raw_expected = data.get("expected_sha")
        expected_sha = raw_expected if isinstance(raw_expected, str) else None
        drift = check_approval_sha_drift(fresh_event, mr_sha, expected_sha=expected_sha)
        if not drift.allowed:
            await ws.send_json({
                "type": "error",
                "kind": drift.code,
                "event_id": event_id,
                "approval_requested_sha": drift.approval_requested_sha,
                "live_sha": drift.live_sha,
                "message": drift.detail,
            })
            return

        clean_by, clean_name = resolve_approval_identity(
            getattr(user, "email", None), getattr(user, "label", None)
        )
        raw_fresh_req = getattr(fresh_event, "approval_requested_sha", None)
        fresh_req_sha = raw_fresh_req if isinstance(raw_fresh_req, str) else None

        stamp_res = self._blackboard.stamp_event(
            event_id,
            _expected_requested_sha=fresh_req_sha,
            approved_by=clean_by,
            approved_mr_id=mr_id,
            approved_mr_sha=mr_sha,
            approval_requested_sha=None,
        )
        stamped = await stamp_res if inspect.isawaitable(stamp_res) else stamp_res
        if stamped is False:
            await ws.send_json({
                "type": "error",
                "kind": "closed",
                "event_id": event_id,
                "approval_requested_sha": fresh_req_sha,
                "live_sha": mr_sha,
                "message": "Event state changed concurrently; please refresh and retry.",
            })
            return

        thought_msg = "User approved the plan."
        if mr_id and mr_sha:
            thought_msg = f"User approved plan for MR/PR !{mr_id} at HEAD {mr_sha[:8]}."

        turn = ConversationTurn(
            turn=len(fresh_event.conversation) + 1,
            actor="user",
            action="approve",
            thoughts=thought_msg,
            user_name=clean_name,
            approved_by=clean_by,
            approved_mr_id=mr_id,
            approved_mr_sha=mr_sha,
        )
        await self._blackboard.append_turn(event_id, turn)
        self._brain.clear_waiting(event_id)
        await self._brain.resume_if_parked(event_id)
        self._brain.enqueue_for_processing(event_id)
        await ws.send_json({
            "type": "turn",
            "event_id": event_id,
            "turn": turn.model_dump(),
        })
        logger.info("WS approval for event: %s by %s (mr_id=%s, sha=%s)", event_id, user.label, mr_id, mr_sha)

    async def _handle_approval_decision(self, ws: WebSocket, data: dict, user) -> None:
        event_id = data.get("event_id", "")
        if not event_id:
            return
        from pydantic import ValidationError
        from ..routes.approval_decision import execute_approval_decision
        from ..routes.approval_decision_helpers import DecisionRequest

        try:
            req = DecisionRequest(
                approval_id=data.get("approval_id"),
                option_id=str(data.get("option_id") or ""),
                message=data.get("message"),
                write_in_text=data.get("write_in_text"),
                image=data.get("image"),
                reject_reason=data.get("reject_reason"),
                expected_sha=data.get("expected_sha"),
            )
            outcome = await execute_approval_decision(
                blackboard=self._blackboard,
                brain=self._brain,
                event_id=event_id,
                user=user,
                auth_enabled=self._auth_enabled,
                req=req,
                source="dashboard",
                head_sha_resolver=None,
            )
            if outcome.kind != "ok":
                kind = outcome.kind
                if kind in ("unauthenticated", "forbidden"):
                    kind = "auth_rejected"
                payload = {
                    "type": "error",
                    "kind": kind,
                    "event_id": event_id,
                    "message": outcome.message,
                }
                if outcome.expected_sha is not None:
                    payload["approval_requested_sha"] = outcome.expected_sha
                if outcome.actual_sha is not None:
                    payload["live_sha"] = outcome.actual_sha
                if kind == "sha_drift":
                    if req.option_id:
                        payload["option_id"] = req.option_id
                    if req.approval_id:
                        payload["approval_id"] = req.approval_id
                await ws.send_json(payload)
                return
            if ws not in self._clients and outcome.turn is not None:
                await ws.send_json({
                    "type": "turn",
                    "event_id": event_id,
                    "turn": outcome.turn.model_dump(),
                })
        except ValidationError as exc:
            logger.warning("WS approval_decision validation error on %s: %s", event_id, exc)
            await ws.send_json({
                "type": "error",
                "kind": "invalid_option",
                "event_id": event_id,
                "message": "Invalid approval decision payload",
            })
        except Exception as exc:
            logger.exception("WS approval_decision failed on %s: %s", event_id, exc)
            await ws.send_json({
                "type": "error",
                "kind": "internal_error",
                "event_id": event_id,
                "message": "Internal error processing approval decision",
            })

    async def _handle_emergency_stop(self, ws: WebSocket) -> None:
        cancelled = await self._brain.emergency_stop()
        await ws.send_json({
            "type": "emergency_stop_ack",
            "cancelled": cancelled,
        })
        logger.critical("WS emergency stop: %d tasks cancelled", cancelled)

    async def _handle_create_kargo_event(self, ws: WebSocket, data: dict) -> None:
        project = data.get("project", "")
        stage = data.get("stage", "")
        directive = data.get("directive", "")
        if not project or not stage:
            await ws.send_json({"type": "kargo_event_result", "status": "error", "detail": "Missing project or stage"})
            return
        try:
            result = await self._brain.create_kargo_event(project, stage, directive=directive)
            await ws.send_json({"type": "kargo_event_result", **result})
        except Exception as e:
            logger.error("create_kargo_event WS handler error: %s", e)
            await ws.send_json({"type": "kargo_event_result", "status": "error", "detail": str(e)})

    async def _send_initial_kargo_state(self, ws: WebSocket) -> None:
        """Send current Kargo failed stages snapshot on new WS connection."""
        stages = self._kargo_observer.get_failed_stages() if self._kargo_observer else []
        try:
            await ws.send_json({"type": "kargo_stages_update", "stages": stages})
        except Exception as e:
            logger.error("Failed to send initial kargo state: %s", e)

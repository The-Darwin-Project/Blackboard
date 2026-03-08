# BlackBoard/src/adapters/dashboard_ws.py
# @ai-rules:
# 1. [Pattern]: Implements BroadcastPort via __call__ -- Brain calls await adapter(message).
# 2. [Constraint]: JWT auth uses auth.get_user_from_websocket (pure crypto, no network).
# 3. [Pattern]: connected_clients set managed here. broadcast fans out, removes disconnected.
# 4. [Constraint]: Brain and Blackboard injected via constructor. No app.state access.
"""Dashboard WebSocket adapter -- manages UI client connections and broadcast."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect

from ..auth import get_user_from_websocket
from ..models import ConversationTurn, EventEvidence

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
        """Handle a single Dashboard WebSocket lifecycle."""
        user = get_user_from_websocket(websocket)
        if self._auth_enabled and user.user_id == "anonymous":
            await websocket.close(code=4001)
            return
        await websocket.accept()

        self._clients.add(websocket)
        logger.info("UI WebSocket connected (%d clients) user=%s", len(self._clients), user.label)

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
                elif msg_type == "emergency_stop":
                    await self._handle_emergency_stop(websocket)

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error("WebSocket error: %s", e)
        finally:
            self._clients.discard(websocket)
            logger.info("UI WebSocket disconnected (%d clients)", len(self._clients))

    async def _handle_chat(self, ws: WebSocket, data: dict, user) -> None:
        message = data.get("message", "")
        service = data.get("service", "general")
        event_id = await self._blackboard.create_event(
            source="chat",
            service=service,
            reason=message,
            evidence=EventEvidence(
                display_text=message,
                source_type="chat",
                triggered_by="dashboard",
                domain="complicated",
                severity="info",
            ),
        )
        image = data.get("image")
        if image and len(image) > 1_400_000:
            await ws.send_json({"type": "error", "message": "Image too large (max 1MB). Image was not attached."})
            image = None
        user_turn = ConversationTurn(
            turn=1,
            actor="user",
            action="message",
            thoughts=message,
            image=image,
            user_name=user.label if user.label != "anonymous" else None,
        )
        await self._blackboard.append_turn(event_id, user_turn)
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
            await ws.send_json({"type": "error", "message": "Image too large (max 1MB). Image was not attached."})
            image = None
        if not event_id or not message:
            return
        event = await self._blackboard.get_event(event_id)
        if not event:
            return
        turn = ConversationTurn(
            turn=len(event.conversation) + 1,
            actor="user",
            action="message",
            thoughts=message,
            image=image,
            user_name=user.label if user.label != "anonymous" else None,
        )
        await self._blackboard.append_turn(event_id, turn)
        self._brain.clear_waiting(event_id)
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
        turn = ConversationTurn(
            turn=len(event.conversation) + 1,
            actor="user",
            action="approve",
            thoughts="User approved the plan.",
            user_name=user.label if user.label != "anonymous" else None,
        )
        await self._blackboard.append_turn(event_id, turn)
        self._brain.clear_waiting(event_id)
        await ws.send_json({
            "type": "turn",
            "event_id": event_id,
            "turn": turn.model_dump(),
        })
        logger.info("WS approval for event: %s", event_id)

    async def _handle_emergency_stop(self, ws: WebSocket) -> None:
        cancelled = await self._brain.emergency_stop()
        await ws.send_json({
            "type": "emergency_stop_ack",
            "cancelled": cancelled,
        })
        logger.critical("WS emergency stop: %d tasks cancelled", cancelled)

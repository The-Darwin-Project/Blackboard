# BlackBoard/src/agents/base_client.py
# @ai-rules:
# 1. [Pattern]: process() serialized via _lock. _process_inner() does the actual WS send/recv.
# 2. [Pattern]: CancelledError in WS recv loop triggers finally -> WS close -> sidecar SIGTERM chain.
# 3. [Gotcha]: busy retry loop re-sends the task. Max 5 retries with exponential backoff (5s-60s).
# 4. [Constraint]: Security check on prompt before sending. FORBIDDEN_PATTERNS from security.py.
# 5. [Pattern]: connect() retries 5 times with exponential backoff (1-16s). _ensure_connected() pings first.
# 6. [Pattern]: process() accepts optional session_id for CLI --resume. Returns tuple[str, Optional[str]] = (result, session_id).
# 7. [Pattern]: followup() sends a follow-up message to an active/resumable session. Same recv loop as process().
"""
Base agent client -- shared WebSocket logic for all Darwin agent sidecars.

All agent clients (Architect, SysAdmin, Developer) are thin subclasses
that only set agent_name, sidecar_url_env, and cwd.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Callable, Optional

import websockets

from .security import FORBIDDEN_PATTERNS, SecurityError

logger = logging.getLogger(__name__)


class AgentClient:
    """WebSocket client to an agent CLI sidecar container (Gemini or Claude Code)."""

    def __init__(
        self,
        agent_name: str,
        sidecar_url_env: str,
        default_url: str,
        cwd: str,
    ):
        self.sidecar_url = os.getenv(sidecar_url_env, default_url)
        ws_base = self.sidecar_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_base}/ws"
        self.agent_name = agent_name
        self.cwd = cwd
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._busy_retries: dict[str, int] = {}
        self._active_sessions: dict[str, str] = {}  # event_id -> session_id (Phase 2)
        # Defense-in-depth lock: serializes process() calls on this agent instance.
        # Brain also holds per-agent locks (_agent_locks) to prevent concurrent dispatch.
        # This client lock ensures safety if the agent is used outside the Brain context
        # (e.g., direct testing, future multi-Brain scenarios).
        self._lock = asyncio.Lock()
        logger.info(f"{agent_name} client initialized (WS: {self.ws_url})")

    async def connect(self) -> None:
        """Establish persistent WebSocket connection with retry."""
        delays = [1, 2, 4, 8, 16]
        for attempt, delay in enumerate(delays, 1):
            try:
                self._ws = await websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                )
                self._connected = True
                logger.info(f"{self.agent_name} WebSocket connected to {self.ws_url}")
                return
            except Exception as e:
                logger.warning(f"{self.agent_name} WS connect attempt {attempt}/{len(delays)} failed: {e}")
                if attempt < len(delays):
                    await asyncio.sleep(delay)
        logger.error(f"{self.agent_name} WebSocket failed to connect after {len(delays)} attempts")

    async def close(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._connected = False
            logger.info(f"{self.agent_name} WebSocket closed")

    def cleanup_event(self, event_id: str) -> None:
        """Clean up per-event state. Called by Brain on event close/cancel."""
        self._active_sessions.pop(event_id, None)

    async def _ensure_connected(self) -> bool:
        """Reconnect if disconnected."""
        if self._ws and self._connected:
            try:
                await self._ws.ping()
                return True
            except Exception:
                self._connected = False
        await self.connect()
        return self._connected

    async def process(
        self,
        event_id: str,
        task: str,
        event_md_path: str = "",
        on_progress: Optional[Callable] = None,
        mode: str = "",
        session_id: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """
        Send task to sidecar via WebSocket, stream progress, return (result, session_id).

        When session_id is provided, the sidecar passes --resume to the CLI so
        the agent retains context from prior turns on this event.
        Returns (result, None) when sessions are unavailable.
        Serialized via asyncio.Lock to prevent concurrent WS recv conflicts.
        """
        async with self._lock:
            return await self._process_inner(event_id, task, event_md_path, on_progress, mode, session_id)

    async def _process_inner(
        self,
        event_id: str,
        task: str,
        event_md_path: str = "",
        on_progress: Optional[Callable] = None,
        mode: str = "",
        session_id: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Inner process logic (called under lock). Returns (result, session_id)."""
        # Build prompt
        if event_md_path:
            prompt = f"Read the event document at {event_md_path} and execute this task:\n\n{task}"
        else:
            prompt = task

        # Prepend mode context for CLI skill matching
        if mode:
            prompt = f"[Mode: {mode}] {prompt}"

        # Security check
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                msg = f"SECURITY BLOCK: Forbidden pattern: {pattern}"
                logger.error(msg)
                raise SecurityError(msg)

        # Ensure connected
        if not await self._ensure_connected():
            return f"Error: Cannot connect to {self.agent_name} sidecar WebSocket", None

        # Send task
        try:
            task_msg = {
                "type": "task",
                "event_id": event_id,
                "prompt": prompt,
                "cwd": self.cwd,
                "autoApprove": True,
            }
            if session_id:
                task_msg["session_id"] = session_id
            await self._ws.send(json.dumps(task_msg))
        except Exception as e:
            self._connected = False
            return f"Error: Failed to send task: {e}", None

        # Receive messages until result or error.
        # CancelledError propagates up to Brain.cancel_active_task().
        # Finally block ensures WS close -> sidecar SIGTERM chain fires.
        session_id: Optional[str] = None
        latest_callback_result: Optional[str] = None  # From sendResults partial_result
        try:
            async for raw_msg in self._ws:
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")

                if msg_type == "progress":
                    progress_text = msg.get("message", "")
                    source = msg.get("source", "")
                    log_prefix = "[agent_msg]" if source == "agent_message" else ""
                    logger.debug(f"{self.agent_name} progress {log_prefix}[{event_id}]: {progress_text[:100]}")
                    if on_progress:
                        await on_progress({
                            "actor": self.agent_name,
                            "event_id": event_id,
                            "message": progress_text,
                            "source": source,
                        })

                elif msg_type == "partial_result":
                    # sendResults callback -- store as latest deliverable
                    content = msg.get("content", "")
                    latest_callback_result = content
                    logger.info(f"{self.agent_name} callback result [{event_id}]: {len(content)} chars")
                    if on_progress:
                        await on_progress({
                            "actor": self.agent_name,
                            "event_id": event_id,
                            "message": f"[deliverable updated: {len(content)} chars]",
                            "source": "callback",
                        })

                elif msg_type == "result":
                    output = msg.get("output", "")
                    source = msg.get("source", "stdout")
                    if isinstance(output, dict):
                        output = json.dumps(output, indent=2)
                    # If we have a callback result and the WS result is a stdout fallback,
                    # prefer the callback (the agent's explicit deliverable)
                    if latest_callback_result and source == "stdout":
                        logger.info(f"{self.agent_name} [{event_id}]: preferring callback result over stdout fallback")
                        output = latest_callback_result
                    # Capture session_id if sidecar reports one (Phase 2)
                    session_id = msg.get("session_id") or session_id
                    if session_id:
                        self._active_sessions[event_id] = session_id
                    logger.info(f"{self.agent_name} completed [{event_id}]: {len(str(output))} chars (source={source})"
                                + (f" (session: {session_id})" if session_id else ""))
                    self._busy_retries.pop(event_id, None)
                    return str(output), session_id

                elif msg_type == "error":
                    error_msg = msg.get("message", "Unknown error")
                    logger.error(f"{self.agent_name} error [{event_id}]: {error_msg}")
                    self._busy_retries.pop(event_id, None)
                    return f"Error: {error_msg}", session_id

                elif msg_type == "busy":
                    retries = self._busy_retries.get(event_id, 0) + 1
                    self._busy_retries[event_id] = retries
                    if retries > 5:
                        self._busy_retries.pop(event_id, None)
                        return json.dumps({
                            "type": "agent_busy",
                            "agent": self.agent_name,
                            "event_id": event_id,
                            "message": f"{self.agent_name} busy after 5 retries. Returning to Brain for decision.",
                        }), None
                    delay = min(5 * (2 ** (retries - 1)), 60)
                    logger.warning(f"{self.agent_name} busy [{event_id}], retry {retries}/5 in {delay}s...")
                    await asyncio.sleep(delay)
                    try:
                        retry_msg = {
                            "type": "task",
                            "event_id": event_id,
                            "prompt": prompt,
                            "cwd": self.cwd,
                            "autoApprove": True,
                        }
                        if session_id:
                            retry_msg["session_id"] = session_id
                        await self._ws.send(json.dumps(retry_msg))
                    except Exception:
                        self._busy_retries.pop(event_id, None)
                        return json.dumps({
                            "type": "agent_busy",
                            "agent": self.agent_name,
                            "event_id": event_id,
                            "message": f"{self.agent_name} busy and retry send failed.",
                        }), None

                elif msg_type == "question":
                    return json.dumps({
                        "type": "question",
                        "message": msg.get("message", ""),
                        "requestingAgent": msg.get("requestingAgent", ""),
                    }), session_id

        except asyncio.CancelledError:
            logger.info(f"{self.agent_name} task cancelled for {event_id}")
            raise
        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            return "Error: WebSocket connection closed during execution", session_id
        except Exception as e:
            return f"Error: {e}", session_id
        finally:
            # Close WS on any exit path -- triggers sidecar SIGTERM on the CLI process
            if self._ws and self._connected:
                try:
                    await self._ws.close()
                except Exception:
                    pass
                self._connected = False

        return "Error: No result received", None

    async def followup(
        self,
        event_id: str,
        session_id: str,
        message: str,
        on_progress: Optional[Callable] = None,
    ) -> str:
        """Send follow-up message to an active or resumable agent session.

        Used in Phase 2 to forward user messages to running agents
        instead of killing and re-spawning them.
        Serialized via the same _lock as process() to prevent WS conflicts.
        """
        async with self._lock:
            return await self._followup_inner(event_id, session_id, message, on_progress)

    async def _followup_inner(
        self,
        event_id: str,
        session_id: str,
        message: str,
        on_progress: Optional[Callable] = None,
    ) -> str:
        """Inner followup logic (called under lock)."""
        if not await self._ensure_connected():
            return "Error: Cannot connect to sidecar"

        try:
            await self._ws.send(json.dumps({
                "type": "followup",
                "event_id": event_id,
                "session_id": session_id,
                "message": message,
            }))
        except Exception as e:
            self._connected = False
            return f"Error: Failed to send followup: {e}"

        # Same receive loop as process() -- progress, result, error
        try:
            async for raw_msg in self._ws:
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")

                if msg_type == "progress":
                    if on_progress:
                        await on_progress({
                            "actor": self.agent_name,
                            "event_id": event_id,
                            "message": msg.get("message", ""),
                        })
                elif msg_type == "result":
                    output = msg.get("output", "")
                    if isinstance(output, dict):
                        output = json.dumps(output, indent=2)
                    return str(output)
                elif msg_type == "error":
                    return f"Error: {msg.get('message', 'Unknown error')}"
        except asyncio.CancelledError:
            logger.info(f"{self.agent_name} followup cancelled for {event_id}")
            raise
        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            return "Error: WebSocket connection closed during followup"
        finally:
            if self._ws and self._connected:
                try:
                    await self._ws.close()
                except Exception:
                    pass
                self._connected = False

        return "Error: No followup result received"

    async def health(self) -> bool:
        """Check sidecar health via HTTP (K8s probes use HTTP)."""
        import httpx
        try:
            url = f"{self.sidecar_url}/health"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False

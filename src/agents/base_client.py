# BlackBoard/src/agents/base_client.py
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
    """WebSocket client to a Gemini CLI sidecar container."""

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
    ) -> str:
        """
        Send task to sidecar via WebSocket, stream progress, return result.

        Serialized via asyncio.Lock to prevent concurrent WS recv conflicts.
        """
        async with self._lock:
            return await self._process_inner(event_id, task, event_md_path, on_progress)

    async def _process_inner(
        self,
        event_id: str,
        task: str,
        event_md_path: str = "",
        on_progress: Optional[Callable] = None,
    ) -> str:
        """Inner process logic (called under lock)."""
        # Build prompt
        if event_md_path:
            prompt = f"Read the event document at {event_md_path} and execute this task:\n\n{task}"
        else:
            prompt = task

        # Security check
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                msg = f"SECURITY BLOCK: Forbidden pattern: {pattern}"
                logger.error(msg)
                raise SecurityError(msg)

        # Ensure connected
        if not await self._ensure_connected():
            return f"Error: Cannot connect to {self.agent_name} sidecar WebSocket"

        # Send task
        try:
            await self._ws.send(json.dumps({
                "type": "task",
                "event_id": event_id,
                "prompt": prompt,
                "cwd": self.cwd,
                "autoApprove": True,
            }))
        except Exception as e:
            self._connected = False
            return f"Error: Failed to send task: {e}"

        # Receive messages until result or error
        try:
            async for raw_msg in self._ws:
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")

                if msg_type == "progress":
                    progress_text = msg.get("message", "")
                    logger.debug(f"{self.agent_name} progress [{event_id}]: {progress_text[:100]}")
                    if on_progress:
                        await on_progress({
                            "actor": self.agent_name,
                            "event_id": event_id,
                            "message": progress_text,
                        })

                elif msg_type == "result":
                    output = msg.get("output", "")
                    if isinstance(output, dict):
                        output = json.dumps(output, indent=2)
                    logger.info(f"{self.agent_name} completed [{event_id}]: {len(str(output))} chars")
                    self._busy_retries.pop(event_id, None)
                    return str(output)

                elif msg_type == "error":
                    error_msg = msg.get("message", "Unknown error")
                    logger.error(f"{self.agent_name} error [{event_id}]: {error_msg}")
                    self._busy_retries.pop(event_id, None)
                    return f"Error: {error_msg}"

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
                        })
                    delay = min(5 * (2 ** (retries - 1)), 60)
                    logger.warning(f"{self.agent_name} busy [{event_id}], retry {retries}/5 in {delay}s...")
                    await asyncio.sleep(delay)
                    try:
                        await self._ws.send(json.dumps({
                            "type": "task",
                            "event_id": event_id,
                            "prompt": prompt,
                            "cwd": self.cwd,
                            "autoApprove": True,
                        }))
                    except Exception:
                        self._busy_retries.pop(event_id, None)
                        return json.dumps({
                            "type": "agent_busy",
                            "agent": self.agent_name,
                            "event_id": event_id,
                            "message": f"{self.agent_name} busy and retry send failed.",
                        })

                elif msg_type == "question":
                    return json.dumps({
                        "type": "question",
                        "message": msg.get("message", ""),
                        "requestingAgent": msg.get("requestingAgent", ""),
                    })

        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            return "Error: WebSocket connection closed during execution"
        except Exception as e:
            return f"Error: {e}"

        return "Error: No result received"

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

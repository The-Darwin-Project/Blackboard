# BlackBoard/src/agents/architect.py
"""
Agent 2: The Architect - WebSocket client to Architect sidecar.

Persistent WebSocket connection for real-time bidirectional communication.
Streams progress from Gemini CLI execution back to Brain for UI broadcast.
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


class Architect:
    """WebSocket client to the Architect Gemini CLI sidecar."""

    def __init__(self):
        self.sidecar_url = os.getenv("ARCHITECT_SIDECAR_URL", "http://localhost:9091")
        # Convert http:// to ws:// for WebSocket
        ws_base = self.sidecar_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_base}/ws"
        self.agent_name = "architect"
        self.cwd = "/data/gitops-architect"
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        logger.info(f"Architect client initialized (WS: {self.ws_url})")

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
                logger.info(f"Architect WebSocket connected to {self.ws_url}")
                return
            except Exception as e:
                logger.warning(f"Architect WS connect attempt {attempt}/{len(delays)} failed: {e}")
                if attempt < len(delays):
                    await asyncio.sleep(delay)
        logger.error(f"Architect WebSocket failed to connect after {len(delays)} attempts")

    async def close(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._connected = False
            logger.info("Architect WebSocket closed")

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

        Args:
            event_id: Event ID for tracking
            task: Task instruction
            event_md_path: Path to event MD file on shared volume
            on_progress: Async callback for progress messages

        Returns:
            Result output string, or error message
        """
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
            return "Error: Cannot connect to Architect sidecar WebSocket"

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
                    logger.debug(f"Architect progress [{event_id}]: {progress_text[:100]}")
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
                    logger.info(f"Architect completed [{event_id}]: {len(str(output))} chars")
                    return str(output)

                elif msg_type == "error":
                    error_msg = msg.get("message", "Unknown error")
                    logger.error(f"Architect error [{event_id}]: {error_msg}")
                    return f"Error: {error_msg}"

                elif msg_type == "busy":
                    # Backoff retry: 5 attempts with exponential delay
                    if not hasattr(self, '_busy_retries'):
                        self._busy_retries = {}
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
                    delay = min(5 * (2 ** (retries - 1)), 60)  # 5, 10, 20, 40, 60s
                    logger.warning(f"Architect busy [{event_id}], retry {retries}/5 in {delay}s...")
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
                    # Agent asking for help from another agent
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

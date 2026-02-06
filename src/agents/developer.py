# BlackBoard/src/agents/developer.py
"""
Agent 4: The Developer (The Coder) - HTTP client to Developer sidecar.

Thin HTTP client that sends tasks to the Developer Gemini CLI sidecar.
The Developer implements source code changes based on Architect plans.

AIR GAP NOTE:
- This module does NOT import vertexai
- All AI reasoning happens in the Gemini CLI sidecar
- Security patterns applied before every prompt via safe_execution
"""
from __future__ import annotations

import logging
import os
import re

import httpx

from .security import FORBIDDEN_PATTERNS, SecurityError

logger = logging.getLogger(__name__)


class Developer:
    """
    Developer agent HTTP client.
    
    Sends tasks to the Developer Gemini CLI sidecar at :9093.
    The sidecar handles git operations, code changes, and pushes.
    """

    def __init__(self):
        self.sidecar_url = os.getenv("DEVELOPER_SIDECAR_URL", "http://localhost:9093")
        self.timeout = 310.0  # 5min + 10s buffer
        logger.info(f"Developer agent client initialized: {self.sidecar_url}")

    async def process(
        self,
        event_id: str,
        task: str,
        event_md_path: str = "",
    ) -> str:
        """
        Send a task to the Developer sidecar for execution.
        
        Args:
            event_id: Event ID for context
            task: Task instruction from Brain
            event_md_path: Path to event MD file on shared volume
            
        Returns:
            Response text from sidecar, or error message
        """
        prompt = f"Read the event document at {event_md_path} and execute this task:\n\n{task}"

        # Security check before sending to sidecar
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                msg = f"SECURITY BLOCK: Forbidden pattern in Developer prompt: {pattern}"
                logger.error(msg)
                raise SecurityError(msg)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.sidecar_url}/execute",
                    json={
                        "prompt": prompt,
                        "autoApprove": True,
                        "cwd": "/data/gitops-developer",
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    output = result.get("output", result.get("stdout", ""))
                    if isinstance(output, dict):
                        output = str(output)
                    logger.info(f"Developer completed task for event {event_id}: {len(str(output))} chars")
                    return str(output)
                else:
                    msg = f"Developer sidecar error: {response.status_code}"
                    logger.warning(msg)
                    return msg

        except httpx.ConnectError:
            msg = f"Cannot connect to Developer sidecar at {self.sidecar_url}"
            logger.warning(msg)
            return msg
        except Exception as e:
            msg = f"Developer execution error: {e}"
            logger.error(msg)
            return msg

    async def health(self) -> bool:
        """Check if Developer sidecar is healthy."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.sidecar_url}/health")
                return response.status_code == 200
        except Exception:
            return False

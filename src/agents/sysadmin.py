# BlackBoard/src/agents/sysadmin.py
"""
SysAdmin Agent - Thin HTTP client to the sysAdmin sidecar.

This module provides a thin HTTP client interface to the sysAdmin sidecar service.
It handles task execution requests and health checks via HTTP calls to the sidecar.
"""
from __future__ import annotations

import json
import logging
import os
import re

import httpx

from .security import FORBIDDEN_PATTERNS, SecurityError

logger = logging.getLogger(__name__)


class SysAdmin:
    """Thin HTTP client for the sysAdmin sidecar."""
    
    def __init__(self):
        self.sidecar_url = os.getenv("SYSADMIN_SIDECAR_URL", "http://localhost:9092")
        self.timeout = 310.0
    
    async def process(self, event_id: str, task: str, event_md_path: str = "") -> str:
        """
        Process a task by sending it to the sysAdmin sidecar.
        
        Args:
            event_id: Identifier for the event (for logging/tracking)
            task: The task description to execute
            event_md_path: Optional path to event document to read before executing
        
        Returns:
            Output text from the sidecar execution
        
        Raises:
            SecurityError: If forbidden patterns are detected in the prompt
        """
        prompt = f"Read the event document at {event_md_path} and execute this task:\n\n{task}" if event_md_path else task
        
        # Run security check inline
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                logger.error(f"SECURITY BLOCK: Forbidden pattern detected: {pattern}")
                raise SecurityError(f"Blocked forbidden pattern: {pattern}")
        
        url = f"{self.sidecar_url}/execute"
        payload = {"prompt": prompt, "autoApprove": True, "cwd": "/data/gitops-sysadmin"}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Sending execution request to {url} for event {event_id}")
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    output = result.get("output", "")
                    if isinstance(output, dict):
                        output = json.dumps(output)
                    elif not isinstance(output, str):
                        output = str(output)
                    logger.info(f"Execution completed successfully for event {event_id}")
                    return output
                else:
                    error_msg = f"Sidecar returned status {response.status_code}: {response.text}"
                    logger.error(f"Execution failed for event {event_id}: {error_msg}")
                    return f"Error: {error_msg}"
        except httpx.TimeoutException:
            error_msg = f"Execution timed out after {self.timeout} seconds"
            logger.error(f"Timeout for event {event_id}: {error_msg}")
            return f"Error: {error_msg}"
        except httpx.ConnectError:
            error_msg = f"Cannot connect to sysAdmin sidecar at {self.sidecar_url}"
            logger.error(f"Connection error for event {event_id}: {error_msg}")
            return f"Error: {error_msg}"
        except SecurityError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Execution error for event {event_id}: {error_msg}")
            return f"Error: {error_msg}"
    
    async def health(self) -> bool:
        """Check the health of the sysAdmin sidecar."""
        url = f"{self.sidecar_url}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                is_healthy = response.status_code == 200
                if not is_healthy:
                    logger.warning(f"Health check failed: status {response.status_code}")
                return is_healthy
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False

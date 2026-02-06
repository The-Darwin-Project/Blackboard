# BlackBoard/src/agents/architect.py
"""
Thin HTTP client to the Architect sidecar.

This module provides a lightweight interface to communicate with the Architect
sidecar service via HTTP. The actual AI processing and decision-making happens
in the sidecar, not in this module.
"""
import httpx
import json
import logging
import os
import re

from ..agents.security import safe_execution, SecurityError

logger = logging.getLogger(__name__)

# Import forbidden patterns for inline security check
from ..agents.security import FORBIDDEN_PATTERNS


class Architect:
    """
    Thin HTTP client to the Architect sidecar.
    
    This class forwards requests to the Architect sidecar service,
    which handles all AI processing and decision-making.
    """
    
    def __init__(self):
        """Initialize the Architect HTTP client."""
        self.sidecar_url = os.getenv("ARCHITECT_SIDECAR_URL", "http://localhost:9091")
        self.timeout = 310.0
        logger.info(f"Architect client initialized with sidecar URL: {self.sidecar_url}")
    
    async def process(self, event_id: str, task: str, event_md_path: str = "") -> str:
        """
        Process a task by forwarding it to the Architect sidecar.
        
        Args:
            event_id: Event identifier
            task: Task description to execute
            event_md_path: Path to event markdown document
            
        Returns:
            Output text from the sidecar, or error message on failure
        """
        # Build prompt
        if event_md_path:
            prompt = f"Read the event document at {event_md_path} and execute this task:\n\n{task}"
        else:
            prompt = task
        
        # Run security check inline (not as decorator since this is async)
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                logger.error(f"SECURITY BLOCK: Forbidden pattern detected: {pattern}")
                return f"SecurityError: Blocked forbidden pattern: {pattern}"
        
        # Prepare request
        url = f"{self.sidecar_url}/execute"
        payload = {
            "prompt": prompt,
            "autoApprove": True,
            "cwd": "/data/gitops-architect"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                return result.get("output", result.get("text", str(result)))
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Architect sidecar at {self.sidecar_url}: {e}")
            return f"Error: Could not connect to Architect sidecar at {self.sidecar_url}"
        except httpx.TimeoutException:
            logger.error(f"Request to Architect sidecar timed out after {self.timeout}s")
            return f"Error: Request to Architect sidecar timed out after {self.timeout}s"
        except Exception as e:
            logger.error(f"Error calling Architect sidecar: {e}")
            return f"Error: {str(e)}"
    
    async def health(self) -> bool:
        """
        Check if the Architect sidecar is healthy.
        
        Returns:
            True if sidecar is healthy, False otherwise
        """
        url = f"{self.sidecar_url}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

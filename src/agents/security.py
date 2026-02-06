# BlackBoard/src/agents/security.py
"""Security patterns and safety decorators for agent execution."""

import functools
import logging
import re

logger = logging.getLogger(__name__)

# =============================================================================
# Safety Decorator
# =============================================================================

FORBIDDEN_PATTERNS = [
    r"rm\s+-rf",
    r"rm\s+-r\s+/",
    r"delete\s+volume",
    r"drop\s+database",
    r"drop\s+table",
    r"truncate\s+table",
    r"kubectl\s+delete\s+namespace",
    r"kubectl\s+delete\s+pv",
    r"--force\s+--grace-period=0",
    r"git\s+push\s+--force",
    r"git\s+push\s+-f",
    r">\s*/dev/sd",
    r"mkfs\.",
    r"dd\s+if=",
]


class SecurityError(Exception):
    """Raised when a forbidden operation is detected."""
    pass


def safe_execution(func):
    """
    Safety decorator that blocks dangerous operations.
    
    Scans the plan context for forbidden patterns before execution.
    """
    @functools.wraps(func)
    def wrapper(self, plan_context: str, *args, **kwargs):
        # Scan for forbidden patterns
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, plan_context, re.IGNORECASE):
                logger.error(f"SECURITY BLOCK: Forbidden pattern detected: {pattern}")
                raise SecurityError(f"Blocked forbidden pattern: {pattern}")
        
        return func(self, plan_context, *args, **kwargs)
    
    return wrapper

# BlackBoard/src/skill_reconciler/constants.py
# @ai-rules:
# 1. [Constraint]: Shared Redis key constants and port utilities for skill reconciler + loader. ZERO imports from Brain, agents, async, or redis.
# 2. [Pattern]: Single source of truth for darwin:skills:* key names and port sanitization.
"""Redis key constants and standalone port utilities for the skill hot-reload system and clients."""
from typing import Union

REDIS_KEY_VERSION = "darwin:skills:version"
REDIS_KEY_CORPUS = "darwin:skills:corpus"
REDIS_KEY_PHASE_CONFIG = "darwin:skills:phase_config"
REDIS_KEY_SYNC_STATE = "darwin:skills:sync_state"


def sanitize_redis_port(port: Union[int, str]) -> int:
    """
    Sanitize and validate Redis port value, stripping any protocol/host prefix.

    Handles both integer port strings ('6379') and Kubernetes service link
    injections ('tcp://10.96.0.1:6379'). Validates port is in 1-65535 range.
    """
    if isinstance(port, int):
        port_num = port
    else:
        port_str = str(port).strip()
        if "://" in port_str:
            port_str = port_str.split(":")[-1]
        try:
            port_num = int(port_str)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid Redis port '{port}': not a valid integer") from e

    if not (1 <= port_num <= 65535):
        raise ValueError(f"Invalid Redis port {port_num}: must be between 1 and 65535")
    return port_num

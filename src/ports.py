# BlackBoard/src/ports.py
# @ai-rules:
# 1. [Pattern]: Ports define interfaces consumed by the Brain core. Adapters implement them.
# 2. [Pattern]: BroadcastPort uses __call__ to preserve backward compatibility with existing callbacks.
# 3. [Constraint]: No implementation logic in this file -- protocols only.
"""Hexagonal Architecture port definitions for the Darwin Brain."""
from __future__ import annotations

from typing import Protocol


class BroadcastPort(Protocol):
    """Port for broadcasting messages to external channels (Dashboard WS, Slack, etc.).

    Uses __call__ so existing bare-function callbacks (broadcast_to_ui, slack.broadcast_handler)
    satisfy the protocol without modification. Brain calls: await target(message)
    """

    async def __call__(self, message: dict) -> None: ...

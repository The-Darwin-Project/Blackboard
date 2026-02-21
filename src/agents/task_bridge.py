# BlackBoard/src/agents/task_bridge.py
# @ai-rules:
# 1. [Pattern]: One Queue per task_id. Created by dispatch coroutine, consumed by same coroutine, fed by /agent/ws handler.
# 2. [Pattern]: put_error injects _error_sentinel so dispatch coroutine unblocks on disconnect/cancel.
# 3. [Constraint]: No lock needed -- single asyncio event loop. put_nowait is safe.
# 4. [Constraint]: Pure infrastructure. No LLM logic, no routing decisions.
"""
TaskBridge -- per-task asyncio.Queue registry.

Bridges the /agent/ws WebSocket handler (producer) to Brain dispatch
coroutines (consumer). Each active task gets its own Queue so streamed
sidecar messages reach the correct dispatch coroutine.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

ERROR_SENTINEL_TYPE = "_error_sentinel"


class TaskBridge:
    """Manages asyncio.Queue instances keyed by task_id."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}

    def create_queue(self, task_id: str) -> asyncio.Queue:
        """Create and register a new Queue for *task_id*."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[task_id] = queue
        logger.debug("TaskBridge: created queue for task_id=%s", task_id)
        return queue

    def put(self, task_id: str, message: dict) -> None:
        """Enqueue *message* for *task_id*. No-crash on unknown task_id."""
        queue = self._queues.get(task_id)
        if queue is None:
            logger.warning(
                "TaskBridge: message for unknown task_id=%s (race after cleanup?)",
                task_id,
            )
            return
        queue.put_nowait(message)
        logger.debug("TaskBridge: put message type=%s for task_id=%s", message.get("type"), task_id)

    def put_error(self, task_id: str, error_msg: str = "Agent disconnected") -> None:
        """Inject an error sentinel so the dispatch coroutine unblocks."""
        queue = self._queues.get(task_id)
        if queue is None:
            logger.debug("TaskBridge: put_error skipped -- task_id=%s already cleaned up", task_id)
            return
        queue.put_nowait({"type": ERROR_SENTINEL_TYPE, "message": error_msg})
        logger.debug("TaskBridge: injected error sentinel for task_id=%s", task_id)

    def delete_queue(self, task_id: str) -> None:
        """Remove the Queue for *task_id*. Idempotent."""
        removed = self._queues.pop(task_id, None)
        if removed is not None:
            logger.debug("TaskBridge: deleted queue for task_id=%s", task_id)

    def get_queue(self, task_id: str) -> asyncio.Queue | None:
        """Return the Queue for *task_id*, or None."""
        return self._queues.get(task_id)

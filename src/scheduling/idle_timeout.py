# src/scheduling/idle_timeout.py
# @ai-rules:
# 1. [Pattern]: Per-event asyncio.Task for warn->close flow. Dict tracks active timers.
# 2. [Constraint]: close_callback MUST re-check _waiting_for_user before closing (race guard).
# 3. [Pattern]: Restart recovery via periodic fallback scan (every 60s) for waiting events without timers.
# 4. [Gotcha]: cancel() must suppress CancelledError from the timer task.
"""
Idle timeout manager for chat/slack events.

Flow per event: sleep(warning_sec) -> warn_callback() -> sleep(close_sec) -> close_callback()
Race guard: close_callback re-checks wait state before closing (user may have responded).
Restart recovery: periodic scan detects waiting events without active timers.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class IdleTimeoutManager:
    """Manages per-event idle timeout timers for chat/slack events."""

    def __init__(
        self,
        warn_callback: Callable[[str], Awaitable[None]],
        close_callback: Callable[[str], Awaitable[None]],
    ) -> None:
        self._warn_callback = warn_callback
        self._close_callback = close_callback
        self._timers: dict[str, asyncio.Task] = {}
        self._warning_sec = int(os.getenv("IDLE_TIMEOUT_WARNING_SEC", "600"))
        self._close_sec = int(os.getenv("IDLE_TIMEOUT_CLOSE_SEC", "300"))

    def schedule(self, event_id: str) -> None:
        """Start or restart the idle timeout for an event."""
        self.cancel(event_id)
        self._timers[event_id] = asyncio.create_task(
            self._run_timer(event_id),
            name=f"idle-timeout-{event_id[:12]}",
        )
        logger.debug("Idle timeout scheduled for %s (%ds warn, %ds close)",
                      event_id, self._warning_sec, self._close_sec)

    def cancel(self, event_id: str) -> None:
        """Cancel any active idle timeout for an event."""
        task = self._timers.pop(event_id, None)
        if task and not task.done():
            task.cancel()
            logger.debug("Idle timeout cancelled for %s", event_id)

    def has_timer(self, event_id: str) -> bool:
        """Check if an event has an active timer."""
        task = self._timers.get(event_id)
        return task is not None and not task.done()

    def cancel_all(self) -> None:
        """Cancel all active timers (shutdown)."""
        for eid in list(self._timers):
            self.cancel(eid)

    async def _run_timer(self, event_id: str) -> None:
        """Warning -> close flow for a single event."""
        try:
            await asyncio.sleep(self._warning_sec)
            await self._warn_callback(event_id)
            await asyncio.sleep(self._close_sec)
            await self._close_callback(event_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Idle timeout error for %s: %s", event_id, e)
        finally:
            self._timers.pop(event_id, None)

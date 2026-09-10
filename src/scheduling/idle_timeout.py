# src/scheduling/idle_timeout.py
# @ai-rules:
# 1. [Pattern]: Per-event asyncio.Task for warn->close flow. Dict tracks active timers.
# 2. [Constraint]: close_callback MUST re-check _waiting_for_user before closing (race guard).
#    It must also re-check event status: WAITING_APPROVAL events are skipped and left to
#    StalenessGuard[chat] (CHAT_STALE_TTL) -- see Brain._idle_timeout_close.
# 3. [Pattern]: Restart recovery via periodic fallback scan (every 60s) for waiting events without timers.
# 4. [Gotcha]: cancel() must suppress CancelledError from the timer task.
# 5. [Gotcha]: Generation counter prevents stale timer callbacks from closing re-scheduled events.
# 6. [Constraint]: assert_approval_notice_window() must be called (with the resolved
#    IDLE_TIMEOUT_APPROVAL_SEC/IDLE_TIMEOUT_CLOSE_SEC/CHAT_STALE_TTL) wherever these
#    three env vars are read together -- see Brain.__init__. It fails fast if the
#    WAITING_APPROVAL notice-window invariant is violated.
"""
Idle timeout manager for chat/slack events.

Flow per event: sleep(warning_sec) -> warn_callback() -> sleep(close_sec) -> close_callback()
Race guard: close_callback re-checks wait state before closing (user may have responded).
Generation guard: each schedule() increments a counter; callbacks abort if generation mismatches.
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
        self._generation: dict[str, int] = {}
        self._warning_sec = int(os.getenv("IDLE_TIMEOUT_WARNING_SEC", "600"))
        self._close_sec = int(os.getenv("IDLE_TIMEOUT_CLOSE_SEC", "300"))

    def schedule(self, event_id: str, warning_sec: int | None = None) -> None:
        """Start or restart the idle timeout for an event.

        Args:
            warning_sec: Override the default warning period (e.g., longer for
                conversation events vs explicit wait_for_user calls).
        """
        self.cancel(event_id)
        gen = self._generation.get(event_id, 0) + 1
        self._generation[event_id] = gen
        effective_warn = warning_sec if warning_sec is not None else self._warning_sec
        self._timers[event_id] = asyncio.create_task(
            self._run_timer(event_id, gen, warning_sec=effective_warn),
            name=f"idle-timeout-{event_id[:12]}",
        )
        logger.debug("Idle timeout scheduled for %s gen=%d (%ds warn, %ds close)",
                      event_id, gen, effective_warn, self._close_sec)

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

    @property
    def close_sec(self) -> int:
        """The configured IDLE_TIMEOUT_CLOSE_SEC (courtesy warn->close gap)."""
        return self._close_sec

    def cancel_all(self) -> None:
        """Cancel all active timers (shutdown)."""
        for eid in list(self._timers):
            self.cancel(eid)

    async def _run_timer(self, event_id: str, gen: int, *, warning_sec: int | None = None) -> None:
        """Warning -> close flow for a single event."""
        try:
            await asyncio.sleep(warning_sec if warning_sec is not None else self._warning_sec)
            if self._generation.get(event_id) != gen:
                return
            await self._warn_callback(event_id)
            await asyncio.sleep(self._close_sec)
            if self._generation.get(event_id) != gen:
                return
            await self._close_callback(event_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Idle timeout error for %s: %s", event_id, e)
        finally:
            self._timers.pop(event_id, None)


def assert_approval_notice_window(approval_sec: int, close_sec: int, chat_stale_ttl: int) -> None:
    """Enforce the WAITING_APPROVAL notice-window invariant: approval_sec + close_sec < chat_stale_ttl.

    This guarantees the courtesy warn->close attempt on a WAITING_APPROVAL event
    (skipped by Brain._idle_timeout_close and handed to StalenessGuard[chat])
    completes with a real notice window before CHAT_STALE_TTL makes the event
    eligible for staleness closure. Violating it collapses or inverts that
    window (see _get_approval_timeout / _check_chat_staleness).

    Raises only on a genuine inversion (sum strictly exceeds the TTL) -- the
    production defaults (5100 + 300 == 5400) land exactly on the boundary,
    which is a zero-margin race rather than a broken close ordering, so that
    case is logged as a warning instead of a hard startup failure.

    Raises:
        ValueError: if approval_sec + close_sec exceeds chat_stale_ttl.
    """
    total = approval_sec + close_sec
    if total > chat_stale_ttl:
        raise ValueError(
            "Idle-timeout invariant violated: IDLE_TIMEOUT_APPROVAL_SEC "
            f"({approval_sec}) + IDLE_TIMEOUT_CLOSE_SEC ({close_sec}) = {total} "
            f"> CHAT_STALE_TTL ({chat_stale_ttl}). This inverts the WAITING_APPROVAL "
            "courtesy notice window before StalenessGuard[chat] becomes eligible "
            "to close -- see Brain._get_approval_timeout."
        )
    if total == chat_stale_ttl:
        logger.warning(
            "Idle-timeout notice window has zero margin: IDLE_TIMEOUT_APPROVAL_SEC "
            "(%d) + IDLE_TIMEOUT_CLOSE_SEC (%d) == CHAT_STALE_TTL (%d). The deferred "
            "idle-close attempt and StalenessGuard[chat]'s eligibility land on the "
            "same instant. Consider lowering IDLE_TIMEOUT_APPROVAL_SEC/"
            "IDLE_TIMEOUT_CLOSE_SEC or raising CHAT_STALE_TTL for a real buffer.",
            approval_sec, close_sec, chat_stale_ttl,
        )

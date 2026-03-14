# BlackBoard/src/observers/timekeeper.py
# @ai-rules:
# 1. [Pattern]: Follows KubernetesObserver pattern -- in-process daemon with start/stop lifecycle.
# 2. [Pattern]: Idle gate -- only fires when darwin:queue is empty (lowest priority source).
# 3. [Pattern]: ZPOPMIN atomic dequeue via blackboard.pop_due_schedule() prevents double-fire.
# 4. [Pattern]: One event per cycle -- break after fire, re-check queue on next iteration.
# 5. [Pattern]: YAML frontmatter output matches Headhunter Bot Instructions format.
"""
TimeKeeper Observer -- fires scheduled events when Brain queue is idle.

Polls Redis ZSET for due schedules, constructs YAML frontmatter plans
identical to Headhunter Bot Instructions, and feeds them into the
Brain queue via create_event().
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

TIMEKEEPER_ENABLED = os.getenv("TIMEKEEPER_ENABLED", "false").lower() == "true"
TIMEKEEPER_POLL_INTERVAL = int(os.getenv("TIMEKEEPER_POLL_INTERVAL", "30"))


class TimeKeeperObserver:
    """Fires scheduled events when the Brain queue is idle."""

    def __init__(
        self,
        blackboard: "BlackboardState",
        interval: int = TIMEKEEPER_POLL_INTERVAL,
    ):
        self.blackboard = blackboard
        self.interval = interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            logger.warning("TimeKeeperObserver already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("TimeKeeperObserver started (interval=%ds)", self.interval)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TimeKeeperObserver stopped")

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                queue_len = await self.blackboard.redis.llen("darwin:queue")
                if queue_len > 0:
                    logger.debug("TimeKeeper: queue has %d items, deferring", queue_len)
                    await asyncio.sleep(self.interval)
                    continue

                result = await self.blackboard.pop_due_schedule()
                if result is None:
                    await asyncio.sleep(self.interval)
                    continue

                sched_id, sched = result
                original_score = sched.fire_at

                try:
                    await self._fire(sched)
                except Exception:
                    logger.exception("TimeKeeper: fire failed for %s, requeuing", sched_id)
                    await self.blackboard.requeue_schedule(sched_id, original_score)
                    await asyncio.sleep(self.interval)
                    continue

                if sched.schedule_type == "recurring" and sched.cron:
                    from croniter import croniter
                    now = time.time()
                    cron = croniter(sched.cron, now)
                    next_at = cron.get_next(float)
                    await self.blackboard.advance_schedule(sched_id, next_at)
                    logger.info("TimeKeeper: advanced recurring %s -> next at %.0f", sched_id, next_at)
                else:
                    await self.blackboard.delete_schedule(sched_id, sched.created_by)
                    logger.info("TimeKeeper: one-shot %s consumed and deleted", sched_id)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("TimeKeeper poll error")

            await asyncio.sleep(self.interval)

    async def _fire(self, sched) -> None:
        """Construct evidence and create a Brain event from the schedule."""
        from ..models import EventEvidence

        context_lines = []
        if sched.repo_url:
            context_lines.append(f"Repository: {sched.repo_url}")
        if sched.mr_url:
            context_lines.append(f"MR: {sched.mr_url}")
        context_block = "\n".join(context_lines)
        if context_block:
            context_block += "\n"

        emails_str = ", ".join(sched.notify_emails) if sched.notify_emails else ""

        reason = (
            f"---\n"
            f'plan: "{sched.name}"\n'
            f"service: {sched.service or 'general'}\n"
            f"domain: {sched.domain.upper()}\n"
            f"risk: low\n"
            f"steps:\n"
            f"  - id: scheduled-task\n"
            f"    mode: execute\n"
            f"    summary: |\n"
            f"      {context_block}"
            f"      {sched.instructions}\n"
            f"    approval_mode: {sched.approval_mode}\n"
            f"    on_failure: {sched.on_failure}\n"
            f"    notify_emails: [{emails_str}]\n"
            f"    created_by: {sched.created_by}\n"
            f"status: pending\n"
            f"---"
        )

        evidence = EventEvidence(
            display_text=f"Scheduled task: {sched.name}",
            source_type="timekeeper",
            domain=sched.domain,
            severity=sched.severity,
            triggered_by=sched.created_by,
        )

        event_id = await self.blackboard.create_event(
            source="timekeeper",
            service=sched.service or "general",
            reason=reason,
            evidence=evidence,
        )
        logger.info("TimeKeeper fired %s (%s) -> %s", sched.id, sched.name, event_id)

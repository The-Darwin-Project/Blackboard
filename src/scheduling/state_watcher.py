# src/scheduling/state_watcher.py
# @ai-rules:
# 1. [Constraint]: StateWatcher is pure scheduling plumbing -- no Brain logic, no LLM.
# 2. [Pattern]: Single asyncio task manages all subscriptions via a heapq priority queue.
# 3. [Gotcha]: poll_fn must be side-effect-free (read-only). Evidence mutation belongs in Brain handlers.
# 4. [Constraint]: register() replaces existing subscription for same event_id (idempotent).
# 5. [Pattern]: Deferred gate -- skip polls for events not yet in deferred status.
# 6. [Pattern]: Hook callback is injected by Brain -- StateWatcher doesn't import Brain or Blackboard.
# 7. [Gotcha]: _QueueEntry uses a monotonic _seq for heapq tie-breaking (same next_poll_at).
# 8. [Pattern]: Outer except in _poll_loop re-queues with backoff to prevent subscription orphaning.
"""
Background state watcher for deferred events.

Polls external resources (GitLab MR, Kargo stage) at configurable intervals
and fires a hook callback when state changes. Designed to wake deferred events
early instead of waiting for blind timer expiry.
"""
from __future__ import annotations

import asyncio
import heapq
import itertools
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

StateKey = dict[str, str | None]

MAX_SUBSCRIPTIONS = 20
MAX_CONSECUTIVE_FAILURES = 5
BACKOFF_BASE = 2.0
BACKOFF_CAP = 300.0

_seq_counter = itertools.count()


@runtime_checkable
class PollFn(Protocol):
    """Side-effect-free read-only poll. Returns canonical state_key fields only."""
    async def __call__(self, **resource_id: Any) -> StateKey: ...


@dataclass(frozen=True)
class GitLabMrRef:
    project_id: int
    mr_iid: int


@dataclass(frozen=True)
class KargoStageRef:
    project: str
    stage: str


ResourceRef = GitLabMrRef | KargoStageRef


@dataclass
class SubscriptionSpec:
    event_id: str
    resource_type: Literal["gitlab_mr", "kargo_stage"]
    resource_ref: ResourceRef
    poll_fn: Callable[..., Awaitable[StateKey]]
    interval: int
    state_key: StateKey
    registered_at: float
    cycle_id: str


@dataclass
class _Subscription:
    spec: SubscriptionSpec
    next_poll_at: float = 0.0
    consecutive_failures: int = 0
    backoff: float = BACKOFF_BASE
    cancelled: bool = False


@dataclass(order=True)
class _QueueEntry:
    next_poll_at: float
    seq: int = field(default_factory=lambda: next(_seq_counter))
    event_id: str = field(default="", compare=False)


OnChangeCallback = Callable[[str, StateKey, StateKey, SubscriptionSpec], Awaitable[None]]
IsDeferred = Callable[[str], Awaitable[bool]]


class StateWatcher:
    """Background poller that detects state changes on watched resources."""

    def __init__(
        self,
        on_change: OnChangeCallback,
        is_deferred: IsDeferred,
    ) -> None:
        self._on_change = on_change
        self._is_deferred = is_deferred
        self._subs: dict[str, _Subscription] = {}
        self._queue: list[_QueueEntry] = []
        self._task: asyncio.Task | None = None
        self._running = False

    def register(self, spec: SubscriptionSpec) -> bool:
        if spec.event_id in self._subs:
            old = self._subs[spec.event_id]
            old.cancelled = True
            logger.debug("StateWatcher: replacing subscription for %s", spec.event_id)
        elif len(self._subs) >= MAX_SUBSCRIPTIONS:
            logger.warning(
                "StateWatcher: cap reached (%d), rejecting %s",
                MAX_SUBSCRIPTIONS, spec.event_id,
            )
            return False

        now = time.time()
        sub = _Subscription(spec=spec, next_poll_at=now + spec.interval)
        self._subs[spec.event_id] = sub
        heapq.heappush(self._queue, _QueueEntry(sub.next_poll_at, event_id=spec.event_id))
        logger.info(
            "StateWatcher: registered %s (%s, interval=%ds)",
            spec.event_id, spec.resource_type, spec.interval,
        )
        return True

    def cancel(self, event_id: str) -> bool:
        sub = self._subs.pop(event_id, None)
        if sub:
            sub.cancelled = True
            logger.debug("StateWatcher: cancelled %s", event_id)
            return True
        return False

    def cancel_if_different_cycle(self, event_id: str, current_cycle_id: str) -> bool:
        sub = self._subs.get(event_id)
        if sub and sub.spec.cycle_id != current_cycle_id:
            return self.cancel(event_id)
        return False

    def cancel_all(self) -> int:
        count = len(self._subs)
        for sub in self._subs.values():
            sub.cancelled = True
        self._subs.clear()
        self._queue.clear()
        return count

    @property
    def active_count(self) -> int:
        return len(self._subs)

    def has_subscription(self, event_id: str) -> bool:
        return event_id in self._subs

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("StateWatcher started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.cancel_all()
        logger.info("StateWatcher stopped")

    async def _poll_loop(self) -> None:
        while self._running:
            if not self._queue:
                await asyncio.sleep(1.0)
                continue

            entry = self._queue[0]
            now = time.time()
            if entry.next_poll_at > now:
                await asyncio.sleep(min(entry.next_poll_at - now, 5.0))
                continue

            heapq.heappop(self._queue)
            sub = self._subs.get(entry.event_id)
            if not sub or sub.cancelled:
                continue

            try:
                deferred = await self._is_deferred(sub.spec.event_id)
                if not deferred:
                    sub.next_poll_at = time.time() + sub.spec.interval
                    heapq.heappush(self._queue, _QueueEntry(sub.next_poll_at, event_id=sub.spec.event_id))
                    continue

                new_state = await self._poll_resource(sub)
                if new_state is None:
                    continue

                if new_state != sub.spec.state_key:
                    logger.info(
                        "StateWatcher: %s state changed %s -> %s",
                        sub.spec.event_id, sub.spec.state_key, new_state,
                    )
                    try:
                        await self._on_change(
                            sub.spec.event_id, sub.spec.state_key, new_state, sub.spec,
                        )
                    except Exception as e:
                        logger.warning(
                            "StateWatcher: on_change failed for %s: %s",
                            sub.spec.event_id, e,
                        )
                    self._subs.pop(sub.spec.event_id, None)
                    continue

                sub.next_poll_at = time.time() + sub.spec.interval
                heapq.heappush(self._queue, _QueueEntry(sub.next_poll_at, event_id=sub.spec.event_id))

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(
                    "StateWatcher: unexpected error for %s: %s", entry.event_id, e,
                )
                sub = self._subs.get(entry.event_id)
                if sub and not sub.cancelled:
                    sub.next_poll_at = time.time() + sub.backoff
                    sub.backoff = min(sub.backoff * 2, BACKOFF_CAP)
                    heapq.heappush(self._queue, _QueueEntry(sub.next_poll_at, event_id=entry.event_id))

    async def _poll_resource(self, sub: _Subscription) -> StateKey | None:
        try:
            ref = sub.spec.resource_ref
            if isinstance(ref, GitLabMrRef):
                result = await sub.spec.poll_fn(
                    project_id=ref.project_id, mr_iid=ref.mr_iid,
                )
            elif isinstance(ref, KargoStageRef):
                result = await sub.spec.poll_fn(
                    project=ref.project, stage=ref.stage,
                )
            else:
                logger.error("StateWatcher: unknown resource ref type for %s", sub.spec.event_id)
                return None

            sub.consecutive_failures = 0
            sub.backoff = BACKOFF_BASE
            return result

        except Exception as e:
            sub.consecutive_failures += 1
            logger.warning(
                "StateWatcher: poll failed for %s (%d/%d): %s",
                sub.spec.event_id, sub.consecutive_failures,
                MAX_CONSECUTIVE_FAILURES, e,
            )
            if sub.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    "StateWatcher: %s exceeded %d consecutive failures, cancelling",
                    sub.spec.event_id, MAX_CONSECUTIVE_FAILURES,
                )
                self._subs.pop(sub.spec.event_id, None)
                return None

            sub.next_poll_at = time.time() + sub.backoff
            sub.backoff = min(sub.backoff * 2, BACKOFF_CAP)
            heapq.heappush(self._queue, _QueueEntry(sub.next_poll_at, event_id=sub.spec.event_id))
            return None

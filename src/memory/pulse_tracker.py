# BlackBoard/src/memory/pulse_tracker.py
# @ai-rules:
# 1. [Constraint]: Implements PulsePort protocol. Single on_pulse_batch entry point.
# 2. [Pattern]: Redis HINCRBY for heat (atomic, O(1)). XADD MAXLEN ~10000 for log stream.
# 3. [Pattern]: Observer pattern for fan-out to System 2 (Layer 2). Observers added via add_observer().
# 4. [Gotcha]: All operations are non-fatal -- log and continue on Redis errors.
# 5. [Pattern]: Broadcast via callable (DashboardWSAdapter pattern). None = no broadcast.
"""
PulseTracker: tracks neuron activation heat and streams pulse events.

Implements PulsePort. Receives PulseBatch from Archivist (knowledge hemisphere)
and Brain (executive hemisphere). Persists heat counters and pulse log in Redis,
broadcasts real-time pulse events via WebSocket.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Protocol

from .pulse import PulseBatch

logger = logging.getLogger(__name__)

HEAT_KEY = "darwin:pulse:heat"
LOG_KEY = "darwin:pulse:log"
LOG_MAXLEN = 10_000


class PulseObserver(Protocol):
    async def send_pulse(self, batch: PulseBatch) -> None: ...


class PulseTracker:
    """Tracks neuron activation heat and streams pulse events."""

    def __init__(
        self,
        redis,
        broadcast: Callable[[dict], Coroutine[Any, Any, None]] | None = None,
    ):
        self._redis = redis
        self._broadcast = broadcast
        self._observers: list[PulseObserver] = []

    def add_observer(self, observer: PulseObserver) -> None:
        self._observers.append(observer)

    async def on_pulse_batch(self, batch: PulseBatch) -> None:
        """PulsePort implementation. Heat + log + broadcast + fan-out."""
        try:
            pipe = self._redis.pipeline()
            for pulse in batch.pulses:
                pipe.hincrby(HEAT_KEY, pulse.neuron_id, 1)
            pipe.xadd(
                LOG_KEY,
                {"batch": json.dumps(batch.to_dict())},
                maxlen=LOG_MAXLEN,
                approximate=True,
            )
            await pipe.execute()
        except Exception as e:
            logger.warning(f"Pulse Redis write failed (non-fatal): {e}")

        batch_dict = batch.to_dict()

        if self._broadcast:
            try:
                await self._broadcast({"type": "pulse_batch", "batch": batch_dict})
            except Exception as e:
                logger.warning(f"Pulse broadcast failed (non-fatal): {e}")

        for obs in self._observers:
            asyncio.create_task(self._safe_observer_send(obs, batch))

    @staticmethod
    async def _safe_observer_send(obs, batch: PulseBatch) -> None:
        try:
            await obs.send_pulse(batch)
        except Exception as e:
            logger.warning(f"Pulse observer failed (non-fatal): {e}")

        n = len(batch.pulses)
        top_id = batch.pulses[0].neuron_id if batch.pulses else "?"
        top_score = batch.pulses[0].score if batch.pulses else 0
        logger.info(
            f"Pulse: {n} neurons fired (top={top_id}, score={top_score:.2f}) "
            f"for {batch.event_id}"
        )

    async def get_heat(self) -> dict[str, int]:
        """Return all neuron heat counters."""
        try:
            raw = await self._redis.hgetall(HEAT_KEY)
            return {k: int(v) for k, v in raw.items()}
        except Exception as e:
            logger.warning(f"get_heat failed: {e}")
            return {}

    async def get_batches(
        self,
        event_id: str | None = None,
        since: str | None = None,
        count: int = 200,
        latest: bool = False,
    ) -> list[dict]:
        """Read pulse log entries, optionally filtered by event_id or timestamp.

        Args:
            latest: If True, return the most recent `count` entries (uses XREVRANGE).
                    If False (default), return entries from `since` forward (XRANGE).
        """
        try:
            if latest:
                entries = await self._redis.xrevrange(LOG_KEY, max="+", min="-", count=count)
                entries.reverse()
            else:
                start = since or "-"
                entries = await self._redis.xrange(LOG_KEY, min=start, max="+", count=count)
            result = []
            for entry_id, fields in entries:
                batch = json.loads(fields.get("batch", "{}"))
                if event_id and batch.get("event_id") != event_id:
                    continue
                batch["_stream_id"] = entry_id
                result.append(batch)
            return result
        except Exception as e:
            logger.warning(f"get_batches failed: {e}")
            return []

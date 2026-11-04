# src/agents/llm/quota_tracker.py
# @ai-rules:
# 1. [Pattern]: Token bucket with rolling 60s window. acquire() blocks callers, record() corrects with real usage.
# 2. [Constraint]: Single event loop -- no threading locks needed. asyncio.Event + asyncio.sleep for gating.
# 3. [Gotcha]: Thinking tokens dominate cost (59/68 in probe). char/4 estimates are 5-10x low. 80% headroom is essential.
# 4. [Pattern]: get_stats() is the PV observation point for the /telemetry/llm endpoint.
# 5. [Architecture]: Reservation handles decouple acquire budget from TTFT; rollback applies negative delta.
# 6. [Constraint]: A request larger than the whole bucket raises RequestExceedsBurstError (subclass of QuotaExhaustedError) IMMEDIATELY,
#    before any reservation. It is PERMANENT for that payload: Brain._is_transient must treat it as non-retryable, and callers
#    (Nightwatcher) must shrink the request rather than wait. Plain QuotaExhaustedError (window timeout) stays transient.
"""
Token-bucket rate limiter for Vertex AI Gemini calls.

Proactively throttles LLM requests before hitting 429 limits.
Uses rolling 60-second window with estimate-then-correct accounting:
  - Pre-request: acquire(estimated_tokens) returns Reservation handle
  - Post-response: record(actual_tokens, ..., reservation) corrects with usage_metadata
  - Error/timeout: rollback(reservation) restores capacity via monotonic negative delta
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time
from collections import deque
import uuid

from .types import PRIORITY_HIGH, PRIORITY_NORMAL

logger = logging.getLogger(__name__)

__all__ = [
    "PRIORITY_HIGH",
    "PRIORITY_NORMAL",
    "QuotaExhaustedError",
    "RequestExceedsBurstError",
    "Reservation",
    "QuotaTracker",
]


class QuotaExhaustedError(Exception):
    """Raised when acquire() times out waiting for quota capacity."""


class RequestExceedsBurstError(QuotaExhaustedError):
    """Raised when a single request is larger than the whole bucket.

    Unlike plain QuotaExhaustedError this is PERMANENT for the given payload: no amount
    of waiting frees enough capacity, so callers must not treat it as a transient
    rate-limit (see Brain._is_transient). Subclasses QuotaExhaustedError so existing
    handlers (e.g. Nightwatcher's sweep) still catch it.
    """


@dataclass(frozen=True)
class Reservation:
    """Opaque handle for an active token reservation."""
    id: str
    tokens: int
    timestamp: float


class QuotaTracker:
    """Rolling-window token bucket for shared Gemini TPM quota."""

    def __init__(
        self,
        tpm_limit: int = 60000,
        burst_factor: float = 0.8,
        tpm_cap: int | None = None,
    ):
        limit = tpm_cap if tpm_cap is not None else tpm_limit
        self._tpm_limit = limit
        self._burst_limit = limit
        self._sustained_limit = int(limit * burst_factor)
        self._window: deque[tuple[float, int, str | None]] = deque()
        self._active_reservations: dict[str, Reservation] = {}
        self._total_requests = 0
        self._total_tokens = 0
        self._throttle_events = 0
        self._high_priority_waiters: int = 0
        logger.info(
            f"QuotaTracker initialized: tpm={limit}, "
            f"sustained={self._sustained_limit} (burst={burst_factor})"
        )

    def _prune(self) -> int:
        """Remove entries older than 60s, evict stale reservations (>300s, exceeding 180s HTTP timeout), return window total."""
        now = time.monotonic()
        cutoff = now - 60.0
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()

        stale_cutoff = now - 300.0
        stale_ids = [
            res_id
            for res_id, res in self._active_reservations.items()
            if res.timestamp < stale_cutoff
        ]
        for res_id in stale_ids:
            res = self._active_reservations.pop(res_id, None)
            if res is not None:
                self._total_tokens = max(0, self._total_tokens - res.tokens)

        return max(0, sum(tokens for _, tokens, *_ in self._window))

    async def acquire(
        self,
        estimated_tokens: int,
        max_wait_seconds: float = 120.0,
        priority: int = PRIORITY_NORMAL,
    ) -> Reservation:
        """Block until the bucket has capacity for estimated_tokens.

        Returns a Reservation handle on success.
        Raises QuotaExhaustedError if max_wait_seconds is exceeded, or RequestExceedsBurstError
        (a QuotaExhaustedError subclass, non-transient) if the payload alone exceeds the burst limit.
        """
        if isinstance(estimated_tokens, bool) or not isinstance(estimated_tokens, int) or estimated_tokens <= 0:
            raise ValueError(f"estimated_tokens must be a positive integer, got {estimated_tokens!r}")

        if estimated_tokens > self._burst_limit:
            raise RequestExceedsBurstError(
                f"Request of {estimated_tokens} estimated tokens exceeds the burst limit "
                f"({self._burst_limit}) and can never be admitted. Reduce the request size."
            )

        deadline = time.monotonic() + max_wait_seconds
        throttled = False

        is_high_prio = (priority == PRIORITY_HIGH)
        try:
            if is_high_prio:
                self._high_priority_waiters += 1
            while True:
                current = self._prune()
                is_gated = (not is_high_prio and self._high_priority_waiters > 0)
                if not is_gated and (current + estimated_tokens <= self._burst_limit):
                    now = time.monotonic()
                    res = Reservation(id=str(uuid.uuid4()), tokens=estimated_tokens, timestamp=now)
                    self._window.append((now, estimated_tokens, res.id))
                    self._total_requests += 1
                    self._total_tokens += estimated_tokens
                    self._active_reservations[res.id] = res

                    if current > self._sustained_limit:
                        logger.debug(
                            f"QuotaTracker: above sustained limit "
                            f"({current}/{self._sustained_limit}), allowing burst"
                        )
                    return res

                if not throttled:
                    self._throttle_events += 1
                    throttled = True

                if time.monotonic() >= deadline:
                    raise QuotaExhaustedError(
                        f"Quota exhausted: {current}/{self._tpm_limit} tokens used in last 60s. "
                        f"Waited {max_wait_seconds:.1f}s for {estimated_tokens} tokens without capacity."
                    )

                wait = max(0.01, min(2.0, deadline - time.monotonic()))
                if is_gated:
                    logger.info(
                        f"QuotaTracker: gated by {self._high_priority_waiters} high-priority waiter(s). "
                        f"Waiting {wait:.1f}s..."
                    )
                else:
                    logger.warning(
                        f"QuotaTracker: throttling ({current}/{self._sustained_limit} tokens). "
                        f"Waiting {wait:.1f}s..."
                    )
                await asyncio.sleep(wait)
        finally:
            if is_high_prio:
                self._high_priority_waiters = max(0, self._high_priority_waiters - 1)

    def rollback(self, reservation: Reservation | None) -> None:
        """Rollback an active reservation on timeout, exception, or empty response."""
        if reservation is None or reservation.id not in self._active_reservations:
            return

        del self._active_reservations[reservation.id]
        now = time.monotonic()
        elapsed = now - reservation.timestamp
        if elapsed < 60.0:
            idx = None
            for i, entry in enumerate(self._window):
                if len(entry) >= 3 and entry[2] == reservation.id:
                    idx = i
                    break
            if idx is not None:
                self._window.insert(idx + 1, (reservation.timestamp, -reservation.tokens, None))

        self._total_tokens = max(0, self._total_tokens - reservation.tokens)
        self._prune()
        logger.debug(f"QuotaTracker: rolled back reservation {reservation.id} (-{reservation.tokens} tokens)")

    def record(
        self,
        actual_tokens: int,
        estimated_tokens: int = 0,
        reservation: Reservation | None = None,
    ) -> None:
        """Correct the most recent estimate with real usage_metadata count.

        Pops the active reservation if provided, and adds the delta.
        """
        if reservation is not None:
            if reservation.id not in self._active_reservations:
                # Already rolled back or recorded; early-return to preserve symmetry
                logger.debug(f"QuotaTracker: ignoring record() for finalized reservation {reservation.id}")
                return
            del self._active_reservations[reservation.id]

        if actual_tokens == estimated_tokens:
            return

        delta = actual_tokens - estimated_tokens
        now = time.monotonic()

        self._window.append((now, delta, None))
        self._total_tokens += delta
        logger.debug(
            f"QuotaTracker: recorded {actual_tokens} actual "
            f"(estimate was {estimated_tokens}, delta={delta:+d})"
        )

    def get_stats(self) -> dict:
        """Return current quota state for observability."""
        current = self._prune()
        return {
            "tokens_used_60s": current,
            "tpm_limit": self._tpm_limit,
            "tokens_remaining": max(0, self._tpm_limit - current),
            "utilization_pct": round(current / self._tpm_limit * 100, 1) if self._tpm_limit else 0,
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "throttle_events": self._throttle_events,
            "active_reservations": len(self._active_reservations),
            "high_priority_waiters": self._high_priority_waiters,
        }

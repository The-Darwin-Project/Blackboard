# src/agents/llm/quota_tracker.py
# @ai-rules:
# 1. [Pattern]: Token bucket with rolling 60s window. acquire() blocks callers, record() corrects with real usage.
# 2. [Constraint]: Single event loop -- no threading locks needed. asyncio.Event + asyncio.sleep for gating.
# 3. [Gotcha]: Thinking tokens dominate cost (59/68 in probe). char/4 estimates are 5-10x low. 80% headroom is essential.
# 4. [Pattern]: get_stats() is the PV observation point for the /telemetry/llm endpoint.
"""
Token-bucket rate limiter for Vertex AI Gemini calls.

Proactively throttles LLM requests before hitting 429 limits.
Uses rolling 60-second window with estimate-then-correct accounting:
  - Pre-request: acquire(estimated_tokens) blocks if bucket is depleted
  - Post-response: record(actual_tokens) corrects with usage_metadata
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger(__name__)


class QuotaExhaustedError(Exception):
    """Raised when acquire() times out waiting for quota capacity."""


class QuotaTracker:
    """Rolling-window token bucket for shared Gemini TPM quota."""

    def __init__(self, tpm_limit: int, burst_factor: float = 0.8):
        self._tpm_limit = tpm_limit
        self._burst_limit = tpm_limit
        self._sustained_limit = int(tpm_limit * burst_factor)
        self._window: deque[tuple[float, int]] = deque()
        self._total_requests = 0
        self._total_tokens = 0
        self._throttle_events = 0
        logger.info(
            f"QuotaTracker initialized: tpm={tpm_limit}, "
            f"sustained={self._sustained_limit} (burst={burst_factor})"
        )

    def _prune(self) -> int:
        """Remove entries older than 60s, return current window total."""
        cutoff = time.monotonic() - 60.0
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()
        return sum(tokens for _, tokens in self._window)

    async def acquire(self, estimated_tokens: int, max_wait_seconds: float = 120.0) -> None:
        """Block until the bucket has capacity for estimated_tokens.

        Raises QuotaExhaustedError if max_wait_seconds is exceeded.
        """
        deadline = time.monotonic() + max_wait_seconds
        throttled = False

        while True:
            current = self._prune()
            if current + estimated_tokens <= self._burst_limit:
                self._window.append((time.monotonic(), estimated_tokens))
                self._total_requests += 1
                self._total_tokens += estimated_tokens
                if current > self._sustained_limit:
                    logger.debug(
                        f"QuotaTracker: above sustained limit "
                        f"({current}/{self._sustained_limit}), allowing burst"
                    )
                return

            if not throttled:
                self._throttle_events += 1
                throttled = True

            if time.monotonic() >= deadline:
                raise QuotaExhaustedError(
                    f"Quota exhausted: {current}/{self._tpm_limit} tokens in window, "
                    f"waited {max_wait_seconds}s"
                )

            wait = min(2.0, deadline - time.monotonic())
            logger.warning(
                f"QuotaTracker: throttling ({current}/{self._sustained_limit} tokens). "
                f"Waiting {wait:.1f}s..."
            )
            await asyncio.sleep(wait)

    def record(self, actual_tokens: int, estimated_tokens: int) -> None:
        """Correct the most recent estimate with real usage_metadata count.

        Replaces the estimate entry with the actual count. If actual > estimate,
        the delta is added; if actual < estimate, tokens are freed.
        """
        if actual_tokens == estimated_tokens:
            return

        delta = actual_tokens - estimated_tokens
        now = time.monotonic()

        self._window.append((now, delta))
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
        }
